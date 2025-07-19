#!/usr/bin/env python3
"""
ISEK UI Python Backend
ISEK Node Client Integration - Real implementation using isek_client
"""

import os
import uuid
import logging
from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS
from datetime import datetime
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import asdict

from isek_client import get_client, initialize_client, SessionConfig, MessageConfig, AgentConfig, NetworkStatus
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Initialize ISEK client
client = get_client()

# Helper function to run async code in sync context
def run_async(coro):
    """Run async coroutine in a separate thread with its own event loop"""
    def run_in_thread():
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()
    
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(run_in_thread)
        return future.result()

# --- Response Formatters ---
def format_agent_response(agent: AgentConfig) -> Dict[str, Any]:
    """Format agent config for API response"""
    return asdict(agent)

def format_session_response(session: SessionConfig) -> Dict[str, Any]:
    """Format session config for API response"""
    return {
        "id": session.id,
        "title": session.title,
        "agentId": session.agent_id,
        "agentName": session.agent_name,
        "agentDescription": session.agent_description,
        "agentAddress": session.agent_address,
        "createdAt": session.created_at,
        "updatedAt": session.updated_at,
        "messageCount": session.message_count
    }

def format_message_response(message: MessageConfig) -> Dict[str, Any]:
    """Format message config for API response"""
    return {
        "id": message.id,
        "sessionId": message.session_id,
        "content": message.content,
        "role": message.role,
        "timestamp": message.timestamp
    }

# --- API Endpoints ---

@app.route('/api/agents', methods=['GET'])
def get_agents():
    """Get all available agents"""
    try:
        agents = run_async(client.discover_agents())
        return jsonify([format_agent_response(agent) for agent in agents])
    except Exception as e:
        logger.error(f"Failed to get agents: {e}")
        return jsonify({"error": "Failed to get agents"}), 500

@app.route('/api/agents/<agent_id>', methods=['GET'])
def get_agent(agent_id: str):
    """Get specific agent by ID"""
    try:
        agent = client.get_agent_by_id(agent_id)
        if not agent:
            # Try to refresh agents cache
            run_async(client.discover_agents())
            agent = client.get_agent_by_id(agent_id)
        
        if agent:
            return jsonify(format_agent_response(agent))
        return jsonify({"error": "Agent not found"}), 404
    except Exception as e:
        logger.error(f"Failed to get agent {agent_id}: {e}")
        return jsonify({"error": "Agent not found"}), 404

@app.route('/api/network/status', methods=['GET'])
def get_network_status():
    """Get network connection status"""
    try:
        status = client.get_network_status()
        return jsonify(asdict(status))
    except Exception as e:
        logger.error(f"Failed to get network status: {e}")
        return jsonify({"error": "Failed to get network status"}), 500

@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """Get all chat sessions, optionally filtered by agent"""
    try:
        agent_id = request.args.get('agentId')
        user_id = request.args.get('userId')
        
        sessions = client.get_all_sessions(user_id=user_id, agent_id=agent_id)
        return jsonify([format_session_response(session) for session in sessions])
    except Exception as e:
        logger.error(f"Failed to get sessions: {e}")
        return jsonify({"error": "Failed to get sessions"}), 500

@app.route('/api/sessions', methods=['POST'])
def create_session():
    """Create new chat session"""
    try:
        data = request.get_json()
        agent_id = data.get('agentId')
        title = data.get('title')
        
        if not agent_id:
            return jsonify({"error": "agentId is required"}), 400
        
        # Check if agent exists
        if not client.is_agent_available(agent_id):
            # Try to refresh agents cache
            run_async(client.discover_agents())
            if not client.is_agent_available(agent_id):
                return jsonify({"error": "Agent not found"}), 404
        
        session = client.create_session(agent_id=agent_id, title=title)
        return jsonify(format_session_response(session)), 201
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        return jsonify({"error": "Failed to create session"}), 500

@app.route('/api/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id: str):
    """Delete chat session"""
    try:
        success = client.delete_session(session_id)
        if success:
            return jsonify({"message": "Session deleted successfully"})
        return jsonify({"error": "Session not found"}), 404
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {e}")
        return jsonify({"error": "Failed to delete session"}), 500

@app.route('/api/sessions/<session_id>/messages', methods=['GET'])
def get_messages(session_id: str):
    """Get all messages in session"""
    try:
        messages = client.get_session_messages(session_id)
        return jsonify([format_message_response(message) for message in messages])
    except Exception as e:
        logger.error(f"Failed to get messages for session {session_id}: {e}")
        return jsonify({"error": "Failed to get messages"}), 500

@app.route('/api/sessions/<session_id>/messages', methods=['POST'])
def create_message(session_id: str):
    """Create new message"""
    try:
        data = request.get_json()
        content = data.get('content')
        role = data.get('role', 'user')
        
        if not content:
            return jsonify({"error": "content is required"}), 400
        
        # Check if session exists
        session = client.get_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404
        
        message = client.add_message(session_id=session_id, content=content, role=role)
        return jsonify(format_message_response(message)), 201
    except Exception as e:
        logger.error(f"Failed to create message: {e}")
        return jsonify({"error": "Failed to create message"}), 500

@app.route('/api/sessions/<session_id>/messages', methods=['DELETE'])
def clear_session_messages(session_id: str):
    """Clear all messages from session (restart conversation)"""
    try:
        success = client.clear_session_messages(session_id)
        if success:
            return jsonify({"message": "Conversation cleared successfully"})
        return jsonify({"error": "Session not found"}), 404
    except Exception as e:
        logger.error(f"Failed to clear messages for session {session_id}: {e}")
        return jsonify({"error": "Failed to clear messages"}), 500

@app.route('/api/chat', methods=['GET', 'POST'])
def chat():
    """Chat endpoint - Send message to agent through ISEK node or get message history"""
    try:
        if request.method == 'GET':
            session_id = request.args.get('sessionId')
            if not session_id:
                return jsonify({"error": "sessionId is required"}), 400
            
            messages = client.get_session_messages(session_id)
            return jsonify([format_message_response(message) for message in messages])
        
        # POST request - send message to agent
        data = request.get_json()
        session_id = data.get('sessionId')
        messages = data.get('messages', [])
        system = data.get('system', '')
        
        if not session_id:
            return jsonify({"error": "sessionId is required"}), 400
        
        # Check if session exists (agent is bound to session)
        session = client.get_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404
        
        # Verify the bound agent is still available
        if not client.is_agent_available(session.agent_id):
            return jsonify({"error": "Agent bound to session is not available"}), 404
        
        # Process user message content
        user_message_content = messages[-1]["content"] if messages else ""
        if isinstance(user_message_content, list) and all(isinstance(item, dict) and 'text' in item for item in user_message_content):
            user_message_content = ' '.join(item['text'] for item in user_message_content)
        elif not isinstance(user_message_content, str):
            user_message_content = str(user_message_content)
        
        # Add user message to session
        user_message = client.add_message(
            session_id=session_id,
            content=user_message_content,
            role="user"
        )
        
        # Get AI response from agent (routes to correct agent via session)
        ai_response = run_async(client.send_message_to_agent(
            session_id=session_id,
            system_prompt=system
        ))
        
        # Parse agent response to extract content and tool calls
        parsed_response = client.parse_agent_response(ai_response)
        content = parsed_response["content"]
        tool_calls = parsed_response["tool_calls"]
        
        # Add AI response to session
        ai_message = client.add_message(
            session_id=session_id,
            content=content,
            role="assistant",
            tool_calls=tool_calls if tool_calls else None
        )
        
        # Create AI message with tool support
        ai_message_dict = {
            "id": ai_message.id,
            "sessionId": session_id,
            "role": ai_message.role,
            "timestamp": ai_message.timestamp,
            "content": [{"type": "text", "text": content}]
        }

        # Add tool calls if present
        if tool_calls:
            ai_message_dict["tool_calls"] = client.format_tool_calls_for_frontend(tool_calls)
        
        # Prepare response data
        response_data = {
            "aiMessage": ai_message_dict,
            "userMessage": {
                "id": user_message.id,
                "role": user_message.role,
                "content": user_message.content,
                "timestamp": user_message.timestamp
            },
            "agent": {"id": session.agent_id}
        }
        
        # Handle streaming response
        if 'text/event-stream' in request.headers.get('Accept', ''):
            return _create_streaming_response(response_data)
        return jsonify(response_data)
            
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Chat error: {str(e)}"}), 500

def _create_streaming_response(response_data: Dict[str, Any]) -> Response:
    """Create streaming response for chat"""
    def generate():
        import time
        import json
        
        content = response_data["aiMessage"]["content"]
        
        # Send text content
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
        
        # Send tool calls if present
        if "tool_calls" in response_data["aiMessage"]:
            tool_calls = response_data["aiMessage"]["tool_calls"]
            
            for tool_call in tool_calls:
                tool_name = tool_call.get("function", {}).get("name", "unknown")
                call_id = tool_call.get("id", f"call_{uuid.uuid4().hex[:8]}")
                
                # Special handling for team-formation tool (testing simulation)
                if tool_name == "team-formation":
                    yield from _simulate_team_formation_stream(call_id, tool_call)
                else:
                    # Regular tool call
                    formatted_tool_call = {
                        "type": "tool-call",
                        "toolCallId": call_id,
                        "toolName": tool_name,
                        "args": tool_call.get("function", {}).get("arguments", {})
                    }
                    yield f'0:{json.dumps(formatted_tool_call)}\n'
                    time.sleep(0.1)
    
def _simulate_team_formation_stream(call_id: str, tool_call: Dict[str, Any]):
        """Simulate team formation streaming for testing"""
        import time
        import json
        
        tool_args = tool_call.get("function", {}).get("arguments", {})
        
        # Initial call
        initial_call = {
            "type": "tool-call",
            "toolCallId": call_id,
            "toolName": "team-formation",
            "args": {
                **tool_args,
                "status": "recruiting",
                "progress": 0.1,
                "currentStep": "开始招募小队成员...",
                "members": []
            }
        }
        yield f'0:{json.dumps(initial_call)}\n'
        time.sleep(1)
        
        # Mock team members
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
        
        # Simulate recruitment process
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
                    **tool_args,
                    "status": "recruiting",
                    "progress": progress,
                    "currentStep": step,
                    "members": current_members.copy()
                }
            }
            yield f'0:{json.dumps(update_call)}\n'
            time.sleep(0.8)
        
        # Final call
        final_call = {
            "type": "tool-call",
            "toolCallId": call_id,
            "toolName": "team-formation",
            "args": {
                **tool_args,
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
        
        # Finish response
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

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        network_status = client.get_network_status()
        sessions = client.get_all_sessions()
        
        total_messages = 0
        for session in sessions:
            total_messages += len(client.get_session_messages(session.id))
        
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "sessions_count": len(sessions),
            "messages_count": total_messages,
            "isek_node": {
                "status": "connected" if network_status.connected else "disconnected",
                "agents_count": network_status.agents_count,
                "node_id": network_status.node_id
            }
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

# Initialize client on startup
async def startup():
    """Initialize ISEK client on application startup"""
    try:
        await initialize_client()
        logger.info("ISEK client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize ISEK client: {e}")

if __name__ == '__main__':
    # Initialize client
    run_async(startup())
    
    port = int(os.getenv('PORT', 5000))
    logger.info(f"Starting ISEK UI Backend on port {port}")
    logger.info("Using ISEK client integration")
    app.run(host='0.0.0.0', port=port, debug=False)