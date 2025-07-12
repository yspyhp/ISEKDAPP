#!/bin/bash

# 停止所有 ISEK DAPP 服务

echo "🛑 停止所有 ISEK DAPP 服务..."

# 停止 Python 进程
echo "停止 Python 进程..."
pkill -f "python.*app.py" || true
pkill -f "python.*mock_isek_node.py" || true

# 停止 Node.js 进程
echo "停止 Node.js 进程..."
pkill -f "next" || true
pkill -f "electron" || true

# 停止特定端口的进程
echo "停止端口进程..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:5001 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

sleep 2

echo "✅ 所有服务已停止"

# 检查是否还有进程在运行
echo "检查剩余进程..."
ps aux | grep -E "(python|next|electron)" | grep -v grep || echo "没有发现相关进程"
