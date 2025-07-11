#!/usr/bin/env python3
"""
ISEK Node Simulator
For testing ISEK UI backend client connections
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Mock agent data
mock_agents = [
    {
        "id": "isek-assistant-001",
        "name": "ISEK Assistant",
        "description": "Friendly assistant in the ISEK network, good at answering various questions",
        "system_prompt": "I am a friendly assistant in the ISEK network, happy to serve you.",
        "model": "gpt-4o-mini",
        "address": "isek://agent/assistant-001",
        "capabilities": ["chat", "help", "general"],
        "status": "online"
    },
    {
        "id": "isek-expert-002",
        "name": "ISEK Tech Expert",
        "description": "Technical expert in the ISEK network, good at solving technical problems",
        "system_prompt": "I am a technical expert in the ISEK network, good at solving various technical problems.",
        "model": "gpt-4o-mini",
        "address": "isek://agent/expert-002",
        "capabilities": ["tech_support", "analysis", "debugging"],
        "status": "online"
    },
    {
        "id": "isek-creative-003",
        "name": "ISEK Creative",
        "description": "Creative expert in the ISEK network, good at creativity and brainstorming",
        "system_prompt": "I am a creative expert in the ISEK network, good at creativity and brainstorming.",
        "model": "gpt-4o-mini",
        "address": "isek://agent/creative-003",
        "capabilities": ["creative", "brainstorming", "design"],
        "status": "online"
    }
]

# Mock user ID for all requests
MOCK_USER_ID = "isek-ui-backend-user-001"

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "node_id": "mock-isek-node-001",
        "version": "1.0.0"
    })

@app.route('/agents', methods=['GET'])
def get_agents():
    """Get agent list"""
    return jsonify(mock_agents)

@app.route('/agents/<agent_id>', methods=['GET'])
def get_agent(agent_id):
    """Get specific agent"""
    agent = next((a for a in mock_agents if a["id"] == agent_id), None)
    if agent:
        return jsonify(agent)
    return jsonify({"error": "Agent not found"}), 404

@app.route('/chat', methods=['POST'])
def chat():
    """Chat endpoint"""
    data = request.get_json()
    agent_id = data.get('agent_id')
    session_id = data.get('session_id')
    user_id = MOCK_USER_ID  # Default mock user ID
    messages = data.get('messages', [])
    system_prompt = data.get('system_prompt', '')
    
    if not agent_id:
        return jsonify({"error": "agent_id is required"}), 400
    
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    
    # Find agent
    agent = next((a for a in mock_agents if a["id"] == agent_id), None)
    if not agent:
        return jsonify({"error": "Agent not found"}), 404
    
    # Get user message and normalize it
    user_message = messages[-1]["content"] if messages else "Hello"
    
    # Handle different message content formats
    if isinstance(user_message, list):
        # If content is an array of objects with text fields
        if all(isinstance(item, dict) and 'text' in item for item in user_message):
            user_message = ' '.join(item['text'] for item in user_message)
        else:
            user_message = str(user_message)
    elif not isinstance(user_message, str):
        user_message = str(user_message)
    
    # Generate response based on agent type
    if "assistant" in agent_id:
        response = f"Hello! I am {agent['name']}, happy to serve you. You said: {user_message}"
    elif "expert" in agent_id:
        response = f"From a technical perspective, {user_message} can be solved like this..."
    elif "creative" in agent_id:
        response = f"Wow! About {user_message}, let me provide some creative ideas..."
    else:
        response = f"I am {agent['name']}, you said: {user_message}"
    
    return jsonify({
        "response": response,
        "agent_id": agent_id,
        "session_id": session_id,
        "user_id": user_id,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/network/status', methods=['GET'])
def network_status():
    """Network status"""
    return jsonify({
        "connected": True,
        "agents_count": len(mock_agents),
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    print("Starting ISEK Node simulator...")
    print("Simulator will run at http://localhost:8000")
    print("Available endpoints:")
    print("  GET  /health - Health check")
    print("  GET  /agents - Get agent list")
    print("  GET  /agents/<id> - Get specific agent")
    print("  POST /chat - Send message")
    print("  GET  /network/status - Network status")
    
    app.run(host='0.0.0.0', port=8000, debug=True) 