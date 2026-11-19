"""GetM4A — 从视频容器提取音频流，导出 m4a / flac / mp3。

仅依赖 Python 标准库 + 外部 LGPL ffmpeg/ffprobe。
"""
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

FORMATS = ("m4a", "flac", "mp3")
VIDEO_FILTER = ("视频文件", "*.mp4 *.mkv *.webm *.mov *.avi *.ts *.flv *.m4v *.wmv *.mpg *.mpeg *.m2ts *.ogg *.opus")
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def find_tool(name):
    exe = name + (".exe" if os.name == "nt" else "")
    bases = [app_dir(), getattr(sys, "_MEIPASS", app_dir())]
    for base in bases:
        local = os.path.join(base, "ffmpeg", exe)
        if os.path.isfile(local):
            return local
    found = shutil.which(name)
    if found:
        return found
    raise FileNotFoundError(f"找不到 {name}，请将其放入程序目录的 ffmpeg/ 子目录或加入 PATH")


def probe(path):
    """返回 (streams, duration)；streams 为音轨列表，duration 为容器时长（秒，可能为 None）。"""
    cmd = [find_tool("ffprobe"), "-v", "error", "-select_streams", "a",
           "-show_entries",
           "stream=index,codec_name,channels,sample_rate:stream_tags=language,title",
           "-show_entries", "format=duration", "-of", "json", path]
    out = subprocess.run(cmd, capture_output=True, text=True,
                         creationflags=NO_WINDOW, check=True)
    data = json.loads(out.stdout)
    streams = data.get("streams", [])
    try:
        duration = float(data.get("format", {}).get("duration"))
    except (TypeError, ValueError):
        duration = None
    return streams, duration


def build_args(src, dst, fmt, stream_index, codec):
    args = ["-hide_banner", "-loglevel", "error", "-nostats", "-progress", "pipe:1",
            "-i", src, "-map", f"0:{stream_index}", "-vn", "-sn", "-dn"]
    if fmt == "m4a":
        if codec == "aac":
            args += ["-c:a", "copy", "-movflags", "+faststart"]
        else:
            args += ["-c:a", "aac", "-b:a", "192k"]
    elif fmt == "flac":
        args += ["-c:a", "flac"]
    elif fmt == "mp3":
        args += ["-c:a", "libmp3lame", "-q:a", "2"]
    else:
        raise ValueError(f"不支持的格式: {fmt}")
    return args + ["-y", dst]


def unique_path(outdir, stem, ext):
    candidate = os.path.join(outdir, f"{stem}.{ext}")
    n = 1
    while os.path.exists(candidate):
        candidate = os.path.join(outdir, f"{stem} ({n}).{ext}")
        n += 1
    return candidate


def convert(src, dst, fmt, stream_index, codec, duration,
            on_progress=None, cancel_event=None):
    """执行转换。返回 (status, detail)，status ∈ ok / error / cancelled。"""
    cmd = [find_tool("ffmpeg")] + build_args(src, dst, fmt, stream_index, codec)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace",
                            creationflags=NO_WINDOW)
    err_chunks = []
    threading.Thread(target=lambda: err_chunks.append(proc.stderr.read()),
                     daemon=True).start()
    status, detail = "ok", ""
    for line in proc.stdout:
        if cancel_event is not None and cancel_event.is_set():
            proc.terminate()
            status = "cancelled"
            break
        line = line.strip()
        if line.startswith("out_time_us=") and duration:
            try:
                us = int(line.split("=", 1)[1])
                if us >= 0 and on_progress:
                    on_progress(min(99.0, us / 1e6 / duration * 100))
            except ValueError:
                pass
        elif line == "progress=end" and on_progress:
            on_progress(100.0)
    proc.wait()
    if status == "ok" and proc.returncode != 0:
        status = "error"
        detail = "".join(err_chunks).strip().splitlines()
        detail = detail[-1] if detail else f"ffmpeg 退出码 {proc.returncode}"
    if status != "ok":
        try:
            os.remove(dst)
        except OSError:
            pass
    return status, detail


def track_label(s):
    parts = [f"#{s['index']} {s.get('codec_name', '?')}"]
    if s.get("channels"):
        parts.append(f"{s['channels']}ch")
    tags = s.get("tags", {})
    if tags.get("language"):
        parts.append(tags["language"])
    if tags.get("title"):
        parts.append(tags["title"])
    return " ".join(parts)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GetM4A — 音频提取")
        self.geometry("780x500")
        self.minsize(640, 400)
        self.items = {}          # iid -> dict(path, streams, duration, track)
        self.q = queue.Queue()
        self.cancel_event = threading.Event()
        self.running = False
        self._build_ui()
        self.after(100, self._poll)

    def _build_ui(self):
        top = ttk.Frame(self, padding=(8, 8, 8, 4))
        top.pack(fill="x")
        ttk.Button(top, text="添加文件", command=self.add_files).pack(side="left")
        ttk.Button(top, text="移除", command=self.remove_selected).pack(side="left", padx=4)
        ttk.Button(top, text="清空", command=self.clear_all).pack(side="left")

        cols = ("file", "track", "status", "progress")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="extended")
        for c, text, width, anchor in (
                ("file", "文件", 340, "w"), ("track", "音轨", 180, "w"),
                ("status", "状态", 120, "w"), ("progress", "进度", 70, "e")):
            self.tree.heading(c, text=text)
            self.tree.column(c, width=width, anchor=anchor, stretch=(c == "file"))
        self.tree.pack(fill="both", expand=True, padx=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        mid = ttk.Frame(self, padding=(8, 4))
        mid.pack(fill="x")
        ttk.Label(mid, text="选中文件音轨:").pack(side="left")
        self.track_box = ttk.Combobox(mid, state="readonly", width=42)
        self.track_box.pack(side="left", padx=4)
        self.track_box.bind("<<ComboboxSelected>>", self._on_track)

        out = ttk.Frame(self, padding=(8, 4))
        out.pack(fill="x")
        ttk.Label(out, text="输出格式:").pack(side="left")
        self.fmt_box = ttk.Combobox(out, state="readonly", width=6, values=FORMATS)
        self.fmt_box.current(0)
        self.fmt_box.pack(side="left", padx=(4, 16))
        ttk.Label(out, text="输出目录:").pack(side="left")
        self.dir_var = tk.StringVar()
        ttk.Entry(out, textvariable=self.dir_var).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(out, text="浏览…", command=self.pick_dir).pack(side="left")

        bottom = ttk.Frame(self, padding=(8, 4, 8, 8))
        bottom.pack(fill="x")
        self.start_btn = ttk.Button(bottom, text="开始转换", command=self.start)
        self.start_btn.pack(side="left")
        self.cancel_btn = ttk.Button(bottom, text="取消", command=self.cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=4)
        self.bar = ttk.Progressbar(bottom, maximum=100)
        self.bar.pack(side="left", fill="x", expand=True, padx=8)
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(self, textvariable=self.status_var, padding=(8, 0, 8, 6)).pack(fill="x")

    # ---------- 文件管理 ----------
    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="选择视频文件", filetypes=[VIDEO_FILTER, ("所有文件", "*.*")])
        existing = {it["path"] for it in self.items.values()}
        added = []
        for p in paths:
            if p in existing:
                continue
            iid = self.tree.insert("", "end", values=(p, "探测中…", "等待", ""))
            self.items[iid] = {"path": p, "streams": [], "duration": None, "track": 0}
            added.append(iid)
        if added:
            if not self.dir_var.get():
                self.dir_var.set(os.path.dirname(self.items[added[0]]["path"]))
            threading.Thread(target=self._probe_worker, args=(added,), daemon=True).start()

    def _probe_worker(self, iids):
        for iid in iids:
            path = self.items[iid]["path"]
            try:
                streams, duration = probe(path)
                self.q.put(("probed", iid, streams, duration, None))
            except Exception as e:
                self.q.put(("probed", iid, [], None, str(e)))

    def remove_selected(self):
        if self.running:
            return
        for iid in self.tree.selection():
            self.tree.delete(iid)
            self.items.pop(iid, None)
        self._on_select()

    def clear_all(self):
        if self.running:
            return
        self.tree.delete(*self.tree.get_children())
        self.items.clear()
        self._on_select()

    def pick_dir(self):
        d = filedialog.askdirectory(title="选择输出目录", initialdir=self.dir_var.get() or None)
        if d:
            self.dir_var.set(d)

    def _on_select(self, _=None):
        sel = self.tree.selection()
        if len(sel) == 1 and sel[0] in self.items:
            it = self.items[sel[0]]
            labels = [track_label(s) for s in it["streams"]]
            self.track_box["values"] = labels
            if labels:
                self.track_box.current(min(it["track"], len(labels) - 1))
            else:
                self.track_box.set("")
        else:
            self.track_box["values"] = []
            self.track_box.set("")

    def _on_track(self, _=None):
        sel = self.tree.selection()
        if len(sel) == 1 and sel[0] in self.items:
            it = self.items[sel[0]]
            idx = self.track_box.current()
            if 0 <= idx < len(it["streams"]):
                it["track"] = idx
                self.tree.set(sel[0], "track", track_label(it["streams"][idx]))

    # ---------- 转换 ----------
    def start(self):
        if self.running:
            return
        jobs = []
        for iid, it in self.items.items():
            if not it["streams"]:
                continue
            s = it["streams"][it["track"]]
            jobs.append((iid, it["path"], s["index"], s.get("codec_name", ""), it["duration"]))
        if not jobs:
            messagebox.showinfo("GetM4A", "没有可转换的文件（请先添加含音轨的视频）")
            return
        outdir = self.dir_var.get().strip()
        if not outdir:
            outdir = os.path.dirname(jobs[0][1])
            self.dir_var.set(outdir)
        if not os.path.isdir(outdir):
            messagebox.showerror("GetM4A", f"输出目录不存在：{outdir}")
            return
        fmt = self.fmt_box.get()
        self.running = True
        self.cancel_event.clear()
        self.start_btn.state(["disabled"])
        self.cancel_btn.state(["!disabled"])
        for iid, *_ in jobs:
            self.tree.set(iid, "status", "等待")
            self.tree.set(iid, "progress", "")
        self.bar["value"] = 0
        threading.Thread(target=self._worker, args=(jobs, fmt, outdir), daemon=True).start()

    def _worker(self, jobs, fmt, outdir):
        done = failed = 0
        total = len(jobs)
        for n, (iid, path, sidx, codec, duration) in enumerate(jobs):
            if self.cancel_event.is_set():
                self.q.put(("status", iid, "已取消", ""))
                continue
            stem = os.path.splitext(os.path.basename(path))[0]
            dst = unique_path(outdir, stem, fmt)
            self.q.put(("status", iid, "转换中…", "0%"))

            def prog(pct, iid=iid, n=n):
                self.q.put(("progress", iid, pct, (n + pct / 100) / total * 100))

            status, detail = convert(path, dst, fmt, sidx, codec, duration,
                                     on_progress=prog, cancel_event=self.cancel_event)
            if status == "ok":
                done += 1
                self.q.put(("status", iid, "完成", "100%"))
            elif status == "cancelled":
                self.q.put(("status", iid, "已取消", ""))
            else:
                failed += 1
                self.q.put(("status", iid, f"失败: {detail}", ""))
            self.q.put(("overall", (n + 1) / total * 100))
        self.q.put(("finished", done, failed, total))

    def cancel(self):
        self.cancel_event.set()
        self.status_var.set("正在取消…")

    # ---------- 消息循环 ----------
    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "probed":
                    _, iid, streams, duration, err = msg
                    if iid not in self.items:
                        continue
                    it = self.items[iid]
                    it["streams"], it["duration"] = streams, duration
                    if err:
                        self.tree.set(iid, "track", "探测失败")
                        self.tree.set(iid, "status", err[:60])
                    elif not streams:
                        self.tree.set(iid, "track", "无音轨")
                        self.tree.set(iid, "status", "跳过")
                    else:
                        it["track"] = 0
                        self.tree.set(iid, "track", track_label(streams[0]))
                        self.tree.set(iid, "status", "等待")
                        self._on_select()
                elif kind == "status":
                    _, iid, text, pct = msg
                    self.tree.set(iid, "status", text)
                    self.tree.set(iid, "progress", pct)
                elif kind == "progress":
                    _, iid, pct, overall = msg
                    self.tree.set(iid, "progress", f"{pct:.0f}%")
                    self.bar["value"] = overall
                elif kind == "overall":
                    self.bar["value"] = msg[1]
                elif kind == "finished":
                    _, done, failed, total = msg
                    self.running = False
                    self.start_btn.state(["!disabled"])
                    self.cancel_btn.state(["disabled"])
                    self.bar["value"] = 100
                    cancelled = total - done - failed
                    parts = [f"完成 {done}"]
                    if failed:
                        parts.append(f"失败 {failed}")
                    if cancelled:
                        parts.append(f"取消 {cancelled}")
                    self.status_var.set("，".join(parts))
        except queue.Empty:
            pass
        self.after(100, self._poll)


if __name__ == "__main__":
    App().mainloop()