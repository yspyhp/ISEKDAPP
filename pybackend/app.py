#!/usr/bin/env python3
"""
ISEK UI Python Backend
ISEK Node Client - Connect to local ISEK node
"""

import os
import uuid
from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS
from datetime import datetime
import asyncio
from isek_client import isek_client

app = Flask(__name__)
CORS(app)

ISEK_NODE_URL = os.getenv('ISEK_NODE_URL', 'http://localhost:8000')

sessions_db = []
messages_db = []

# --- 格式化函数 ---
def format_agent(agent):
    return {
        "id": agent.get("id", ""),
        "name": agent.get("name", ""),
        "description": agent.get("description", ""),
        "system_prompt": agent.get("system_prompt") or agent.get("systemPrompt", ""),
        "model": agent.get("model", ""),
        "address": agent.get("address", ""),
        "capabilities": agent.get("capabilities", []),
        "status": agent.get("status", "online")
    }

def format_chat_response(ai_message, agent_id, session_id, user_id):
    # ai_message["content"] 可能是字符串或[{type: text, text: ...}]
    if isinstance(ai_message["content"], str):
        content = ai_message["content"]
    elif isinstance(ai_message["content"], list) and ai_message["content"] and isinstance(ai_message["content"][0], dict):
        content = ai_message["content"][0].get("text", "")
    else:
        content = str(ai_message["content"])
    return {
        "response": content,
        "agent_id": agent_id,
        "session_id": session_id,
        "user_id": user_id,
        "timestamp": ai_message["timestamp"]
    }

def format_network_status(status, agents_count):
    return {
        "connected": status == "connected",
        "agents_count": agents_count,
        "timestamp": datetime.now().isoformat()
    }

# --- API 实现 ---
@app.route('/api/agents', methods=['GET'])
def get_agents():
    try:
        agents = asyncio.run(isek_client.discover_agents())
        return jsonify([format_agent(a) for a in agents])
    except Exception as e:
        print(f"Failed to get agents: {e}")
        return jsonify([]), 500

@app.route('/api/agents/<agent_id>', methods=['GET'])
def get_agent(agent_id):
    try:
        agents = asyncio.run(isek_client.discover_agents())
        agent = next((a for a in agents if a["id"] == agent_id), None)
        if agent:
            return jsonify(format_agent(agent))
        return jsonify({"error": "Agent not found"}), 404
    except Exception as e:
        print(f"Failed to get agent: {e}")
        return jsonify({"error": "Agent not found"}), 404

@app.route('/api/network/status', methods=['GET'])
def get_network_status():
    try:
        agents = asyncio.run(isek_client.discover_agents())
        status = "connected"
        return jsonify(format_network_status(status, len(agents)))
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
    
    try:
        agent = {"id": agent_id, "name": "Example Agent", "description": "This is a placeholder agent", "address": "http://localhost:8000"}
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
    sessions_db = [s for s in sessions_db if s["id"] != session_id]
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
    
    session["updatedAt"] = datetime.now().isoformat()
    
    return jsonify(message), 201

@app.route('/api/chat', methods=['GET', 'POST'])
def chat():
    """Chat endpoint - Send message to agent through ISEK node or get message history"""
    try:
        if request.method == 'GET':
            session_id = request.args.get('sessionId')
            if not session_id:
                return jsonify({"error": "sessionId is required"}), 400
            messages = [m for m in messages_db if m["sessionId"] == session_id]
            return jsonify(messages)
        
        data = request.get_json()
        agent_id = data.get('agentId')
        session_id = data.get('sessionId')
        messages = data.get('messages', [])
        system = data.get('system', '')
        
        if not agent_id:
            return jsonify({"error": "agentId is required"}), 400
        
        if not session_id:
            return jsonify({"error": "sessionId is required"}), 400
        
        user_message_content = messages[-1]["content"] if messages else ""
        
        if isinstance(user_message_content, list):
            if all(isinstance(item, dict) and 'text' in item for item in user_message_content):
                user_message_content = ' '.join(item['text'] for item in user_message_content)
            else:
                user_message_content = str(user_message_content)
        elif not isinstance(user_message_content, str):
            user_message_content = str(user_message_content)
        
        user_message = {
            "id": str(uuid.uuid4()),
            "sessionId": session_id,
            "content": user_message_content,
            "role": "user",
            "timestamp": datetime.now().isoformat()
        }
        messages_db.append(user_message)
        
        ai_response = asyncio.run(isek_client.send_message_to_agent(agent_id, messages, system, session_id))
        
        ai_message = {
            "id": str(uuid.uuid4()),
            "sessionId": session_id,
            "role": "assistant",
            "timestamp": datetime.now().isoformat(),
            "content": ai_response
        }

        user_content = user_message_content.lower()
        if "组队" in user_content or "小队" in user_content or "recruit" in user_content:
            ai_message["content"] = "正在为您组建小队..."
            ai_message["tool"] = {
                "type": "team-formation",
                "input": {
                    "task": "AI项目开发小队",
                    "requiredRoles": ["工程师", "数据科学家", "前端开发", "项目经理"]
                },
                "status": "starting"
            }
        else:
            ai_message["content"] = [
                {"type": "text", "text": ai_response}
            ]

        messages_db.append(ai_message)
        
        session = next((s for s in sessions_db if s["id"] == session_id), None)
        if session:
            session["updatedAt"] = datetime.now().isoformat()
        
        response_data = {
            "aiMessage": ai_message,
            "userMessage": {
                "id": user_message["id"],
                "role": user_message["role"],
                "content": user_message["content"],
                "timestamp": user_message["timestamp"]
            },
            "agent": {
                "id": agent_id
            }
        }
        accept_header = request.headers.get('Accept', '')
        if 'text/event-stream' in accept_header:
            import json
            from flask import Response, stream_with_context
            
            def generate():
                import time
                content = response_data["aiMessage"]["content"]
                
                text_to_send = ""
                if isinstance(content, str):
                    text_to_send = content
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            text_to_send += part.get("text", "")
                elif isinstance(content, dict) and content.get("type") == "text":
                    text_to_send = content.get("text", "")
                
                if text_to_send:
                    chunk_size = 3
                    for i in range(0, len(text_to_send), chunk_size):
                        text_chunk = text_to_send[i:i+chunk_size]
                        yield f'0:{{"type":"text","text":{json.dumps(text_chunk)}}}\n'
                        time.sleep(0.04)
                
                if "tool" in response_data["aiMessage"]:
                    tool_data = response_data["aiMessage"]["tool"]
                    
                    if tool_data["type"] == "team-formation":
                        call_id = f"call_{uuid.uuid4().hex[:8]}"
                        
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
        network_status = {"status": "connected"}
    except:
        network_status = {"status": "disconnected"}
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "sessions_count": len(sessions_db),
        "messages_count": len(messages_db),
        "isek_node": network_status
    })

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