"""GetM4A 核心逻辑无头测试：生成测试媒体 → 转换 → ffprobe 校验。"""
import os
import shutil
import subprocess
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import getm4a as g

FFMPEG = g.find_tool("ffmpeg")
NW = g.NO_WINDOW
TMP = tempfile.mkdtemp(prefix="getm4a_test_")


def run(args):
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y"] + args,
                   check=True, creationflags=NW)


def make_media():
    run(["-f", "lavfi", "-i", "testsrc2=duration=3:size=128x72:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
         "-c:v", "mpeg4", "-q:v", "5", "-c:a", "aac", "-b:a", "96k",
         os.path.join(TMP, "aac.mp4")])
    run(["-f", "lavfi", "-i", "testsrc2=duration=3:size=128x72:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
         "-f", "lavfi", "-i", "sine=frequency=880:duration=3",
         "-map", "0:v", "-map", "1:a", "-map", "2:a",
         "-c:v", "mpeg4", "-q:v", "5",
         "-c:a:0", "aac", "-ac:a:0", "2", "-metadata:s:a:0", "language=jpn",
         "-c:a:1", "flac", "-ac:a:1", "1", "-metadata:s:a:1", "language=eng",
         os.path.join(TMP, "dual.mkv")])
    run(["-f", "lavfi", "-i", "testsrc2=duration=3:size=128x72:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
         "-c:v", "libvpx", "-b:v", "200k", "-c:a", "libopus",
         os.path.join(TMP, "opus.webm")])


def out_codec(path):
    streams, _ = g.probe(path)
    assert len(streams) == 1, f"期望单音轨: {path}"
    return streams[0]


def test_probe():
    streams, dur = g.probe(os.path.join(TMP, "aac.mp4"))
    assert len(streams) == 1 and streams[0]["codec_name"] == "aac"
    assert dur and 2.5 < dur < 3.5
    streams, _ = g.probe(os.path.join(TMP, "dual.mkv"))
    assert [s["codec_name"] for s in streams] == ["aac", "flac"]
    assert streams[1]["tags"]["language"] == "eng"


def test_m4a_copy():
    src = os.path.join(TMP, "aac.mp4")
    streams, dur = g.probe(src)
    dst = os.path.join(TMP, "copy.m4a")
    st, detail = g.convert(src, dst, "m4a", streams[0]["index"], "aac", dur)
    assert st == "ok", detail
    s = out_codec(dst)
    assert s["codec_name"] == "aac"
    args = g.build_args(src, dst, "m4a", 0, "aac")
    assert "copy" in args


def test_m4a_transcode():
    src = os.path.join(TMP, "opus.webm")
    streams, dur = g.probe(src)
    dst = os.path.join(TMP, "trans.m4a")
    st, detail = g.convert(src, dst, "m4a", streams[0]["index"], "opus", dur)
    assert st == "ok", detail
    assert out_codec(dst)["codec_name"] == "aac"


def test_track_selection():
    src = os.path.join(TMP, "dual.mkv")
    streams, dur = g.probe(src)
    dst = os.path.join(TMP, "track1.flac")
    st, detail = g.convert(src, dst, "flac", streams[1]["index"], "flac", dur)
    assert st == "ok", detail
    s = out_codec(dst)
    assert s["codec_name"] == "flac" and s["channels"] == 1, s


def test_mp3():
    src = os.path.join(TMP, "aac.mp4")
    streams, dur = g.probe(src)
    dst = os.path.join(TMP, "out.mp3")
    st, detail = g.convert(src, dst, "mp3", streams[0]["index"], "aac", dur)
    assert st == "ok", detail
    assert out_codec(dst)["codec_name"] == "mp3"


def test_unique_path():
    stem, ext = "song", "m4a"
    p0 = g.unique_path(TMP, stem, ext)
    assert p0 == os.path.join(TMP, "song.m4a")
    open(p0, "w").close()
    p1 = g.unique_path(TMP, stem, ext)
    assert p1 == os.path.join(TMP, "song (1).m4a")


def test_cancel():
    src = os.path.join(TMP, "aac.mp4")
    streams, dur = g.probe(src)
    dst = os.path.join(TMP, "cancelled.mp3")
    ev = threading.Event()
    ev.set()
    st, _ = g.convert(src, dst, "mp3", streams[0]["index"], "aac", dur, cancel_event=ev)
    assert st == "cancelled"
    assert not os.path.exists(dst)


def test_progress():
    src = os.path.join(TMP, "aac.mp4")
    streams, dur = g.probe(src)
    dst = os.path.join(TMP, "prog.flac")
    seen = []
    st, detail = g.convert(src, dst, "flac", streams[0]["index"], "aac", dur,
                           on_progress=seen.append)
    assert st == "ok", detail
    assert seen and seen[-1] == 100.0


def main():
    make_media()
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()