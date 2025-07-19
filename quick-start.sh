#!/bin/bash

# 快速启动脚本 - ISEK DAPP (Client前端、Client后端、Agent Server)
echo "🚀 ISEK DAPP 快速启动"

# 停止现有进程
echo "停止现有进程..."
./stop-all.sh
sleep 2

# 清理端口（确保端口可用）
echo "检查并清理端口..."
lsof -ti:5001 | xargs kill -9 2>/dev/null || true  # Client 后端
lsof -ti:5000 | xargs kill -9 2>/dev/null || true  # Client 后端备用
lsof -ti:8888 | xargs kill -9 2>/dev/null || true  # Agent Server
lsof -ti:3000 | xargs kill -9 2>/dev/null || true  # Client 前端
sleep 2

# 创建日志目录
mkdir -p logs

# 启动 Agent Server
echo "🔧 启动 Agent Server (端口: 8888)..."
cd agent_server
python3 app.py > ../logs/agent_server.log 2>&1 &
SERVER_PID=$!
cd ..
echo "Agent Server PID: $SERVER_PID"
sleep 5

# 启动 Client 后端 (FastAPI)
echo "🐍 启动 Client 后端 FastAPI (端口: 5001)..."
cd agent_client/client_backend
python3 app_fastapi.py > ../../logs/client_backend.log 2>&1 &
CLIENT_BACKEND_PID=$!
cd ../..
echo "Client 后端 PID: $CLIENT_BACKEND_PID"
sleep 5

# 启动 Client 前端
echo "⚡ 启动 Client 前端 (端口: 3000)..."
cd agent_client/client_ui
npm run dev:frontend > ../../logs/client_frontend.log 2>&1 &
CLIENT_FRONTEND_PID=$!
cd ../..
echo "Client 前端 PID: $CLIENT_FRONTEND_PID"
sleep 8

# 启动 Electron（可选）
read -p "是否启动 Electron 桌面应用？ (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🖥️  启动 Electron 应用..."
    cd agent_client/client_ui
    npm run dev:electron > ../../logs/electron.log 2>&1 &
    ELECTRON_PID=$!
    cd ../..
    echo "Electron PID: $ELECTRON_PID"
    sleep 3
fi

# 健康检查
echo "🔍 健康检查..."
sleep 3

# 检查 Agent Server
echo "检查 Agent Server..."
if netstat -an | grep -q ":8888.*LISTEN"; then
    echo "✅ Agent Server (端口 8888) 正常启动"
else
    echo "❌ Agent Server (端口 8888) 启动失败"
    echo "查看日志: tail -f logs/agent_server.log"
fi

# 检查 Client 后端
echo "检查 Client 后端..."
if curl -s http://localhost:5001/health > /dev/null 2>&1; then
    echo "✅ Client 后端 (端口 5001) 正常运行"
elif netstat -an | grep -q ":5001.*LISTEN"; then
    echo "⚠️  Client 后端 (端口 5001) 启动但健康检查失败"
else
    echo "❌ Client 后端 (端口 5001) 启动失败"
    echo "查看日志: tail -f logs/client_backend.log"
fi

# 检查 Client 前端
echo "检查 Client 前端..."
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ Client 前端 (端口 3000) 正常运行"
elif netstat -an | grep -q ":3000.*LISTEN"; then
    echo "⚠️  Client 前端 (端口 3000) 启动但响应异常"
else
    echo "❌ Client 前端 (端口 3000) 启动失败"
    echo "查看日志: tail -f logs/client_frontend.log"
fi

echo ""
echo "🎉 启动完成！"
echo ""
echo "📍 服务地址:"
echo "  🔧 Agent Server:    http://localhost:8888"
echo "  🐍 Client 后端:     http://localhost:5001"
echo "  ⚡ Client 前端:     http://localhost:3000"
echo ""
echo "📋 进程 ID:"
echo "  Agent Server:      $SERVER_PID"
echo "  Client 后端:       $CLIENT_BACKEND_PID"
echo "  Client 前端:       $CLIENT_FRONTEND_PID"
if [ ! -z "$ELECTRON_PID" ]; then
    echo "  Electron:          $ELECTRON_PID"
fi
echo ""
echo "📄 日志文件:"
echo "  Agent Server:      logs/agent_server.log"
echo "  Client 后端:       logs/client_backend.log"
echo "  Client 前端:       logs/client_frontend.log"
if [ ! -z "$ELECTRON_PID" ]; then
    echo "  Electron:          logs/electron.log"
fi
echo ""
echo "🛑 停止所有服务:     ./stop-all.sh"
echo "📊 查看实时日志:     tail -f logs/*.log"
echo ""
echo "🌐 在浏览器中打开:   http://localhost:3000"

# 保存进程 ID 到文件
echo $SERVER_PID > logs/agent_server.pid
echo $CLIENT_BACKEND_PID > logs/client_backend.pid  
echo $CLIENT_FRONTEND_PID > logs/client_frontend.pid
if [ ! -z "$ELECTRON_PID" ]; then
    echo $ELECTRON_PID > logs/electron.pid
fi

# 自动打开浏览器（可选）
sleep 2
read -p "是否在浏览器中打开应用？ (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if command -v open > /dev/null; then
        open http://localhost:3000  # macOS
    elif command -v xdg-open > /dev/null; then
        xdg-open http://localhost:3000  # Linux
    else
        echo "请手动打开: http://localhost:3000"
    fi
fi
