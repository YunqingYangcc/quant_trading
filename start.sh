#!/bin/bash
# 一键启动 TrackQuant 服务
# 用法: bash start.sh

echo "🚀 启动 TrackQuant..."
BASEDIR="$(cd "$(dirname "$0")" && pwd)"

# 启动后端
echo "📦 启动后端..."
cd "$BASEDIR/backend"
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

# 启动前端
echo "🎨 启动前端..."
cd "$BASEDIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ 后端 → http://localhost:8000  (PID: $BACKEND_PID)"
echo "✅ 前端 → http://localhost:5173  (PID: $FRONTEND_PID)"
echo ""
echo "按 Ctrl+C 停止所有服务"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
