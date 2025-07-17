#!/usr/bin/env python3
"""
ISEK UI Python Backend
ISEK Node Client - Connect to local ISEK node
"""

import os
import requests
import uuid
from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

ISEK_NODE_URL = os.getenv('ISEK_NODE_URL', 'http://localhost:8000')

# 内存存储 (生产环境应该用数据库)
sessions_db = []
messages_db = []

@app.route('/api/agents', methods=['GET'])
def get_agents():
    try:
        resp = requests.get(f"{ISEK_NODE_URL}/agents", timeout=3)
        resp.raise_for_status()
        agents = resp.json()
        return jsonify(agents)
    except Exception as e:
        print(f"Failed to get agents: {e}")
        return jsonify([]), 500

@app.route('/api/agents/<agent_id>', methods=['GET'])
def get_agent(agent_id):
    try:
        resp = requests.get(f"{ISEK_NODE_URL}/agents/{agent_id}", timeout=3)
        resp.raise_for_status()
        agent = resp.json()
        return jsonify(agent)
    except Exception as e:
        print(f"Failed to get agent: {e}")
        return jsonify({"error": "Agent not found"}), 404

@app.route('/api/network/status', methods=['GET'])
def get_network_status():
    try:
        resp = requests.get(f"{ISEK_NODE_URL}/network/status", timeout=3)
        resp.raise_for_status()
        status = resp.json()
        return jsonify(status)
    except Exception as e:
        print(f"Failed to get network status: {e}")
        return jsonify({"error": "Failed to get network status"}), 500

@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """Get all chat sessions"""
    sessions_with_count = []
    for session in sessions_db:
        message_count = len([m for m in messages_db if m["sessionId"] == session["id"]])
        session_copy = session.copy()
        session_copy["messageCount"] = message_count
        sessions_with_count.append(session_copy)
    return jsonify(sessions_with_count)

@app.route('/api/sessions', methods=['POST'])
def create_session():
    """Create new chat session"""
    data = request.get_json()
    agent_id = data.get('agentId')
    title = data.get('title')
    
    if not agent_id:
        return jsonify({"error": "agentId is required"}), 400
    
    # Get agent information from node
    try:
        resp = requests.get(f"{ISEK_NODE_URL}/agents/{agent_id}", timeout=3)
        resp.raise_for_status()
        agent = resp.json()
    except Exception as e:
        print(f"Failed to get agent info: {e}")
        return jsonify({"error": "Agent not found"}), 404
    
    session = {
        "id": str(uuid.uuid4()),
        "title": title or f"Chat with {agent['name']}",
        "agentId": agent_id,
        "agentName": agent['name'],
        "agentDescription": agent['description'],
        "agentAddress": agent['address'],
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat(),
        "messageCount": 0
    }
    sessions_db.append(session)
    return jsonify(session), 201

@app.route('/api/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete chat session"""
    global sessions_db, messages_db
    # Delete session
    sessions_db = [s for s in sessions_db if s["id"] != session_id]
    # Delete related messages
    messages_db = [m for m in messages_db if m["sessionId"] != session_id]
    return jsonify({"message": "Session deleted successfully"})

@app.route('/api/sessions/<session_id>/messages', methods=['GET'])
def get_messages(session_id):
    """Get all messages in session"""
    messages = [m for m in messages_db if m["sessionId"] == session_id]
    return jsonify(messages)

@app.route('/api/sessions/<session_id>/messages', methods=['POST'])
def create_message(session_id):
    """Create new message"""
    data = request.get_json()
    content = data.get('content')
    role = data.get('role', 'user')
    
    if not content:
        return jsonify({"error": "content is required"}), 400
    
    # Check if session exists
    session = next((s for s in sessions_db if s["id"] == session_id), None)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    
    message = {
        "id": str(uuid.uuid4()),
        "sessionId": session_id,
        "content": content,
        "role": role,
        "timestamp": datetime.now().isoformat()
    }
    messages_db.append(message)
    
    # Update session timestamp
    session["updatedAt"] = datetime.now().isoformat()
    
    return jsonify(message), 201

@app.route('/api/chat', methods=['GET', 'POST'])
def chat():
    """Chat endpoint - Send message to agent through ISEK node or get message history"""
    try:
        if request.method == 'GET':
            # GET request: Return message history for the session
            session_id = request.args.get('sessionId')
            if not session_id:
                return jsonify({"error": "sessionId is required"}), 400
            
            # Get messages for the session
            messages = [m for m in messages_db if m["sessionId"] == session_id]
            return jsonify(messages)
        
        # POST request: Send message to agent
        data = request.get_json()
        agent_id = data.get('agentId')
        session_id = data.get('sessionId')
        messages = data.get('messages', [])
        system = data.get('system', '')
        
        if not agent_id:
            return jsonify({"error": "agentId is required"}), 400
        
        if not session_id:
            return jsonify({"error": "sessionId is required"}), 400
        
        # Get agent information
        try:
            resp = requests.get(f"{ISEK_NODE_URL}/agents/{agent_id}", timeout=3)
            resp.raise_for_status()
            agent = resp.json()
        except Exception as e:
            print(f"Failed to get agent info: {e}")
            return jsonify({"error": "Agent not found"}), 404
        
        # Get user message content and normalize it
        user_message_content = messages[-1]["content"] if messages else ""
        
        # Handle different message content formats
        if isinstance(user_message_content, list):
            # If content is an array of objects with text fields
            if all(isinstance(item, dict) and 'text' in item for item in user_message_content):
                user_message_content = ' '.join(item['text'] for item in user_message_content)
            else:
                user_message_content = str(user_message_content)
        elif not isinstance(user_message_content, str):
            user_message_content = str(user_message_content)
        
        # Save user message to database
        user_message = {
            "id": str(uuid.uuid4()),
            "sessionId": session_id,
            "content": user_message_content,
            "role": "user",
            "timestamp": datetime.now().isoformat()
        }
        messages_db.append(user_message)
        
        # Send message to agent through ISEK node
        try:
            payload = {
                "agent_id": agent_id,
                "session_id": session_id,
                "user_id": "isek-ui-backend-user-001",
                "messages": messages,
                "system_prompt": system or agent.get('system_prompt', '')
            }
            
            resp = requests.post(f"{ISEK_NODE_URL}/chat", json=payload, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            ai_response = result.get("response", "Agent response")
        except Exception as e:
            print(f"Failed to send message to agent: {e}")
            ai_response = f"I am {agent.get('name', 'ISEK Agent')}, you said: {user_message_content}"
        
        # 只统计用户消息数量
        user_message_count = len([m for m in messages if m.get('role') == 'user'])

        # Create AI message
        ai_message = {
            "id": str(uuid.uuid4()),
            "sessionId": session_id,
            "role": "assistant",
            "timestamp": datetime.now().isoformat()
        }

        # 根据用户输入触发不同的富组件演示
        user_content = user_message_content.lower()
        if "组队" in user_content or "小队" in user_content or "recruit" in user_content:
            # 返回 assistant-ui tool 协议的 team-formation 结构
            ai_message["content"] = "正在为您组建小队..."
            ai_message["tool"] = {
                "type": "team-formation",
                "input": {
                    "task": "AI项目开发小队",
                    "requiredRoles": ["工程师", "数据科学家", "前端开发", "项目经理"]
                },
                "status": "starting"
            }
        elif "进度" in user_content or "progress" in user_content:
            # 进度更新场景：使用特殊标记的文本消息
            ai_message["content"] = [
                {"type": "text", "text": "当前任务进度如下：\n\n<UI_COMPONENT type=\"progress\" label=\"任务执行进度\" value=\"0.7\" status=\"进行中\" id=\"task-progress\" />"}
            ]
        else:
            ai_message["content"] = [
                {"type": "text", "text": ai_response}
            ]

        messages_db.append(ai_message)
        
        # Update session timestamp
        session = next((s for s in sessions_db if s["id"] == session_id), None)
        if session:
            session["updatedAt"] = datetime.now().isoformat()
        
        # --- 修改返回格式为官方 example ---
        response_data = {
            "aiMessage": ai_message,  # 包含完整的ai_message，包括tool字段
            "userMessage": {
                "id": user_message["id"],
                "role": user_message["role"],
                "content": user_message["content"],
                "timestamp": user_message["timestamp"]
            },
            "agent": {
                "id": agent.get("id", agent_id),
                "name": agent.get("name", "Agent")
            }
        }
        # 判断前端是否要求流式返回
        accept_header = request.headers.get('Accept', '')
        if 'text/event-stream' in accept_header:
            import json
            from flask import Response, stream_with_context
            
            def generate():
                import time
                # 先发送文本内容
                content = response_data["aiMessage"]["content"]
                
                # 处理不同格式的content
                text_to_send = ""
                if isinstance(content, str):
                    text_to_send = content
                elif isinstance(content, list):
                    # 从列表中提取文本内容
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            text_to_send += part.get("text", "")
                elif isinstance(content, dict) and content.get("type") == "text":
                    text_to_send = content.get("text", "")
                
                if text_to_send:
                    # 文本分块发送
                    chunk_size = 3
                    for i in range(0, len(text_to_send), chunk_size):
                        text_chunk = text_to_send[i:i+chunk_size]
                        yield f'0:{{"type":"text","text":{json.dumps(text_chunk)}}}\n'
                        time.sleep(0.04)
                
                # 检查是否有tool调用需要发送并模拟渐进式更新
                if "tool" in response_data["aiMessage"]:
                    tool_data = response_data["aiMessage"]["tool"]
                    
                    if tool_data["type"] == "team-formation":
                        # 小队组建工具的渐进式更新
                        call_id = f"call_{uuid.uuid4().hex[:8]}"
                        
                        # 1. 开始组建
                        initial_call = {
                            "type": "tool-call",
                            "toolCallId": call_id,
                            "toolName": "team-formation",
                            "args": {
                                **tool_data["input"],
                                "status": "recruiting",
                                "progress": 0.1,
                                "currentStep": "开始招募小队成员...",
                                "members": []
                            }
                        }
                        yield f'0:{json.dumps(initial_call)}\n'
                        time.sleep(1)
                        
                        # 2. 渐进式添加成员
                        members = [
                            {
                                "name": "Magic Image Agent",
                                "role": "图像生成",
                                "skill": "AI图片创作",
                                "experience": "2年",
                                "avatar": "🖼️",
                                "description": "根据文本描述生成高质量图片，支持风格化和多场景渲染"
                            },
                            {
                                "name": "Data Insight Agent",
                                "role": "数据分析",
                                "skill": "自动化数据洞察",
                                "experience": "3年",
                                "avatar": "📊",
                                "description": "擅长大数据分析、趋势预测和可视化报告"
                            },
                            {
                                "name": "Smart QA Agent",
                                "role": "智能问答",
                                "skill": "知识检索/FAQ",
                                "experience": "2年",
                                "avatar": "💡",
                                "description": "快速响应用户问题，支持多领域知识库"
                            },
                            {
                                "name": "Workflow Orchestrator",
                                "role": "流程编排",
                                "skill": "多Agent协作调度",
                                "experience": "4年",
                                "avatar": "🕹️",
                                "description": "负责各智能体之间的任务分配与流程自动化"
                            }
                        ]
                        
                        current_members = []
                        for i, member in enumerate(members):
                            current_members.append(member)
                            progress = 0.2 + (i + 1) * 0.2
                            step = f"已招募 {member['name']} ({member['role']})..."
                            
                            update_call = {
                                "type": "tool-call",
                                "toolCallId": call_id,
                                "toolName": "team-formation",
                                "args": {
                                    **tool_data["input"],
                                    "status": "recruiting",
                                    "progress": progress,
                                    "currentStep": step,
                                    "members": current_members.copy()
                                }
                            }
                            yield f'0:{json.dumps(update_call)}\n'
                            time.sleep(0.8)
                        
                        # 3. 完成组建
                        final_call = {
                            "type": "tool-call",
                            "toolCallId": call_id,
                            "toolName": "team-formation",
                            "args": {
                                **tool_data["input"],
                                "status": "completed",
                                "progress": 1.0,
                                "currentStep": "小队组建完成！",
                                "members": current_members,
                                "teamStats": {
                                    "totalMembers": len(current_members),
                                    "avgExperience": "4年",
                                    "skills": ["项目管理", "机器学习", "前端开发", "数据科学"]
                                }
                            }
                        }
                        yield f'0:{json.dumps(final_call)}\n'
                    else:
                        # 其他工具的常规处理
                        tool_call = {
                            "type": "tool-call",
                            "toolCallId": f"call_{uuid.uuid4().hex[:8]}",
                            "toolName": tool_data["type"],
                            "args": tool_data["input"]
                        }
                        yield f'0:{json.dumps(tool_call)}\n'
                
                finish_data = {
                    "finishReason": "stop",
                    "usage": {
                        "promptTokens": 0,
                        "completionTokens": len(content) if isinstance(content, str) else 0
                    }
                }
                yield f'd:{json.dumps(finish_data)}\n'
            
            response = Response(stream_with_context(generate()), mimetype='text/plain; charset=utf-8')
            response.headers['Cache-Control'] = 'no-cache'
            response.headers['Connection'] = 'keep-alive'
            response.headers['x-vercel-ai-data-stream'] = 'v1'
            return response
        else:
            return jsonify(response_data)
    except Exception as e:
        print(f"Chat endpoint error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"服务器内部错误: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        resp = requests.get(f"{ISEK_NODE_URL}/network/status", timeout=3)
        network_status = resp.json() if resp.status_code == 200 else {"status": "disconnected"}
    except:
        network_status = {"status": "disconnected"}
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "sessions_count": len(sessions_db),
        "messages_count": len(messages_db),
        "isek_node": network_status
    })

# Error handling
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print(f"Starting ISEK UI Backend on port {port}")
    print(f"Debug mode: {app.debug}")
    print("Connecting to ISEK node...")
    app.run(host='0.0.0.0', port=port, debug=False) 