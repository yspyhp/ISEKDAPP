"""
ISEK Agent Wrapper for AGUI
Wraps ISEK agents to be compatible with AGUI protocol
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass
from datetime import datetime

# Try to import AGUI SDK components
try:
    from ag_ui.core import Agent, RunAgentInput, Message
    AGUI_AVAILABLE = True
except ImportError:
    # Fallback if AGUI SDK not available
    AGUI_AVAILABLE = False
    
    class Agent:
        """Fallback Agent base class"""
        async def run(self, input_data):
            raise NotImplementedError("Override this method")

logger = logging.getLogger(__name__)


@dataclass
class ISEKAgentInfo:
    """Information about an ISEK agent"""
    id: str
    name: str
    description: str
    url: str
    capabilities: Dict[str, Any]
    status: str = "available"


class ISEKAgentWrapper(Agent if AGUI_AVAILABLE else object):
    """Wrapper that makes ISEK agents compatible with AGUI protocol"""
    
    def __init__(self, agent_info: ISEKAgentInfo, isek_client):
        if AGUI_AVAILABLE:
            super().__init__()
        
        self.agent_info = agent_info
        self.isek_client = isek_client
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        
    @property
    def id(self) -> str:
        """Agent ID"""
        return self.agent_info.id
    
    @property
    def name(self) -> str:
        """Agent name"""
        return self.agent_info.name
    
    @property
    def description(self) -> str:
        """Agent description"""
        return self.agent_info.description
    
    async def run(self, input_data: Any) -> AsyncGenerator[Any, None]:
        """
        Run the ISEK agent with AGUI-compatible input/output
        """
        try:
            run_id = str(uuid.uuid4())
            session_id = None
            
            # Extract session information
            if hasattr(input_data, 'context'):
                session_id = getattr(input_data.context, 'session_id', str(uuid.uuid4()))
            elif isinstance(input_data, dict):
                session_id = input_data.get('session_id', str(uuid.uuid4()))
            else:
                session_id = str(uuid.uuid4())
            
            # Track session
            self.active_sessions[session_id] = {
                "run_id": run_id,
                "started_at": datetime.now(),
                "agent_id": self.agent_info.id,
                "status": "running"
            }
            
            logger.info(f"🚀 Starting ISEK agent run: {self.agent_info.id} (session: {session_id})")
            
            # Yield run started event
            yield self._create_run_started_event(run_id, input_data)
            
            # Extract message content
            message_text = self._extract_message_content(input_data)
            
            # Send A2A message to ISEK agent
            logger.info(f"📤 Sending A2A message to {self.agent_info.id}: {message_text[:100]}...")
            
            a2a_response = await self.isek_client.send_a2a_message(
                agent_id=self.agent_info.id,
                message=message_text,
                session_id=session_id
            )
            
            if a2a_response.get("success"):
                # Process successful response
                response_data = a2a_response.get("response", {})
                
                # Extract response content
                if "result" in response_data:
                    # Successful A2A response
                    task_info = response_data["result"]
                    task_id = task_info.get("id", "unknown")
                    task_status = task_info.get("status", {}).get("state", "unknown")
                    
                    logger.info(f"✅ A2A response received: task {task_id} ({task_status})")
                    
                    # Yield message event with task information
                    yield self._create_message_event(
                        content=f"Task created: {task_id} (Status: {task_status})",
                        role="assistant"
                    )
                    
                    # For now, yield completion - in real implementation, 
                    # you might want to poll for task completion
                    yield self._create_run_finished_event(run_id, {
                        "task_id": task_id,
                        "status": task_status,
                        "agent_id": self.agent_info.id
                    })
                    
                elif "error" in response_data:
                    # A2A error response
                    error_info = response_data["error"]
                    error_message = error_info.get("message", "Unknown A2A error")
                    
                    logger.error(f"❌ A2A error from {self.agent_info.id}: {error_message}")
                    
                    yield self._create_error_event(run_id, f"A2A Error: {error_message}")
                
                else:
                    # Unexpected response format
                    logger.warning(f"⚠️ Unexpected A2A response format: {response_data}")
                    yield self._create_message_event(
                        content=f"Received response from {self.agent_info.name}: {str(response_data)}",
                        role="assistant"
                    )
                    yield self._create_run_finished_event(run_id, response_data)
            
            else:
                # A2A communication failed
                error_message = a2a_response.get("error", "Unknown communication error")
                logger.error(f"❌ Failed to communicate with {self.agent_info.id}: {error_message}")
                
                yield self._create_error_event(run_id, f"Communication failed: {error_message}")
            
            # Update session status
            if session_id in self.active_sessions:
                self.active_sessions[session_id]["status"] = "completed"
                self.active_sessions[session_id]["completed_at"] = datetime.now()
            
        except Exception as e:
            logger.error(f"❌ Error in ISEK agent run: {e}")
            yield self._create_error_event(run_id, str(e))
            
            # Update session status
            if session_id in self.active_sessions:
                self.active_sessions[session_id]["status"] = "error"
                self.active_sessions[session_id]["error"] = str(e)
    
    def _extract_message_content(self, input_data: Any) -> str:
        """Extract message content from AGUI input"""
        try:
            if AGUI_AVAILABLE and hasattr(input_data, 'messages'):
                # AGUI RunAgentInput with messages
                messages = input_data.messages
                if messages:
                    # Get the last user message
                    for msg in reversed(messages):
                        if msg.role == "user":
                            return msg.content
                    # Fallback to first message
                    return messages[0].content if messages else ""
            elif isinstance(input_data, dict):
                # Dictionary format
                if "messages" in input_data:
                    messages = input_data["messages"]
                    if messages:
                        return messages[-1].get("content", "")
                elif "message" in input_data:
                    return str(input_data["message"])
                elif "content" in input_data:
                    return str(input_data["content"])
            elif isinstance(input_data, str):
                # Direct string
                return input_data
            
            # Fallback
            return str(input_data)
            
        except Exception as e:
            logger.error(f"❌ Failed to extract message content: {e}")
            return "Unable to extract message content"
    
    def _create_run_started_event(self, run_id: str, input_data: Any) -> Dict[str, Any]:
        """Create run started event"""
        if AGUI_AVAILABLE:
            # Use actual AGUI event if available
            try:
                from ag_ui.core import AgentRunStartedEvent
                return AgentRunStartedEvent(
                    id=run_id,
                    timestamp=datetime.now(),
                    run_input=input_data
                )
            except ImportError:
                pass
        
        # Fallback event
        return {
            "type": "agent_run_started",
            "id": run_id,
            "timestamp": datetime.now().isoformat(),
            "agent_id": self.agent_info.id,
            "agent_name": self.agent_info.name,
            "data": {"input": str(input_data)}
        }
    
    def _create_message_event(self, content: str, role: str = "assistant") -> Dict[str, Any]:
        """Create message event"""
        if AGUI_AVAILABLE:
            try:
                from ag_ui.core import MessageEvent
                return MessageEvent(
                    id=str(uuid.uuid4()),
                    timestamp=datetime.now(),
                    content=content,
                    role=role
                )
            except ImportError:
                pass
        
        # Fallback event
        return {
            "type": "message",
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "agent_id": self.agent_info.id,
            "data": {
                "content": content,
                "role": role
            }
        }
    
    def _create_run_finished_event(self, run_id: str, result: Any) -> Dict[str, Any]:
        """Create run finished event"""
        if AGUI_AVAILABLE:
            try:
                from ag_ui.core import AgentRunFinishedEvent
                return AgentRunFinishedEvent(
                    id=run_id,
                    timestamp=datetime.now(),
                    result=result
                )
            except ImportError:
                pass
        
        # Fallback event
        return {
            "type": "agent_run_finished",
            "id": run_id,
            "timestamp": datetime.now().isoformat(),
            "agent_id": self.agent_info.id,
            "data": {"result": result}
        }
    
    def _create_error_event(self, run_id: str, error_message: str) -> Dict[str, Any]:
        """Create error event"""
        if AGUI_AVAILABLE:
            try:
                from ag_ui.core import AgentRunErrorEvent
                return AgentRunErrorEvent(
                    id=run_id,
                    timestamp=datetime.now(),
                    error=error_message
                )
            except ImportError:
                pass
        
        # Fallback event
        return {
            "type": "agent_run_error",
            "id": run_id,
            "timestamp": datetime.now().isoformat(),
            "agent_id": self.agent_info.id,
            "data": {"error": error_message}
        }
    
    async def get_capabilities(self) -> Dict[str, Any]:
        """Get agent capabilities"""
        return self.agent_info.capabilities
    
    async def get_status(self) -> str:
        """Get agent status"""
        return self.agent_info.status
    
    def get_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get active sessions for this agent"""
        return self.active_sessions.copy()
    
    def cleanup_old_sessions(self, max_age_minutes: int = 60):
        """Clean up old sessions"""
        cutoff_time = datetime.now().timestamp() - (max_age_minutes * 60)
        
        sessions_to_remove = []
        for session_id, session_info in self.active_sessions.items():
            if session_info["started_at"].timestamp() < cutoff_time:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del self.active_sessions[session_id]
            logger.info(f"🧹 Cleaned up old session: {session_id}")
        
        return len(sessions_to_remove)