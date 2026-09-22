#!/usr/bin/env bash
# 本地开发启动脚本：先杀掉占用端口的旧进程，再用 fastapi dev 启动。
# 用法：
#   ./scripts/dev.sh          # 默认端口 8000
#   ./scripts/dev.sh 9000     # 指定端口
set -euo pipefail

PORT="${1:-8000}"

# 切到项目根目录（脚本所在目录的上一级），保证相对路径正确
cd "$(dirname "$0")/.."

# 找到监听该端口的进程并杀掉；没有则跳过
pids="$(lsof -ti tcp:"$PORT" -sTCP:LISTEN || true)"
if [ -n "$pids" ]; then
    echo "端口 $PORT 被占用，杀掉进程：$pids"
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 1
    # 仍未退出则强杀
    pids="$(lsof -ti tcp:"$PORT" -sTCP:LISTEN || true)"
    if [ -n "$pids" ]; then
        # shellcheck disable=SC2086
        kill -9 $pids 2>/dev/null || true
    fi
fi

echo "启动 fastapi dev（端口 $PORT）..."
exec uv run fastapi dev src/main.py --port "$PORT"
