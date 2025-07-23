#!/bin/bash

# 快速启动脚本 - ISEK DAPP (Client前端、Client后端、Agent Server)
echo "🚀 ISEK DAPP 快速启动"

# 参数解析
AGENT_MODE=1
SKIP_CLIENT=false
SKIP_SERVER=false
FORCE_ELECTRON=false
CLEAN_BUILD=true
USE_PROXY=false

# 显示帮助信息
show_help() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --lyra              使用 Lyra Agent 模式 (默认: 默认 Agent)"
    echo "  --client-only       只启动 Client (前端+后端)"
    echo "  --server-only       只启动 Agent Server"
    echo "  --electron          强制启动 Electron 应用"
    echo "  --no-clean          跳过清理和构建步骤"
    echo "  --proxy             使用代理运行 Agent Server"
    echo "  --help              显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                  # 启动所有服务(默认Agent)"
    echo "  $0 --lyra           # 启动所有服务(Lyra Agent)"
    echo "  $0 --client-only    # 只启动Client"
    echo "  $0 --server-only    # 只启动Agent Server"
    echo "  $0 --electron       # 启动并打开Electron"
    echo "  $0 --no-clean       # 跳过清理构建"
    echo "  $0 --proxy          # 使用代理运行Agent Server"
    exit 0
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --lyra)
            AGENT_MODE=2
            shift
            ;;
        --client-only)
            SKIP_SERVER=true
            shift
            ;;
        --server-only)
            SKIP_CLIENT=true
            shift
            ;;
        --electron)
            FORCE_ELECTRON=true
            shift
            ;;
        --no-clean)
            CLEAN_BUILD=false
            shift
            ;;
        --proxy)
            USE_PROXY=true
            shift
            ;;
        --help)
            show_help
            ;;
        *)
            echo "未知参数: $1"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
done

# 如果没有参数，交互式选择模式
if [ "$AGENT_MODE" = "1" ] && [ "$SKIP_CLIENT" = "false" ] && [ "$SKIP_SERVER" = "false" ] && [ "$FORCE_ELECTRON" = "false" ]; then
    echo ""
    echo "请选择启动模式:"
    echo "1) 默认 Agent Server (Session Management)"
    echo "2) Lyra Agent (AI Prompt Optimizer)"
    echo ""
    read -p "选择模式 (1/2) [默认: 1]: " -n 1 -r
    echo ""
    AGENT_MODE=${REPLY:-1}
fi

# 检查 Lyra 模式的环境变量
if [ "$AGENT_MODE" = "2" ] && [ "$SKIP_SERVER" = "false" ]; then
    if [ ! -f ".env" ]; then
        echo "⚠️  警告: 启动 Lyra Agent 需要 .env 文件"
        echo "请基于 env.example 创建 .env 文件并配置 OpenAI API Key"
        echo ""
        read -p "是否继续启动？ (y/n): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "启动已取消"
            exit 1
        fi
    fi
fi

# 清理和构建
if [ "$CLEAN_BUILD" = "true" ]; then
    echo ""
    echo "🧹 清理和构建..."
    
    # 停止所有相关进程
    echo "停止现有进程..."
    pkill -f "app.py" 2>/dev/null || true
    pkill -f "app_fastapi.py" 2>/dev/null || true
    pkill -f "Lyra_gent.py" 2>/dev/null || true
    pkill -f "next-server" 2>/dev/null || true
    pkill -f "electron" 2>/dev/null || true
    sleep 2
    
    # 清理Python缓存
    echo "清理Python缓存..."
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    
    # 清理前端缓存和构建
    if [ "$SKIP_CLIENT" = "false" ]; then
        echo "清理前端缓存..."
        cd agent_client/client_ui
        rm -rf .next 2>/dev/null || true
        rm -rf node_modules/.cache 2>/dev/null || true
        npm run build > /dev/null 2>&1 || echo "前端构建跳过"
        cd ../..
    fi
    
    # 清理日志文件
    echo "清理日志文件..."
    rm -rf logs/*.log 2>/dev/null || true
    mkdir -p logs
    
    echo "✅ 清理完成"
fi

# 如果未启用清理，仍需要停止现有进程并清理端口
if [ "$CLEAN_BUILD" = "false" ]; then
    echo "停止现有进程..."
    ./stop-all.sh
    sleep 2

    # 清理端口（确保端口可用）
    echo "检查并清理端口..."
    lsof -ti:5001 | xargs kill -9 2>/dev/null || true  # Client 后端
    lsof -ti:5000 | xargs kill -9 2>/dev/null || true  # Client 后端备用
    lsof -ti:8888 | xargs kill -9 2>/dev/null || true  # Agent Server (默认)
    lsof -ti:8889 | xargs kill -9 2>/dev/null || true  # Agent Server (Lyra)
    lsof -ti:9000 | xargs kill -9 2>/dev/null || true  # P2P (默认)
    lsof -ti:9001 | xargs kill -9 2>/dev/null || true  # P2P (Client)
    lsof -ti:9002 | xargs kill -9 2>/dev/null || true  # P2P (Lyra)
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true  # Client 前端
    sleep 2
fi

# 创建日志目录
mkdir -p logs

# 启动 Agent Server
if [ "$SKIP_SERVER" = "false" ]; then
    # 设置代理环境变量
    if [ "$USE_PROXY" = "true" ]; then
        echo "🌐 使用代理启动 Agent Server (http://127.0.0.1:1087)..."
        export http_proxy=http://127.0.0.1:1087
        export https_proxy=http://127.0.0.1:1087
    fi
    
    if [ "$AGENT_MODE" = "2" ]; then
        if [ "$USE_PROXY" = "true" ]; then
            echo "🎯 启动 Lyra Agent Server (端口: 8889) [使用代理]..."
        else
            echo "🎯 启动 Lyra Agent Server (端口: 8889)..."
        fi
        cd agent_server
        /Users/sparkss/.pyenv/versions/3.10.10/bin/python3 app/lyra/Lyra_gent.py > ../logs/agent_server.log 2>&1 &
        SERVER_PID=$!
        cd ..
        echo "Lyra Agent Server PID: $SERVER_PID"
    else
        if [ "$USE_PROXY" = "true" ]; then
            echo "🔧 启动默认 Agent Server (端口: 8888) [使用代理]..."
        else
            echo "🔧 启动默认 Agent Server (端口: 8888)..."
        fi
        cd agent_server
        /Users/sparkss/.pyenv/versions/3.10.10/bin/python3 app.py > ../logs/agent_server.log 2>&1 &
        SERVER_PID=$!
        cd ..
        echo "Agent Server PID: $SERVER_PID"
    fi
    
    # 清除代理环境变量，避免影响其他服务
    if [ "$USE_PROXY" = "true" ]; then
        unset http_proxy
        unset https_proxy
    fi
    
    sleep 5
fi

# 启动 Client 后端 (FastAPI)
if [ "$SKIP_CLIENT" = "false" ]; then
    echo "🐍 启动 Client 后端 FastAPI (端口: 5001)..."
    cd agent_client/client_backend
    /Users/sparkss/.pyenv/versions/3.10.10/bin/python3 app_fastapi.py > ../../logs/client_backend.log 2>&1 &
    CLIENT_BACKEND_PID=$!
    cd ../..
    echo "Client 后端 PID: $CLIENT_BACKEND_PID"
    sleep 5
fi

# 启动 Client 前端
if [ "$SKIP_CLIENT" = "false" ]; then
    echo "⚡ 启动 Client 前端 (端口: 3000)..."
    cd agent_client/client_ui
    npm run dev:frontend > ../../logs/client_frontend.log 2>&1 &
    CLIENT_FRONTEND_PID=$!
    cd ../..
    echo "Client 前端 PID: $CLIENT_FRONTEND_PID"
    sleep 8

    # Electron 启动逻辑
    if [ "$FORCE_ELECTRON" = "true" ]; then
        echo "🖥️  启动 Electron 应用..."
        cd agent_client/client_ui
        npm run dev:electron > ../../logs/electron.log 2>&1 &
        ELECTRON_PID=$!
        cd ../..
        echo "Electron PID: $ELECTRON_PID"
        sleep 3
    else
        echo ""
        echo "🌐 应用将在网页中打开 (http://localhost:3000)"
        echo "💡 使用 --electron 参数可直接启动桌面应用"
    fi
fi

# 健康检查
echo ""
echo "🔍 健康检查..."
sleep 3

# 检查 Agent Server
if [ "$SKIP_SERVER" = "false" ]; then
    echo "检查 Agent Server..."
    if [ "$AGENT_MODE" = "2" ]; then
        # Lyra Agent uses port 8889 - use lsof for reliable port checking
        if lsof -i :8889 > /dev/null 2>&1; then
            echo "✅ Lyra Agent Server (端口 8889) 正常启动"
        else
            echo "❌ Lyra Agent Server (端口 8889) 启动失败"
            echo "查看日志: tail -f logs/agent_server.log"
        fi
    else
        # Default Agent uses port 8888 - use lsof for reliable port checking
        if lsof -i :8888 > /dev/null 2>&1; then
            echo "✅ Agent Server (端口 8888) 正常启动"
        else
            echo "❌ Agent Server (端口 8888) 启动失败"
            echo "查看日志: tail -f logs/agent_server.log"
        fi
    fi
fi

# 检查 Client 后端
if [ "$SKIP_CLIENT" = "false" ]; then
    echo "检查 Client 后端..."
    if curl -s http://localhost:5001/health > /dev/null 2>&1; then
        echo "✅ Client 后端 (端口 5001) 正常运行"
    elif lsof -i :5001 > /dev/null 2>&1; then
        echo "⚠️  Client 后端 (端口 5001) 启动但健康检查失败"
    else
        echo "❌ Client 后端 (端口 5001) 启动失败"
        echo "查看日志: tail -f logs/client_backend.log"
    fi

    # 检查 Client 前端
    echo "检查 Client 前端..."
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        echo "✅ Client 前端 (端口 3000) 正常运行"
    elif lsof -i :3000 > /dev/null 2>&1; then
        echo "⚠️  Client 前端 (端口 3000) 启动但响应异常"
    else
        echo "❌ Client 前端 (端口 3000) 启动失败"
        echo "查看日志: tail -f logs/client_frontend.log"
    fi
fi

echo ""
echo "🎉 启动完成！"
echo ""

# 显示启动模式
if [ "$SKIP_CLIENT" = "true" ]; then
    echo "🖥️  启动模式: 仅 Agent Server"
elif [ "$SKIP_SERVER" = "true" ]; then
    echo "🌐 启动模式: 仅 Client"
else
    echo "🚀 启动模式: 完整服务"
fi

if [ "$SKIP_SERVER" = "false" ]; then
    if [ "$AGENT_MODE" = "2" ]; then
        echo "🎯 Agent模式: Lyra Agent (AI Prompt Optimizer)"
    else
        echo "🔧 Agent模式: 默认 Agent Server (Session Management)"
    fi
fi

echo ""
echo "📍 服务地址:"

if [ "$SKIP_SERVER" = "false" ]; then
    if [ "$AGENT_MODE" = "2" ]; then
        echo "  🎯 Lyra Agent:      http://localhost:8889"
    else
        echo "  🔧 Agent Server:    http://localhost:8888"
    fi
fi

if [ "$SKIP_CLIENT" = "false" ]; then
    echo "  🐍 Client 后端:     http://localhost:5001"
    echo "  ⚡ Client 前端:     http://localhost:3000"
fi

echo ""
echo "📄 日志文件:"
if [ "$SKIP_SERVER" = "false" ]; then
    echo "  Agent Server:      logs/agent_server.log"
fi
if [ "$SKIP_CLIENT" = "false" ]; then
    echo "  Client 后端:       logs/client_backend.log"
    echo "  Client 前端:       logs/client_frontend.log"
fi
if [ "$FORCE_ELECTRON" = "true" ] && [ ! -z "$ELECTRON_PID" ]; then
    echo "  Electron:          logs/electron.log"
fi

echo ""
echo "🛑 停止所有服务:     ./stop-all.sh"
echo "📊 查看实时日志:     tail -f logs/*.log"

if [ "$SKIP_CLIENT" = "false" ]; then
    echo ""
    echo "🌐 在浏览器中打开:   http://localhost:3000"

    # 保存进程 ID 到文件
    if [ ! -z "$CLIENT_BACKEND_PID" ]; then
        echo "$CLIENT_BACKEND_PID" > logs/client_backend.pid
    fi
    if [ ! -z "$CLIENT_FRONTEND_PID" ]; then
        echo "$CLIENT_FRONTEND_PID" > logs/client_frontend.pid
    fi
fi

if [ "$SKIP_SERVER" = "false" ] && [ ! -z "$SERVER_PID" ]; then
    echo "$SERVER_PID" > logs/agent_server.pid
fi

if [ "$FORCE_ELECTRON" = "true" ] && [ ! -z "$ELECTRON_PID" ]; then
    echo "$ELECTRON_PID" > logs/electron.pid
fi

# 自动打开浏览器（仅在客户端模式下且非强制Electron时）
if [ "$SKIP_CLIENT" = "false" ] && [ "$FORCE_ELECTRON" = "false" ]; then
    sleep 2
    if command -v open > /dev/null; then
        open http://localhost:3000  # macOS
    elif command -v xdg-open > /dev/null; then
        xdg-open http://localhost:3000  # Linux
    fi
fi