#!/usr/bin/env python3
"""
ISEK UI Python Backend - FastAPI Version
ISEK Node Client Integration with native async support
"""

import os
import uuid
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import asdict
from contextlib import asynccontextmanager

from isek_client import get_client, initialize_client, SessionConfig, MessageConfig, AgentConfig, NetworkStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global client instance
client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global client
    try:
        # Startup
        client = get_client()
        await initialize_client()
        logger.info("ISEK client initialized successfully")
        
        # Fetch existing sessions from agent servers
        try:
            logger.info("Fetching existing sessions from agent servers...")
            sessions = await client.get_all_sessions_distributed()
            logger.info(f"Successfully fetched {len(sessions)} sessions from agent servers")
            for session in sessions:
                logger.info(f"- Session {session.id}: {session.title} (Agent: {session.agent_name})")
        except Exception as e:
            logger.warning(f"Failed to fetch sessions from agent servers: {e}")
            logger.info("Continuing with empty session cache...")
        
        yield
    except Exception as e:
        logger.error(f"Failed to initialize ISEK client: {e}")
        yield
    finally:
        # Shutdown
        logger.info("Shutting down ISEK client")

# Create FastAPI app with lifespan
app = FastAPI(
    title="ISEK UI Backend",
    description="ISEK Node Client Integration with native async support",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Response Formatters ---
def format_agent_response(agent: AgentConfig) -> Dict[str, Any]:
    """Format agent config for API response"""
    return asdict(agent)

def format_session_response(session: SessionConfig) -> Dict[str, Any]:
    """Format session config for API response"""
    return {
        "id": session.id,
        "title": session.title,
        "agentId": session.node_id,
        "agentName": session.agent_name,
        "agentDescription": session.agent_description,
        "agentAddress": session.agent_address,
        "createdAt": session.created_at,
        "updatedAt": session.updated_at,
        "messageCount": session.message_count
    }

def format_message_response(message: MessageConfig) -> Dict[str, Any]:
    """Format message config for API response"""
    result = {
        "id": message.id,
        "sessionId": message.session_id,
        "content": message.content,
        "role": message.role,
        "timestamp": message.timestamp
    }
    
    # Include tool calls if present - 修复工具调用数据格式
    if hasattr(message, 'tool_calls') and message.tool_calls:
        # 确保工具调用数据格式正确，包含完整的小队信息
        formatted_tool_calls = []
        for tool_call in message.tool_calls:
            if isinstance(tool_call, dict):
                # 如果是字典格式，直接使用
                formatted_tool_calls.append(tool_call)
            else:
                # 如果是其他格式，转换为标准格式
                formatted_tool_calls.append({
                    "id": getattr(tool_call, 'id', f"call_{uuid.uuid4().hex[:8]}"),
                    "type": getattr(tool_call, 'type', 'function'),
                    "function": {
                        "name": getattr(tool_call, 'name', 'unknown'),
                        "arguments": getattr(tool_call, 'arguments', {})
                    }
                })
        result["toolInvocations"] = formatted_tool_calls
        # 同时保存为 tool_calls 以保持一致性
        result["tool_calls"] = formatted_tool_calls
    
    return result

# --- API Endpoints ---

@app.get("/api/agents")
async def get_agents(refresh: bool = False):
    """Get all available agents"""
    try:
        agents = await client.discover_agents(force_refresh=refresh)
        return [format_agent_response(agent) for agent in agents]
    except Exception as e:
        logger.error(f"Failed to get agents: {e}")
        raise HTTPException(status_code=500, detail="Failed to get agents")

@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get specific agent by ID"""
    try:
        agent = client.get_agent_by_id(agent_id)
        
        if agent:
            return format_agent_response(agent)
        raise HTTPException(status_code=404, detail="Agent not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent {agent_id}: {e}")
        raise HTTPException(status_code=404, detail="Agent not found")

@app.get("/api/network/status")
async def get_network_status():
    """Get network connection status"""
    try:
        status = client.get_network_status()
        return asdict(status)
    except Exception as e:
        logger.error(f"Failed to get network status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get network status")

@app.get("/api/sessions")
async def get_sessions(agentId: Optional[str] = None, userId: Optional[str] = None):
    """Get all chat sessions, optionally filtered by agent"""
    try:
        sessions = client.get_all_sessions(user_id=userId, node_id=agentId)
        return [format_session_response(session) for session in sessions]
    except Exception as e:
        logger.error(f"Failed to get sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get sessions")

@app.post("/api/sessions/sync")
async def sync_sessions_from_agents():
    """Sync sessions from all agent servers"""
    try:
        logger.info("Manual session sync requested")
        sessions = await client.get_all_sessions_distributed()
        logger.info(f"Synced {len(sessions)} sessions from agent servers")
        return {
            "message": "Sessions synced successfully",
            "count": len(sessions),
            "sessions": [format_session_response(session) for session in sessions]
        }
    except Exception as e:
        logger.error(f"Failed to sync sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync sessions")

@app.post("/api/sessions")
async def create_session(request: Dict[str, Any]):
    """Create new chat session"""
    try:
        node_id = request.get('agentId')  # Keep 'agentId' in API for frontend compatibility
        title = request.get('title')
        
        if not node_id:
            raise HTTPException(status_code=400, detail="agentId is required")
        
        # Check if agent exists (remove expensive refresh)
        if not client.is_agent_available(node_id):
            raise HTTPException(status_code=404, detail="Agent not found")
        
        session = client.create_session(node_id=node_id, title=title)
        return format_session_response(session)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create session")

@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete chat session"""
    try:
        success = client.delete_session(session_id)
        if success:
            return {"message": "Session deleted successfully"}
        raise HTTPException(status_code=404, detail="Session not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete session")

@app.get("/api/sessions/{session_id}/messages")
async def get_messages(session_id: str):
    """Get all messages in session"""
    try:
        messages = client.get_session_messages(session_id)
        return [format_message_response(message) for message in messages]
    except Exception as e:
        logger.error(f"Failed to get messages for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get messages")

@app.post("/api/sessions/{session_id}/messages")
async def create_message(session_id: str, request: Dict[str, Any]):
    """Create new message"""
    try:
        content = request.get('content')
        role = request.get('role', 'user')
        
        if not content:
            raise HTTPException(status_code=400, detail="content is required")
        
        # Check if session exists
        session = client.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        message = client.add_message(session_id=session_id, content=content, role=role)
        return format_message_response(message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create message: {e}")
        raise HTTPException(status_code=500, detail="Failed to create message")

@app.delete("/api/sessions/{session_id}/messages")
async def clear_session_messages(session_id: str):
    """Clear all messages from session (restart conversation)"""
    try:
        success = client.clear_session_messages(session_id)
        if success:
            return {"message": "Conversation cleared successfully"}
        raise HTTPException(status_code=404, detail="Session not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear messages for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear messages")

@app.get("/api/chat")
async def get_chat_history(sessionId: str):
    """Get message history for a session"""
    try:
        if not sessionId:
            raise HTTPException(status_code=400, detail="sessionId is required")
        
        messages = client.get_session_messages(sessionId)
        return [format_message_response(message) for message in messages]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get chat history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get chat history")

@app.post("/api/chat")
async def chat(request: Request):
    """Chat endpoint - Send message to agent through ISEK node"""
    try:
        data = await request.json()
        session_id = data.get('sessionId')
        messages = data.get('messages', [])
        system = data.get('system', '')
        
        if not session_id:
            raise HTTPException(status_code=400, detail="sessionId is required")
        
        # Check if session exists (agent is bound to session)
        session = client.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Verify the bound agent is still available
        if not client.is_agent_available(session.node_id):
            raise HTTPException(status_code=404, detail="Agent bound to session is not available")
        
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
        
        # Get AI response from agent (routes to correct agent via session) - ASYNC!
        ai_response = await client.send_message_to_agent(
            session_id=session_id,
            system_prompt=system
        )
        
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

        # Add tool calls if present - 修复工具调用数据格式
        if tool_calls:
            # 确保工具调用数据包含完整的小队信息
            formatted_tool_calls = []
            for tool_call in tool_calls:
                formatted_call = {
                    "id": tool_call.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                    "type": tool_call.get("type", "function"),
                    "function": {
                        "name": tool_call.get("function", {}).get("name", "unknown"),
                        "arguments": tool_call.get("function", {}).get("arguments", {})
                    }
                }
                formatted_tool_calls.append(formatted_call)
            ai_message_dict["tool_calls"] = formatted_tool_calls
            # 同时保存为 toolInvocations 以保持兼容性
            ai_message_dict["toolInvocations"] = formatted_tool_calls
        
        # Prepare response data
        response_data = {
            "aiMessage": ai_message_dict,
            "userMessage": {
                "id": user_message.id,
                "role": user_message.role,
                "content": user_message.content,
                "timestamp": user_message.timestamp
            },
            "agent": {"id": session.node_id}
        }
        
        # Check if streaming is requested
        accept_header = request.headers.get('accept', '')
        if 'text/event-stream' in accept_header:
            return StreamingResponse(
                _create_streaming_response(response_data),
                media_type='text/plain; charset=utf-8',
                headers={
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'x-vercel-ai-data-stream': 'v1'
                }
            )
        
        return response_data
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

async def _create_streaming_response(response_data: Dict[str, Any]):
    """Create streaming response for chat"""
    import asyncio
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
            await asyncio.sleep(0.04)
    
    # Send tool calls if present
    if "tool_calls" in response_data["aiMessage"]:
        tool_calls = response_data["aiMessage"]["tool_calls"]
        
        # 调试信息
        logger.info(f"🔍 Streaming tool_calls: {tool_calls}")
        
        for tool_call in tool_calls:
            tool_name = tool_call.get("function", {}).get("name", "unknown")
            call_id = tool_call.get("id", f"call_{uuid.uuid4().hex[:8]}")
            
            # 调试信息
            logger.info(f"🔍 Processing tool_call: {tool_call}")
            logger.info(f"🔍 tool_name: {tool_name}")
            logger.info(f"🔍 call_id: {call_id}")
            
            # Special handling for team-formation - simulate streaming progress
            if tool_name == "team-formation":
                async for chunk in _simulate_team_formation_streaming(call_id, tool_call):
                    yield chunk
            else:
                # Regular tool call
                formatted_tool_call = {
                    "type": "tool-call",
                    "toolCallId": call_id,
                    "toolName": tool_name,
                    "args": tool_call.get("function", {}).get("arguments", {})
                }
                yield f'0:{json.dumps(formatted_tool_call)}\n'
                await asyncio.sleep(0.1)
    
    # Finish response
    finish_data = {
        "finishReason": "stop",
        "usage": {
            "promptTokens": 0,
            "completionTokens": len(content) if isinstance(content, str) else 0
        }
    }
    yield f'd:{json.dumps(finish_data)}\n'

async def _simulate_team_formation_streaming(call_id: str, tool_call: Dict[str, Any]):
    """Simulate streaming progress for team formation using server data"""
    import asyncio
    import json
    
    # Get initial data from server response
    server_args = tool_call.get("function", {}).get("arguments", {})
    initial_members = server_args.get("members", [])
    
    # 调试信息
    logger.info(f"🔍 Client backend received tool_call: {tool_call}")
    logger.info(f"🔍 server_args: {server_args}")
    logger.info(f"🔍 initial_members: {initial_members}")
    logger.info(f"🔍 initial_members length: {len(initial_members)}")
    
    # 如果服务器已经提供了完整的小队数据，直接返回完成状态
    if server_args.get("status") == "completed" and initial_members:
        final_args = {
            **server_args,
            "members": initial_members,
            "teamStats": {
                "totalMembers": len(initial_members),
                "skills": ["AI图片创作", "数据分析", "智能问答", "流程编排"]
            }
        }
        final_call = {
            "type": "tool-call",
            "toolCallId": call_id,
            "toolName": "team-formation", 
            "args": final_args
        }
        yield f'0:{json.dumps(final_call)}\n'
        return
    
    # Initial call with starting progress
    initial_call = {
        "type": "tool-call",
        "toolCallId": call_id,
        "toolName": "team-formation",
        "args": {
            **server_args,
            "status": "recruiting",
            "progress": 0.1,
            "currentStep": "开始招募小队成员...",
            "members": []
        }
    }
    yield f'0:{json.dumps(initial_call)}\n'
    await asyncio.sleep(0.8)
    
    # Simulate recruitment progress for each member
    current_members = []
    for i, member in enumerate(initial_members):
        current_members.append(member)
        progress = 0.2 + (i + 1) * 0.15
        step = f"已招募 {member['name']} ({member['role']})..."
        
        update_call = {
            "type": "tool-call", 
            "toolCallId": call_id,
            "toolName": "team-formation",
            "args": {
                **server_args,
                "status": "recruiting",
                "progress": progress,
                "currentStep": step,
                "members": current_members.copy()
            }
        }
        yield f'0:{json.dumps(update_call)}\n'
        await asyncio.sleep(0.6)
    
    # Final completion call
    final_call = {
        "type": "tool-call",
        "toolCallId": call_id,
        "toolName": "team-formation", 
        "args": {
            **server_args,
            "status": "completed",
            "progress": 1.0,
            "currentStep": "小队组建完成！",
            "members": current_members,
            "teamStats": {
                "totalMembers": len(current_members),
                "skills": ["AI图片创作", "数据分析", "智能问答", "流程编排"]
            }
        }
    }
    yield f'0:{json.dumps(final_call)}\n'

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        network_status = client.get_network_status()
        sessions = client.get_all_sessions()
        
        total_messages = 0
        for session in sessions:
            total_messages += len(client.get_session_messages(session.id))
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "sessions_count": len(sessions),
            "messages_count": total_messages,
            "isek_node": {
                "status": "connected" if network_status.connected else "disconnected",
                "agents_count": network_status.agents_count,
                "node_id": network_status.node_id
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail={
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
        )

if __name__ == '__main__':
    import uvicorn
    port = int(5001)
    logger.info(f"Starting ISEK UI Backend (FastAPI) on port {port}")
    logger.info("Using native async support with ISEK client integration")
    uvicorn.run(app, host='0.0.0.0', port=port)