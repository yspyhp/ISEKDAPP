"""
AGUI Middleware HTTP API
FastAPI application that provides AGUI-compatible frontend communication endpoints
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import uvicorn

# AGUI Middleware components
from ..services.agui_service import AGUIService, AGUIRequest
from ..adapters.agui_adapter import AGUIAdapter
from ..core.isek_client import ISEKClient, ISEKNodeConfig

logger = logging.getLogger(__name__)

# Pydantic models for API
class ChatMessage(BaseModel):
    """Chat message compatible with AGUI frontend"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    role: str = Field(default="user", description="Message role: user, assistant, system")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

class SendMessageRequest(BaseModel):
    """Send message request from frontend"""
    agentId: str = Field(description="Target agent ID")
    address: str = Field(description="Agent node address")
    sessionId: str = Field(description="Session ID")
    messages: List[ChatMessage] = Field(default_factory=list)
    system: Optional[str] = Field(None, description="System prompt")

class ChatSession(BaseModel):
    """Chat session model"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    agentId: str
    agentName: str
    agentDescription: str
    agentAddress: str
    createdAt: str = Field(default_factory=lambda: datetime.now().isoformat())
    updatedAt: str = Field(default_factory=lambda: datetime.now().isoformat())
    messageCount: int = 0

class AgentInfo(BaseModel):
    """Agent information model"""
    name: str
    node_id: str
    bio: str
    lore: str
    knowledge: str
    routine: str
    status: str = "available"
    url: str = ""

class NetworkStatus(BaseModel):
    """Network status model"""
    connected: bool
    nodeCount: int
    activeAgents: int
    lastChecked: str


class AGUIMiddlewareAPI:
    """AGUI Middleware FastAPI Application"""
    
    def __init__(self):
        self.app = FastAPI(
            title="AGUI Middleware API",
            description="HTTP API for AGUI frontend communication with ISEK agents",
            version="1.0.0"
        )
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure based on your frontend
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Service components
        self.agui_service: Optional[AGUIService] = None
        self.isek_client: Optional[ISEKClient] = None
        self.sessions: Dict[str, ChatSession] = {}
        
        # Register routes
        self._setup_routes()
    
    async def initialize(self, isek_config: ISEKNodeConfig):
        """Initialize the middleware with ISEK configuration"""
        try:
            logger.info("🔧 Initializing AGUI Middleware API...")
            
            # Create AGUI adapter
            agui_adapter = AGUIAdapter({
                "registry": {
                    "host": isek_config.registry_host,
                    "port": isek_config.registry_port
                }
            })
            await agui_adapter.initialize()
            
            # Create service with adapter registry
            adapter_registry = {"agui": agui_adapter}
            self.agui_service = AGUIService(adapter_registry)
            
            # Create ISEK client for network operations
            self.isek_client = ISEKClient(isek_config, self._middleware_callback)
            await self.isek_client.initialize()
            
            logger.info("✅ AGUI Middleware API initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize AGUI Middleware API: {e}")
            raise
    
    async def _middleware_callback(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Callback for ISEK client integration"""
        # This is called when A2A messages are received
        # Convert to AGUI format and process
        return {"content": f"Processed: {context.get('message', '')}"}
    
    def _setup_routes(self):
        """Setup API routes"""
        
        @self.app.get("/api/agents", response_model=List[AgentInfo])
        async def get_agents():
            """Get list of available agents"""
            try:
                if not self.agui_service:
                    raise HTTPException(status_code=503, detail="Service not initialized")
                
                agents = await self.agui_service.get_available_agents()
                
                # Convert to frontend format
                agent_list = []
                for agent in agents:
                    agent_info = AgentInfo(
                        name=agent.get("name", agent["id"]),
                        node_id=agent["id"],
                        bio=agent.get("description", ""),
                        lore=agent.get("description", ""),
                        knowledge=", ".join(agent.get("capabilities", {}).keys()),
                        routine="Agent processing routine",
                        status=agent.get("status", "available"),
                        url=agent.get("url", "")
                    )
                    agent_list.append(agent_info)
                
                return agent_list
                
            except Exception as e:
                logger.error(f"❌ Failed to get agents: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/agents/{agent_id}", response_model=AgentInfo)
        async def get_agent(agent_id: str):
            """Get specific agent details"""
            try:
                if not self.agui_service:
                    raise HTTPException(status_code=503, detail="Service not initialized")
                
                status = await self.agui_service.get_agent_status(agent_id)
                
                if "error" in status:
                    raise HTTPException(status_code=404, detail=status["error"])
                
                return AgentInfo(
                    name=status.get("name", agent_id),
                    node_id=agent_id,
                    bio=status.get("description", ""),
                    lore=status.get("description", ""),
                    knowledge="Available capabilities",
                    routine="Agent processing routine",
                    status=status.get("status", "available"),
                    url=status.get("url", "")
                )
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"❌ Failed to get agent {agent_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/sessions", response_model=List[ChatSession])
        async def get_sessions():
            """Get all chat sessions"""
            return list(self.sessions.values())
        
        @self.app.post("/api/sessions", response_model=ChatSession)
        async def create_session(agentId: str, title: str = None):
            """Create new chat session"""
            try:
                if not title:
                    title = f"Chat with {agentId}"
                
                # Get agent info
                if not self.agui_service:
                    raise HTTPException(status_code=503, detail="Service not initialized")
                
                status = await self.agui_service.get_agent_status(agentId)
                
                session = ChatSession(
                    title=title,
                    agentId=agentId,
                    agentName=status.get("name", agentId),
                    agentDescription=status.get("description", ""),
                    agentAddress=status.get("url", "")
                )
                
                self.sessions[session.id] = session
                
                logger.info(f"✅ Created session {session.id} for agent {agentId}")
                return session
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"❌ Failed to create session: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/sessions/{session_id}", response_model=ChatSession)
        async def get_session(session_id: str):
            """Get specific session"""
            if session_id not in self.sessions:
                raise HTTPException(status_code=404, detail="Session not found")
            return self.sessions[session_id]
        
        @self.app.delete("/api/sessions/{session_id}")
        async def delete_session(session_id: str):
            """Delete session"""
            if session_id in self.sessions:
                del self.sessions[session_id]
                return {"success": True}
            raise HTTPException(status_code=404, detail="Session not found")
        
        @self.app.post("/api/chat")
        async def send_message(request: SendMessageRequest):
            """Send message to agent with streaming response"""
            try:
                if not self.agui_service:
                    raise HTTPException(status_code=503, detail="Service not initialized")
                
                # Create AGUI request
                agui_request = AGUIRequest(
                    agent_id=request.agentId,
                    messages=[msg.dict() for msg in request.messages],
                    context={"system": request.system} if request.system else {},
                    session_id=request.sessionId,
                    user_id="default"
                )
                
                # Process and stream response
                return StreamingResponse(
                    self._create_streaming_response(agui_request),
                    media_type='text/plain; charset=utf-8',
                    headers={
                        'Cache-Control': 'no-cache',
                        'Connection': 'keep-alive',
                        'x-vercel-ai-data-stream': 'v1'
                    }
                )
                
            except Exception as e:
                logger.error(f"❌ Failed to send message: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/network/status", response_model=NetworkStatus)
        async def get_network_status():
            """Get ISEK network status"""
            try:
                if not self.isek_client:
                    return NetworkStatus(
                        connected=False,
                        nodeCount=0,
                        activeAgents=0,
                        lastChecked=datetime.now().isoformat()
                    )
                
                agents = await self.isek_client.get_agent_list()
                
                return NetworkStatus(
                    connected=True,
                    nodeCount=1,  # This node
                    activeAgents=len(agents),
                    lastChecked=datetime.now().isoformat()
                )
                
            except Exception as e:
                logger.error(f"❌ Failed to get network status: {e}")
                return NetworkStatus(
                    connected=False,
                    nodeCount=0,
                    activeAgents=0,
                    lastChecked=datetime.now().isoformat()
                )
    
    async def _create_streaming_response(self, agui_request: AGUIRequest) -> AsyncGenerator[str, None]:
        """Create streaming response compatible with Vercel AI SDK"""
        try:
            # Stream events from AGUI service
            async for event in self.agui_service.stream_agui_request(agui_request):
                # Convert AGUI events to Vercel AI SDK format
                if hasattr(event, 'type'):
                    event_type = getattr(event, 'type', 'unknown')
                else:
                    event_type = event.get('type', 'unknown')
                
                if event_type == 'message' or 'message' in str(type(event)).lower():
                    # Extract content
                    if hasattr(event, 'content'):
                        content = event.content
                    elif hasattr(event, 'data') and 'content' in event.data:
                        content = event.data['content']
                    else:
                        content = str(event)
                    
                    # Send as text chunk
                    chunk = {
                        "type": "text",
                        "text": content
                    }
                    yield f'0:{{"type":"text","text":"{content}"}}\n'
                
                elif event_type == 'agent_run_finished':
                    # Send completion
                    yield 'd:{"finishReason":"stop","usage":{"completionTokens":0,"promptTokens":0,"totalTokens":0}}\n'
                
                elif event_type == 'agent_run_error':
                    # Send error
                    error_msg = getattr(event, 'error', str(event))
                    yield f'd:{{"finishReason":"error","error":"{error_msg}"}}\n'
                    
        except Exception as e:
            logger.error(f"❌ Streaming error: {e}")
            yield f'd:{{"finishReason":"error","error":"{str(e)}"}}\n'


# Global API instance
api = AGUIMiddlewareAPI()

# FastAPI app for uvicorn
app = api.app

async def startup():
    """Startup event handler"""
    # Initialize with default configuration
    config = ISEKNodeConfig(
        node_id="agui_middleware_node",
        host="0.0.0.0",
        port=8082,
        registry_host="47.236.116.81",
        registry_port=2379
    )
    await api.initialize(config)

@app.on_event("startup")
async def startup_event():
    await startup()

if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8083,
        reload=True,
        log_level="info"
    )