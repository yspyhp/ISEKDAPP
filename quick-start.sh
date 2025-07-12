#!/bin/bash

# 快速启动脚本 - ISEK DAPP
echo "🚀 ISEK DAPP 快速启动"

# 停止现有进程
echo "停止现有进程..."
pkill -f "python.*app.py" || true
pkill -f "python.*mock_isek_node.py" || true
pkill -f "next" || true
pkill -f "electron" || true
sleep 2

# 检查端口
echo "检查端口..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:5001 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true
sleep 1

# 启动 Mock 节点
echo "启动 Mock ISEK 节点..."
cd pybackend
python3 mock_isek_node.py &
MOCK_PID=$!
cd ..
sleep 3

# 启动 Python 后端
echo "启动 Python 后端..."
cd pybackend
python3 app.py &
BACKEND_PID=$!
cd ..
sleep 5

# 启动前端
echo "启动 Next.js 前端..."
cd electron
npm run dev:frontend &
FRONTEND_PID=$!
cd ..
sleep 8

# 启动 Electron
echo "启动 Electron 应用..."
cd electron
npm run dev:electron &
ELECTRON_PID=$!
cd ..
sleep 3

# 健康检查
echo "健康检查..."
sleep 5

if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ Mock 节点正常"
else
    echo "❌ Mock 节点异常"
fi

if curl -s http://localhost:5001/health > /dev/null; then
    echo "✅ Python 后端正常"
else
    echo "❌ Python 后端异常"
fi

if curl -s http://localhost:3000 > /dev/null; then
    echo "✅ Next.js 前端正常"
else
    echo "❌ Next.js 前端异常"
fi

echo "🎉 启动完成！"
echo "服务地址:"
echo "  Mock 节点: http://localhost:8000"
echo "  Python 后端: http://localhost:5001"
echo "  Next.js 前端: http://localhost:3000"
echo ""
echo "进程 ID:"
echo "  Mock 节点: $MOCK_PID"
echo "  Python 后端: $BACKEND_PID"
echo "  Next.js 前端: $FRONTEND_PID"
echo "  Electron: $ELECTRON_PID"
echo ""
echo "停止所有服务: pkill -f 'python\|next\|electron'"
