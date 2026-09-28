#!/usr/bin/env bash
# 本地开发一键启动：后端 API + Worker（改代码自动重启）+ 前端 Vite，按 Ctrl+C 同时停止。
#
# 用法：
#   scripts/dev.sh          只允许本机访问
#   scripts/dev.sh --lan    同一局域网的设备（如 iPad）也能访问前端
#
# 环境变量：
#   BACKEND_PORT   后端端口，默认 8000；被占用时自动往后找空闲端口，前端代理会跟着切换
#   FRONTEND_PORT  前端端口，默认 5173
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LAN=false
for arg in "$@"; do
  case "$arg" in
    --lan) LAN=true ;;
    -h | --help)
      sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "未知参数：$arg（用 --help 查看用法）" >&2
      exit 1
      ;;
  esac
done

need() {
  command -v "$1" >/dev/null || {
    echo "缺少命令 $1：$2" >&2
    exit 1
  }
}
need uv "安装方法见 https://docs.astral.sh/uv/"
need npm "请先安装 Node.js"

port_in_use() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

BACKEND_PORT="${BACKEND_PORT:-8000}"
while port_in_use "$BACKEND_PORT"; do
  echo "端口 $BACKEND_PORT 已被占用，后端改用 $((BACKEND_PORT + 1))"
  BACKEND_PORT=$((BACKEND_PORT + 1))
done

FRONTEND_PORT="${FRONTEND_PORT:-5173}"
if port_in_use "$FRONTEND_PORT"; then
  echo "前端端口 $FRONTEND_PORT 已被占用（可能已有一个开发服务器在运行），可用 FRONTEND_PORT=5174 换一个" >&2
  exit 1
fi

# ---- 准备环境 ----
if [[ ! -f backend/.env ]]; then
  cp backend/.env.example backend/.env
  echo "已从 backend/.env.example 创建 backend/.env（管理员账号密码在里面）"
fi
echo "检查后端依赖…"
(cd backend && uv sync --quiet)
if [[ package-lock.json -nt node_modules/.package-lock.json ]]; then
  echo "安装前端依赖…"
  npm install --no-fund --no-audit
fi

# ---- 启动 ----
pids=()
cleanup() {
  trap - INT TERM EXIT
  echo
  echo "正在停止…"
  kill "${pids[@]}" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap 'cleanup; exit 130' INT TERM
trap cleanup EXIT

# 给每行输出加上来源标记，方便区分前后端日志
prefix() { while IFS= read -r line; do printf '%s %s\n' "$1" "$line"; done; }

(cd backend && exec .venv/bin/uvicorn --factory app.main:create_app \
  --host 127.0.0.1 --port "$BACKEND_PORT" --reload --reload-dir app) \
  > >(prefix "[api]") 2>&1 &
pids+=($!)

# Worker：执行 PDF 拆页等后台任务；app/ 下的代码变化时自动重启
(cd backend && exec .venv/bin/watchfiles --filter python ".venv/bin/python -m app.worker" app) \
  > >(prefix "[worker]") 2>&1 &
pids+=($!)

vite_args=(--port "$FRONTEND_PORT" --strictPort)
$LAN && vite_args+=(--host)
API_PROXY_TARGET="http://127.0.0.1:$BACKEND_PORT" ./node_modules/.bin/vite "${vite_args[@]}" \
  > >(prefix "[web]") 2>&1 &
pids+=($!)

# 等后端就绪（启动时会执行数据库迁移）
for _ in $(seq 60); do
  port_in_use "$BACKEND_PORT" && break
  sleep 0.5
done

cat <<INFO

  dance-page 开发环境已启动
    前端      http://localhost:$FRONTEND_PORT
    接口文档  http://127.0.0.1:$BACKEND_PORT/api/docs
    管理员    账号密码见 backend/.env
  按 Ctrl+C 停止

INFO
if $LAN; then
  echo "  局域网设备请使用上方 [web] 日志中 Network 一行的地址"
  echo
fi

# 任意一个进程退出（如启动失败），就停止其他进程。
# 不用 `wait -n`：macOS 自带的 bash 3.2 不支持，而且进程在执行到 wait 之前就退出时它也察觉不到
while :; do
  for pid in "${pids[@]}"; do
    kill -0 "$pid" 2>/dev/null || exit 1
  done
  sleep 1
done
