#!/usr/bin/env python3
"""
AGUI Middleware Main Application
FastAPI server that provides AGUI-compatible endpoints while using ISEK for backend communication
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
from datetime import datetime

# FastAPI and async support
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
import uvicorn

# Add core modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'core'))

from core.middleware import AGUIMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global middleware instance
middleware: Optional[AGUIMiddleware] = None


# Pydantic models for API
class SendMessageRequest(BaseModel):
    """Request model for sending messages to agents"""
    agent_id: str = Field(..., description="ID of the target agent")
    message: str = Field(..., description="Message content")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class AgentRunRequest(BaseModel):
    """Request model for running agents with AGUI input"""
    agent_id: str = Field(..., description="ID of the agent to run")
    messages: List[Dict[str, Any]] = Field(..., description="List of messages")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Context information")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    middleware: Dict[str, Any]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global middleware
    
    try:
        # Startup
        logger.info("🚀 Starting AGUI Middleware Server...")
        
        # Initialize middleware
        middleware = AGUIMiddleware()
        await middleware.initialize()
        
        logger.info("✅ AGUI Middleware Server started successfully")
        yield
        
    except Exception as e:
        logger.error(f"❌ Failed to start AGUI Middleware: {e}")
        raise
    finally:
        # Shutdown
        if middleware:
            await middleware.shutdown()
        logger.info("🛑 AGUI Middleware Server shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="AGUI-ISEK Middleware",
    description="Middleware that bridges AGUI protocol with ISEK agents via A2A communication",
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


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    if not middleware:
        raise HTTPException(status_code=503, detail="Middleware not initialized")
    
    status = await middleware.get_middleware_status()
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        middleware=status
    )


@app.get("/agents")
async def get_agents():
    """Get list of available agents"""
    if not middleware:
        raise HTTPException(status_code=503, detail="Middleware not initialized")
    
    try:
        agents = await middleware.get_agents()
        return {
            "agents": agents,
            "count": len(agents),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Failed to get agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agents/refresh")
async def refresh_agents():
    """Refresh the list of available agents"""
    if not middleware:
        raise HTTPException(status_code=503, detail="Middleware not initialized")
    
    try:
        await middleware.refresh_agents()
        agents = await middleware.get_agents()
        
        return {
            "message": "Agents refreshed successfully",
            "agents": agents,
            "count": len(agents),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Failed to refresh agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agents/{agent_id}/message")
async def send_message_to_agent(agent_id: str, request: SendMessageRequest):
    """Send a message to a specific agent"""
    if not middleware:
        raise HTTPException(status_code=503, detail="Middleware not initialized")
    
    try:
        logger.info(f"📤 Sending message to agent {agent_id}: {request.message[:100]}...")
        
        response = await middleware.send_message_to_agent(
            agent_id=agent_id,
            message=request.message,
            session_id=request.session_id
        )
        
        if response.get("success"):
            return {
                "success": True,
                "agent_id": agent_id,
                "response": response.get("response"),
                "session_id": request.session_id,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to send message: {response.get('error', 'Unknown error')}"
            )
            
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Failed to send message to agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agents/{agent_id}/run")
async def run_agent(agent_id: str, request: AgentRunRequest):
    """Run an agent with AGUI-compatible input"""
    if not middleware:
        raise HTTPException(status_code=503, detail="Middleware not initialized")
    
    try:
        logger.info(f"🚀 Running agent {agent_id} with AGUI input...")
        
        # Prepare AGUI input format
        agui_input = {
            "messages": request.messages,
            "context": request.context,
            "session_id": request.context.get("session_id", "default")
        }
        
        events = await middleware.run_agent(agent_id, agui_input)
        
        return {
            "success": True,
            "agent_id": agent_id,
            "events": events,
            "events_count": len(events),
            "timestamp": datetime.now().isoformat()
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Failed to run agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agents/{agent_id}/status")
async def get_agent_status(agent_id: str):
    """Get status of a specific agent"""
    if not middleware:
        raise HTTPException(status_code=503, detail="Middleware not initialized")
    
    try:
        agents = await middleware.get_agents()
        
        for agent in agents:
            if agent["id"] == agent_id:
                return {
                    "agent": agent,
                    "timestamp": datetime.now().isoformat()
                }
        
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get agent status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
async def get_middleware_status():
    """Get detailed middleware status"""
    if not middleware:
        raise HTTPException(status_code=503, detail="Middleware not initialized")
    
    try:
        status = await middleware.get_middleware_status()
        return status
    except Exception as e:
        logger.error(f"❌ Failed to get middleware status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# AGUI-compatible endpoints (following AGUI conventions)
@app.post("/agui/agents")
async def agui_get_agents():
    """AGUI-compatible agents endpoint"""
    return await get_agents()


@app.post("/agui/agents/{agent_id}/run")
async def agui_run_agent(agent_id: str, request: AgentRunRequest):
    """AGUI-compatible agent run endpoint"""
    return await run_agent(agent_id, request)


# Test endpoint for development
@app.get("/test")
async def test_endpoint():
    """Test endpoint for debugging"""
    return {
        "message": "AGUI-ISEK Middleware is running",
        "timestamp": datetime.now().isoformat(),
        "middleware_initialized": middleware is not None,
        "endpoints": [
            "/health",
            "/agents",
            "/agents/refresh",
            "/agents/{agent_id}/message",
            "/agents/{agent_id}/run",
            "/agents/{agent_id}/status",
            "/status",
            "/agui/agents",
            "/agui/agents/{agent_id}/run"
        ]
    }


def main():
    """Main entry point"""
    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")
    reload = os.getenv("RELOAD", "false").lower() == "true"
    
    logger.info(f"🚀 Starting AGUI-ISEK Middleware on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()