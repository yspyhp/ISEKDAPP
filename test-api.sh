#!/bin/bash

# API 测试脚本
# 用于验证 ISEK DAPP 的各个 API 端点

set -e

echo "🧪 ISEK DAPP API 测试"
echo "================================"

# 等待服务启动
sleep 2

# 测试函数
test_endpoint() {
    local url=$1
    local name=$2
    local method=${3:-GET}
    local data=${4:-""}
    
    echo "测试: $name"
    echo "URL: $url"
    
    if [ "$method" = "POST" ] && [ -n "$data" ]; then
        response=$(curl -s -X POST -H "Content-Type: application/json" -d "$data" "$url" 2>/dev/null || echo "ERROR")
    else
        response=$(curl -s "$url" 2>/dev/null || echo "ERROR")
    fi
    
    if [ "$response" = "ERROR" ]; then
        echo "❌ 失败"
        return 1
    else
        echo "✅ 成功"
        echo "响应: $response" | head -c 100
        echo "..."
        return 0
    fi
}

# 测试健康检查
echo "1. 健康检查"
test_endpoint "http://localhost:8000/health" "Mock ISEK 节点健康检查"
test_endpoint "http://localhost:5001/health" "Python 后端健康检查"
test_endpoint "http://localhost:3000" "Next.js 前端健康检查"

echo ""
echo "2. 代理 API"
test_endpoint "http://localhost:8000/agents" "Mock 节点代理列表"
test_endpoint "http://localhost:5001/api/agents" "后端代理列表"
test_endpoint "http://localhost:3000/api/agents" "前端代理代理"

echo ""
echo "3. 会话 API"
test_endpoint "http://localhost:5001/api/sessions" "后端会话列表"
test_endpoint "http://localhost:3000/api/sessions" "前端会话代理"

# 创建测试会话
echo ""
echo "4. 创建测试会话"
session_data='{"agentId": "isek-assistant-001", "title": "API Test Session"}'
test_endpoint "http://localhost:5001/api/sessions" "创建会话 (后端)" "POST" "$session_data"
test_endpoint "http://localhost:3000/api/sessions" "创建会话 (前端)" "POST" "$session_data"

# 获取会话列表
echo ""
echo "5. 获取会话列表"
sessions=$(curl -s http://localhost:3000/api/sessions)
echo "会话列表: $sessions"

# 如果有会话，测试聊天功能
if echo "$sessions" | grep -q "id"; then
    session_id=$(echo "$sessions" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    echo ""
    echo "6. 测试聊天功能 (会话ID: $session_id)"
    
    chat_data="{\"agentId\": \"isek-assistant-001\", \"sessionId\": \"$session_id\", \"messages\": [{\"role\": \"user\", \"content\": \"Hello, this is a test message\"}]}"
    test_endpoint "http://localhost:3000/api/chat" "发送聊天消息" "POST" "$chat_data"
    
    # 获取消息历史
    test_endpoint "http://localhost:3000/api/chat?sessionId=$session_id" "获取消息历史"
fi

echo ""
echo "🎉 API 测试完成！"
