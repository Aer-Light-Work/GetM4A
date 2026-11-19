"""GUI 链路测试：注入文件 → 启动转换 → 校验产物与界面状态（不依赖手动点击）。"""
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import getm4a as g

TMP = tempfile.mkdtemp(prefix="getm4a_gui_")
SRC = os.path.join(TMP, "sample.mp4")
OUT = os.path.join(TMP, "out")
os.makedirs(OUT)

subprocess.run([g.find_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "testsrc2=duration=2:size=128x72:rate=10",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                "-c:v", "mpeg4", "-q:v", "5", "-c:a", "aac", SRC],
               check=True, creationflags=g.NO_WINDOW)

app = g.App()
failed = 0
total = 4
for fmt in g.FORMATS:
    iid = app.tree.insert("", "end", values=(SRC, "探测中…", "等待", ""))
    app.items[iid] = {"path": SRC, "streams": [], "duration": None, "track": 0}
    app._probe_worker([iid])
    app.update()
    app.dir_var.set(OUT)
    app.fmt_box.set(fmt)
    app.start()
    deadline = time.time() + 30
    while app.running and time.time() < deadline:
        app.update()
        time.sleep(0.05)
    app.update()
    dst = os.path.join(OUT, f"sample.{fmt}")
    ok = (not app.running) and os.path.isfile(dst) and app.tree.set(iid, "status") == "完成"
    if ok:
        streams, _ = g.probe(dst)
        ok = len(streams) == 1
    print(f"{'PASS' if ok else 'FAIL'} gui_{fmt}: status={app.tree.set(iid, 'status')!r}")
    failed += 0 if ok else 1

# 多音轨选择：dual.mkv 第二条音轨（flac 单声道）→ flac
dual = os.path.join(TMP, "dual.mkv")
subprocess.run([g.find_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "testsrc2=duration=2:size=128x72:rate=10",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                "-f", "lavfi", "-i", "sine=frequency=880:duration=2",
                "-map", "0:v", "-map", "1:a", "-map", "2:a",
                "-c:v", "mpeg4", "-q:v", "5",
                "-c:a:0", "aac", "-ac:a:0", "2",
                "-c:a:1", "flac", "-ac:a:1", "1", dual],
               check=True, creationflags=g.NO_WINDOW)
iid = app.tree.insert("", "end", values=(dual, "探测中…", "等待", ""))
app.items[iid] = {"path": dual, "streams": [], "duration": None, "track": 0}
app._probe_worker([iid])
app.update()
app.tree.selection_set(iid)
app._on_select()
app.track_box.current(1)
app._on_track()
app.dir_var.set(OUT)
app.fmt_box.set("flac")
app.start()
deadline = time.time() + 30
while app.running and time.time() < deadline:
    app.update()
    time.sleep(0.05)
app.update()
dst = os.path.join(OUT, "dual.flac")
ok = os.path.isfile(dst) and app.tree.set(iid, "status") == "完成"
if ok:
    streams, _ = g.probe(dst)
    ok = len(streams) == 1 and streams[0]["channels"] == 1
print(f"{'PASS' if ok else 'FAIL'} gui_track_select")
failed += 0 if ok else 1
app.destroy()
print(f"\n{total - failed}/{total} passed")
sys.exit(1 if failed else 0)