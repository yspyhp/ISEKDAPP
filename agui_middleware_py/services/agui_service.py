"""
AGUI Service Layer
Handles AGUI protocol communication from frontend and routes to appropriate adapters
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass
from datetime import datetime

# Try to import AGUI SDK components
try:
    from ag_ui.core import (
        RunAgentInput, Message, Context, Agent,
        AgentRunStartedEvent, AgentRunFinishedEvent, AgentRunErrorEvent,
        MessageEvent, ToolCallEvent, StateUpdateEvent
    )
    AGUI_AVAILABLE = True
except ImportError:
    AGUI_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class AGUIRequest:
    """AGUI request structure"""
    agent_id: str
    messages: List[Dict[str, Any]]
    context: Dict[str, Any]
    session_id: str
    user_id: str = "default"
    request_id: str = None
    
    def __post_init__(self):
        if self.request_id is None:
            self.request_id = str(uuid.uuid4())


@dataclass
class AGUIResponse:
    """AGUI response structure"""
    request_id: str
    events: List[Any]
    status: str
    agent_id: str
    session_id: str
    timestamp: datetime
    error: Optional[str] = None


class AGUIService:
    """
    AGUI Service Layer
    
    Architecture:
    Frontend → AGUI → Service (this) → Adapter → Translator → Node → Server
    """
    
    def __init__(self, adapter_registry):
        """
        Initialize AGUI Service
        
        Args:
            adapter_registry: Registry of available adapters
        """
        self.adapter_registry = adapter_registry
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.request_history: Dict[str, AGUIRequest] = {}
        
    async def process_agui_request(self, agui_request: AGUIRequest) -> AGUIResponse:
        """
        Process AGUI request from frontend
        
        Args:
            agui_request: AGUI request containing agent_id, messages, context
            
        Returns:
            AGUIResponse: Processed response with events
        """
        try:
            logger.info(f"🔄 Processing AGUI request for agent: {agui_request.agent_id}")
            
            # Store request for tracking
            self.request_history[agui_request.request_id] = agui_request
            
            # Update session tracking
            await self._update_session_tracking(agui_request)
            
            # Get appropriate adapter for the agent
            adapter = await self._get_adapter_for_agent(agui_request.agent_id)
            
            if not adapter:
                raise ValueError(f"No adapter found for agent: {agui_request.agent_id}")
            
            # Convert AGUI request to adapter format
            adapter_input = await self._convert_agui_to_adapter_input(agui_request)
            
            # Process through adapter
            logger.info(f"📤 Sending to adapter: {adapter.__class__.__name__}")
            events = []
            
            async for event in adapter.process_agui_request(adapter_input):
                events.append(event)
                logger.debug(f"📨 Received event: {type(event).__name__}")
            
            # Create response
            response = AGUIResponse(
                request_id=agui_request.request_id,
                events=events,
                status="completed",
                agent_id=agui_request.agent_id,
                session_id=agui_request.session_id,
                timestamp=datetime.now()
            )
            
            logger.info(f"✅ AGUI request processed successfully: {len(events)} events")
            return response
            
        except Exception as e:
            logger.error(f"❌ Failed to process AGUI request: {e}")
            
            # Create error response
            return AGUIResponse(
                request_id=agui_request.request_id,
                events=[self._create_error_event(str(e))],
                status="error",
                agent_id=agui_request.agent_id,
                session_id=agui_request.session_id,
                timestamp=datetime.now(),
                error=str(e)
            )
    
    async def stream_agui_request(self, agui_request: AGUIRequest) -> AsyncGenerator[Any, None]:
        """
        Stream AGUI request processing (for real-time responses)
        
        Args:
            agui_request: AGUI request
            
        Yields:
            AGUI events as they are processed
        """
        try:
            logger.info(f"🌊 Streaming AGUI request for agent: {agui_request.agent_id}")
            
            # Store request
            self.request_history[agui_request.request_id] = agui_request
            
            # Update session
            await self._update_session_tracking(agui_request)
            
            # Get adapter
            adapter = await self._get_adapter_for_agent(agui_request.agent_id)
            
            if not adapter:
                yield self._create_error_event(f"No adapter found for agent: {agui_request.agent_id}")
                return
            
            # Convert and stream
            adapter_input = await self._convert_agui_to_adapter_input(agui_request)
            
            async for event in adapter.process_agui_request(adapter_input):
                yield event
                
        except Exception as e:
            logger.error(f"❌ Failed to stream AGUI request: {e}")
            yield self._create_error_event(str(e))
    
    async def get_available_agents(self) -> List[Dict[str, Any]]:
        """
        Get list of available agents from all registered adapters
        
        Returns:
            List of agent information
        """
        try:
            agents = []
            
            for adapter_name, adapter in self.adapter_registry.items():
                if hasattr(adapter, 'get_available_agents'):
                    adapter_agents = await adapter.get_available_agents()
                    
                    for agent in adapter_agents:
                        agent['adapter'] = adapter_name
                        agents.append(agent)
            
            logger.info(f"✅ Found {len(agents)} available agents")
            return agents
            
        except Exception as e:
            logger.error(f"❌ Failed to get available agents: {e}")
            return []
    
    async def get_agent_status(self, agent_id: str) -> Dict[str, Any]:
        """
        Get status of specific agent
        
        Args:
            agent_id: ID of the agent
            
        Returns:
            Agent status information
        """
        try:
            # Find adapter that handles this agent
            for adapter_name, adapter in self.adapter_registry.items():
                if hasattr(adapter, 'get_agent_status'):
                    status = await adapter.get_agent_status(agent_id)
                    if status:
                        status['adapter'] = adapter_name
                        return status
            
            return {"error": f"Agent {agent_id} not found"}
            
        except Exception as e:
            logger.error(f"❌ Failed to get agent status: {e}")
            return {"error": str(e)}
    
    async def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """
        Get information about a session
        
        Args:
            session_id: Session ID
            
        Returns:
            Session information
        """
        return self.active_sessions.get(session_id, {})
    
    async def _update_session_tracking(self, agui_request: AGUIRequest):
        """Update session tracking information"""
        session_id = agui_request.session_id
        
        if session_id not in self.active_sessions:
            self.active_sessions[session_id] = {
                "session_id": session_id,
                "user_id": agui_request.user_id,
                "created_at": datetime.now(),
                "last_activity": datetime.now(),
                "request_count": 0,
                "agents_used": set()
            }
        
        session = self.active_sessions[session_id]
        session["last_activity"] = datetime.now()
        session["request_count"] += 1
        session["agents_used"].add(agui_request.agent_id)
    
    async def _get_adapter_for_agent(self, agent_id: str):
        """Get the appropriate adapter for an agent"""
        # Try to find adapter that can handle this agent
        for adapter_name, adapter in self.adapter_registry.items():
            if hasattr(adapter, 'can_handle_agent'):
                if await adapter.can_handle_agent(agent_id):
                    return adapter
            elif hasattr(adapter, 'get_available_agents'):
                # Check if agent is in adapter's agent list
                agents = await adapter.get_available_agents()
                for agent in agents:
                    if agent.get('id') == agent_id:
                        return adapter
        
        # Default to first available adapter
        if self.adapter_registry:
            return next(iter(self.adapter_registry.values()))
        
        return None
    
    async def _convert_agui_to_adapter_input(self, agui_request: AGUIRequest) -> Dict[str, Any]:
        """Convert AGUI request to adapter input format"""
        return {
            "agent_id": agui_request.agent_id,
            "messages": agui_request.messages,
            "context": agui_request.context,
            "session_id": agui_request.session_id,
            "user_id": agui_request.user_id,
            "request_id": agui_request.request_id,
            "timestamp": datetime.now().isoformat()
        }
    
    def _create_error_event(self, error_message: str) -> Dict[str, Any]:
        """Create an error event"""
        if AGUI_AVAILABLE:
            try:
                from ag_ui.core import AgentRunErrorEvent
                return AgentRunErrorEvent(
                    id=str(uuid.uuid4()),
                    timestamp=datetime.now(),
                    error=error_message
                )
            except ImportError:
                pass
        
        # Fallback error event
        return {
            "type": "agent_run_error",
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "data": {"error": error_message}
        }
    
    async def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Clean up old sessions"""
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        
        sessions_to_remove = []
        for session_id, session_info in self.active_sessions.items():
            if session_info["last_activity"].timestamp() < cutoff_time:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del self.active_sessions[session_id]
            logger.info(f"🧹 Cleaned up old session: {session_id}")
        
        return len(sessions_to_remove)
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            "active_sessions": len(self.active_sessions),
            "total_requests": len(self.request_history),
            "registered_adapters": list(self.adapter_registry.keys()),
            "uptime": datetime.now().isoformat()
        }