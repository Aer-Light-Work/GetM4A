# GetM4A

从视频容器（.mp4 / .mkv / .webm / .mov 等）提取音频流，导出为 **m4a / flac / mp3** 的跨平台小工具。

- 单文件 Python + tkinter（仅标准库），原生系统文件/目录选择器
- 批量转换、多音轨选择、实时进度、可取消
- m4a 智能直提：源音频为 AAC 时无损 stream copy，秒级完成；其他编码自动转码
- 捆绑 **LGPL 版 FFmpeg**（shared 构建），目标机器无需安装任何运行时

## 直接使用（Windows）

运行打包产物 `dist/GetM4A/GetM4A.exe`（整个 GetM4A 目录可压缩分发）。

## 从源码运行（Windows / macOS / Linux）

需要 Python 3.10+ 与 ffmpeg/ffprobe（放入程序目录的 `ffmpeg/` 子目录，或在 PATH 中）：

```bash
python getm4a.py
```

## 开发与打包（uv 独立环境）

```bash
uv sync                 # 创建 .venv 并安装 PyInstaller
uv run python tests/test_core.py
uv run python build.py  # 准备 LGPL ffmpeg + PyInstaller onedir 打包
```

`build.py` 自动准备 LGPL ffmpeg（环境变量 `GETM4A_FFMPEG_DIR` 指定本地构建 →
本机已知路径 → 下载 BtbN win64-lgpl-shared 构建），然后 PyInstaller onedir 打包。

macOS / Linux：在对应系统上安装 Python + PyInstaller，将本平台的 LGPL ffmpeg
放入 `vendor/ffmpeg/` 后运行 `python build.py`（或直接源码运行）。

## 测试

```bash
uv run python tests/test_core.py
```

## 许可

应用代码：LGPL-2.1（见 LICENSE）。FFmpeg：LGPL（见 THIRD_PARTY_NOTICES.md）。

## CI 发行版本（GitHub Actions）

| Workflow | 产物 | FFmpeg 来源 | 说明 |
|---|---|---|---|
| `build.yml` | `GetM4A-<OS>.zip` | BtbN LGPL 构建 / macOS 源码编译 | LGPL 合规版，捆绑 LGPL ffmpeg |
| `build-bundled.yml` | `GetM4A-full-<OS>.zip` | gyan.dev (Win) / johnvans.com (Linux) / evermeet.cx (macOS) | 全功能版，自动捆绑完整 ffmpeg，用户无需自行准备可执行文件 |

两个版本均已内置 ffmpeg/ffprobe，下载解压即用。全功能版捆绑的是 GPL 构建
（含 x264/x265 等，为后续视频转码准备）；macOS 全功能版为 Intel 二进制，
Apple Silicon 需 Rosetta 2。