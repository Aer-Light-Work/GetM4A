"""打包 GetM4A：准备 LGPL ffmpeg → PyInstaller onedir。

用法：python build.py
ffmpeg 来源优先级：环境变量 GETM4A_FFMPEG_DIR → 本机已知路径 → 下载 BtbN LGPL 构建。
"""
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(ROOT, "vendor", "ffmpeg")
LOCAL_BUILD = r"D:\Tools\ffmpeg-n7.1-latest-win64-lgpl-shared-7.1"
BTBN_URL = ("https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
            "ffmpeg-master-latest-win64-lgpl-shared.zip")


def prepare_ffmpeg():
    os.makedirs(VENDOR, exist_ok=True)
    src = os.environ.get("GETM4A_FFMPEG_DIR") or (
        LOCAL_BUILD if os.path.isdir(LOCAL_BUILD) else None)
    if src:
        bin_dir = os.path.join(src, "bin")
        lic = os.path.join(src, "LICENSE.txt")
    else:
        print(f"下载 LGPL 构建: {BTBN_URL}")
        zip_path = os.path.join(ROOT, "vendor", "ffmpeg-lgpl.zip")
        urllib.request.urlretrieve(BTBN_URL, zip_path)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(os.path.join(ROOT, "vendor"))
        extracted = next(d for d in os.listdir(os.path.join(ROOT, "vendor"))
                         if d.startswith("ffmpeg-") and os.path.isdir(
                             os.path.join(ROOT, "vendor", d)))
        src = os.path.join(ROOT, "vendor", extracted)
        bin_dir = os.path.join(src, "bin")
        lic = os.path.join(src, "LICENSE.txt")
        os.remove(zip_path)
    for f in os.listdir(bin_dir):
        if f == "ffplay.exe" or not (f.endswith(".dll") or f in ("ffmpeg.exe", "ffprobe.exe")):
            continue
        shutil.copy2(os.path.join(bin_dir, f), VENDOR)
    if os.path.isfile(lic):
        shutil.copy2(lic, os.path.join(VENDOR, "LICENSE.txt"))
    print(f"ffmpeg 已就绪: {VENDOR}")


def build():
    prepare_ffmpeg()
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