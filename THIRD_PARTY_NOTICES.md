# 第三方组件声明

## FFmpeg（LGPL）

本程序捆绑并调用 FFmpeg（ffmpeg.exe / ffprobe.exe 及共享库 DLL），用于音频探测与转换。

- 许可证：GNU Lesser General Public License v2.1（部分组件为 LGPL v3 / 其他宽松许可证）。
  完整许可文本见随包分发的 `ffmpeg/LICENSE.txt`。
- 构建来源：本组织自有仓库 **Aer-Light-Work/ffmpeg-build-flow** 的滚动 LGPL 构建
  （https://github.com/Aer-Light-Work/ffmpeg-build-flow/releases/tag/latest），
  Windows 取 `ffmpeg-win64-lgpl-shared`，Linux / macOS 取对应平台的静态 LGPL 包；
  配置不含 `--enable-gpl` / `--enable-nonfree`（未启用 x264/x265 等 GPL 组件；
  libmp3lame 本身为 LGPL 许可）。
- 对应源码：https://git.ffmpeg.org/ffmpeg.git （构建版本 n7.1，
  精确 commit 与完整 configure 参数见包内 `README-build.txt` 或 `ffmpeg -version` 输出）；
  构建脚本见上述仓库。
- LGPL 合规：FFmpeg 以独立子进程被调用，与本程序为独立作品；Windows 包以**共享库（DLL）**
  形式分发 FFmpeg，用户可自行替换兼容版本的 DLL 实现再链接。
  本程序自身亦以 LGPL-2.1 分发（见 LICENSE）。

## Python / PyInstaller

打包产物包含 Python 运行时（PSF 许可）与 PyInstaller 引导代码（GPL 兼容的
特殊例外许可，允许以任意许可分发打包产物）。tkinter 基于 Tcl/Tk（BSD 风格许可）。