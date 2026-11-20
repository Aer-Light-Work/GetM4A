"""打包 GetM4A：准备并校验 LGPL ffmpeg → PyInstaller onedir。

用法：python build.py
ffmpeg 来源优先级：环境变量 GETM4A_FFMPEG_DIR → 本机已知路径（仅 Windows）
→ 下载 ffmpeg-build-flow 的滚动 LGPL 构建（三平台）→ 回落 BtbN
（仅 Windows/Linux）。
"""
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

if os.name == "nt":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(ROOT, "vendor", "ffmpeg")
LOCAL_BUILD = r"D:\Tools\ffmpeg-n7.1-latest-win64-lgpl-shared-7.1"
ROLLING = "https://github.com/Aer-Light-Work/ffmpeg-build-flow/releases/download/latest/"
URLS = {
    "win32": ROLLING + "ffmpeg-win64-lgpl-shared.zip",
    "linux": ROLLING + "ffmpeg-linux64-lgpl.tar.xz",
    "darwin": ROLLING + "ffmpeg-macos-arm64-lgpl.tar.xz",
}
BTBN = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
FALLBACK_URLS = {
    "win32": BTBN + "ffmpeg-master-latest-win64-lgpl-shared.zip",
    "linux": BTBN + "ffmpeg-master-latest-linux64-lgpl.tar.xz",
}
EXE = ".exe" if os.name == "nt" else ""


def prepare_ffmpeg():
    os.makedirs(VENDOR, exist_ok=True)
    src = os.environ.get("GETM4A_FFMPEG_DIR")
    if not src and os.name == "nt" and os.path.isdir(LOCAL_BUILD):
        src = LOCAL_BUILD
    if not src:
        urls = [u for u in (URLS.get(sys.platform), FALLBACK_URLS.get(sys.platform)) if u]
        if not urls:
            raise SystemExit(f"本平台（{sys.platform}）没有可用的 LGPL 构建源，请自行编译并设置 "
                             "GETM4A_FFMPEG_DIR（指向含 bin/ 与 LICENSE.txt 的目录）")
        archive = None
        for url in urls:
            print(f"下载 LGPL 构建: {url}")
            archive = os.path.join(VENDOR, os.path.basename(url))
            try:
                urllib.request.urlretrieve(url, archive)
                break
            except OSError as exc:
                print(f"下载失败：{exc}")
                archive = None
        if archive is None:
            raise SystemExit("LGPL 构建的所有源都不可达")
        if archive.endswith(".zip"):
            with zipfile.ZipFile(archive) as z:
                z.extractall(os.path.join(ROOT, "vendor"))
        else:
            with tarfile.open(archive) as t:
                t.extractall(os.path.join(ROOT, "vendor"))
        extracted = next(d for d in os.listdir(os.path.join(ROOT, "vendor"))
                         if d.startswith("ffmpeg-") and os.path.isdir(
                             os.path.join(ROOT, "vendor", d)))
        src = os.path.join(ROOT, "vendor", extracted)
        os.remove(archive)
    bin_dir = os.path.join(src, "bin")
    for f in os.listdir(bin_dir):
        if f.startswith("ffplay"):
            continue
        if f.endswith(".dll") or f in ("ffmpeg" + EXE, "ffprobe" + EXE):
            shutil.copy2(os.path.join(bin_dir, f), VENDOR)
    lic = os.path.join(src, "LICENSE.txt")
    if os.path.isfile(lic):
        shutil.copy2(lic, os.path.join(VENDOR, "LICENSE.txt"))
    print(f"ffmpeg 已就绪: {VENDOR}")


def verify_lgpl():
    """强制校验捆绑构建符合 LGPL 条件：无 GPL/nonfree 组件，且含所需编码器。"""
    ffmpeg = os.path.join(VENDOR, "ffmpeg" + EXE)
    ver = subprocess.run([ffmpeg, "-hide_banner", "-version"],
                         capture_output=True, text=True, check=True).stdout
    if "--enable-gpl" in ver or "--enable-nonfree" in ver:
        raise SystemExit("拒绝打包：ffmpeg 构建含 GPL/nonfree 组件，不符合 LGPL 条件")
    enc = subprocess.run([ffmpeg, "-hide_banner", "-encoders"],
                         capture_output=True, text=True, check=True).stdout
    for name in ("aac", "flac", "libmp3lame"):
        if name not in enc:
            raise SystemExit(f"拒绝打包：ffmpeg 缺少编码器 {name}")
    print("LGPL 合规校验通过（无 --enable-gpl/--enable-nonfree，aac/flac/libmp3lame 齐全）")


def build():
    prepare_ffmpeg()
    if os.environ.get("GETM4A_SKIP_LGPL_VERIFY") == "1":
        print("警告：已跳过 LGPL 合规校验（全功能版捆绑 GPL 构建）")
    else:
        verify_lgpl()
    sep = ";" if os.name == "nt" else ":"
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--noconsole",
           "--onedir", "--name", "GetM4A",
           "--add-binary", os.path.join(ROOT, "vendor", "ffmpeg") + sep + "ffmpeg",
           os.path.join(ROOT, "getm4a.py")]
    subprocess.run(cmd, check=True, cwd=ROOT)
    dist = os.path.join(ROOT, "dist", "GetM4A")
    for f in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(os.path.join(ROOT, f), dist)
    print(f"\n打包完成: {dist}")


if __name__ == "__main__":
    build()