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
    
    # Create AI message
    ai_message = {
        "id": str(uuid.uuid4()),
        "sessionId": session_id,
        "content": ai_response,
        "role": "assistant",
        "timestamp": datetime.now().isoformat()
    }
    messages_db.append(ai_message)
    
    # Update session timestamp
    session = next((s for s in sessions_db if s["id"] == session_id), None)
    if session:
        session["updatedAt"] = datetime.now().isoformat()
    
    # Return streaming response format that assistant-ui expects
    response_data = {
        "id": ai_message["id"],
        "content": ai_response,
        "role": "assistant",
        "timestamp": ai_message["timestamp"]
    }
    
    # 判断前端是否要求流式返回
    accept_header = request.headers.get('Accept', '')
    if 'text/event-stream' in accept_header:
        import json
        from flask import Response, stream_with_context
        def generate():
            # Use assistant-stream protocol format with type:json format
            # Type "0" = TextDelta for text content
            content = response_data["content"]
            # Split content into chunks for streaming effect
            words = content.split()
            for i, word in enumerate(words):
                # TextDelta should send the text directly, not wrapped in an object
                text_chunk = word + (" " if i < len(words) - 1 else "")
                yield f'0:{json.dumps(text_chunk)}\n'
                import time
                time.sleep(0.1)  # Simulate streaming delay
            
            # Type "d" = FinishMessage to end the stream
            finish_data = {
                "finishReason": "stop",
                "usage": {
                    "promptTokens": 0,
                    "completionTokens": len(words)
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