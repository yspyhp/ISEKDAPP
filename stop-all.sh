#!/bin/bash

# 停止所有 ISEK DAPP 服务（Client前端、Client后端、Server）

echo "🛑 停止所有 ISEK DAPP 服务..."

# 停止 Client 后端 (client_backend)
echo "停止 Client 后端 (client_backend)..."
pkill -f "python.*client_backend.*app.py" || true
pkill -f "python3.*client_backend.*app.py" || true
pkill -f "python.*client_backend.*app_fastapi.py" || true
pkill -f "python3.*client_backend.*app_fastapi.py" || true

# 停止 Agent Server
echo "停止 Agent Server..."
pkill -f "python.*agent_server.*app.py" || true
pkill -f "python3.*agent_server.*app.py" || true

# 停止所有 Python app.py 进程（兜底）
echo "停止其他 Python 进程..."
pkill -f "python.*app.py" || true
pkill -f "python3.*app.py" || true

# 停止 Client 前端 (Next.js)
echo "停止 Client 前端 (Next.js)..."
pkill -f "next" || true
pkill -f "next-dev" || true
pkill -f "next start" || true

# 停止 Electron
echo "停止 Electron..."
pkill -f "electron" || true

# 停止特定端口的进程
echo "停止端口进程..."
# Client 后端端口
lsof -ti:5001 | xargs kill -9 2>/dev/null || true
lsof -ti:5000 | xargs kill -9 2>/dev/null || true

# Agent Server 端口
lsof -ti:8888 | xargs kill -9 2>/dev/null || true

# Client 前端端口
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

# ETCD 端口（如果本地运行）
lsof -ti:2379 | xargs kill -9 2>/dev/null || true

sleep 3

# 清理临时文件和缓存
echo "清理临时文件..."

# 清理 Python 缓存
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -type f -delete 2>/dev/null || true

# 清理 Node.js 缓存
if [ -d "electron/.next" ]; then
    rm -rf electron/.next
    echo "删除 .next 缓存"
fi

# 清理日志文件
find . -name "*.log" -type f -delete 2>/dev/null || true

# 清理进程 ID 文件
find . -name "*.pid" -type f -delete 2>/dev/null || true

echo "✅ 所有服务已停止，临时文件已清理"

# 检查是否还有进程在运行
echo "检查剩余进程..."
echo "Python 进程:"
ps aux | grep -E "python.*app\.py" | grep -v grep || echo "  没有发现 Python 进程"

echo "Node.js 进程:"
ps aux | grep -E "(next|electron)" | grep -v grep || echo "  没有发现 Node.js 进程"

echo "端口占用:"
echo "  5001: $(lsof -ti:5001 2>/dev/null || echo '空闲')"
echo "  5000: $(lsof -ti:5000 2>/dev/null || echo '空闲')"  
echo "  8888: $(lsof -ti:8888 2>/dev/null || echo '空闲')"
echo "  3000: $(lsof -ti:3000 2>/dev/null || echo '空闲')"
