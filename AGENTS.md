# 项目协作约定

- 推送到远程前：默认运行 L2 轻量安全审查（qodersec review --layer=l2），
  无需每次询问 L3；发现安全问题时先呈现问题再决定修复与推送。
- 网络环境：访问 GitHub 需走本地代理 socks5h://127.0.0.1:10808
  （git 用 `-c http.proxy=...`，gh 用 `HTTPS_PROXY=socks5://127.0.0.1:10808`）。
- Python 环境：统一使用 uv（`uv sync` / `uv run`），不向全局 Python 安装依赖。
- ffmpeg 捆绑：必须使用 LGPL 构建（build.py 的 verify_lgpl 强制校验）；
  全功能版（build-bundled.yml）例外，捆绑 GPL 构建并跳过该校验。