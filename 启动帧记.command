#!/bin/bash
set -e
cd "$(dirname "$0")"
BUNDLED="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies"
if command -v node >/dev/null 2>&1; then NODE_BIN="$(command -v node)"; else NODE_BIN="$BUNDLED/node/bin/node"; fi
if [ -x "$BUNDLED/python/bin/python3" ]; then PYTHON_BIN="$BUNDLED/python/bin/python3"; else PYTHON_BIN="$(command -v python3 || true)"; fi
if [ ! -x "$NODE_BIN" ] || [ ! -x "$PYTHON_BIN" ]; then echo '请安装 Node.js 20+ 和 Python 3.10+ 后重试。'; read -r; exit 1; fi
mkdir -p .runtime/python-libs
export PYTHONPATH="$PWD/.runtime/python-libs${PYTHONPATH:+:$PYTHONPATH}"
if ! "$PYTHON_BIN" -c "import faster_whisper, yt_dlp, youtube_transcript_api, av; assert av.__version__ == '16.1.0'" >/dev/null 2>&1; then
 echo '首次运行：正在安装本地语音识别依赖…'
 "$PYTHON_BIN" -m pip install --upgrade --target .runtime/python-libs -r requirements.txt
fi
export FRAME_PYTHON="$PYTHON_BIN"
export PORT="${PORT:-8789}"
echo "启动后，请在浏览器打开 http://127.0.0.1:$PORT"
"$NODE_BIN" scripts/dev.mjs
