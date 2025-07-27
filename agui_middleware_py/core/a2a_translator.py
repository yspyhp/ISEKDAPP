"""
A2A to AGUI Protocol Translator
Converts between A2A protocol messages and AGUI events/types
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
        RunAgentInput, Message, Context, Tool, State,
        # Events
        AgentRunStartedEvent, AgentRunFinishedEvent, AgentRunErrorEvent,
        MessageEvent, ToolCallEvent, StateUpdateEvent
    )
    AGUI_AVAILABLE = True
except ImportError:
    # Fallback types if AGUI SDK not available
    AGUI_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("AGUI SDK not available, using fallback types")

logger = logging.getLogger(__name__)


@dataclass
class AGUIMessage:
    """AGUI Message structure (fallback if SDK not available)"""
    id: str
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = None


@dataclass
class AGUIRunInput:
    """AGUI Run Input structure (fallback)"""
    messages: List[AGUIMessage]
    context: Dict[str, Any]
    agent_id: str
    session_id: str


@dataclass
class AGUIEvent:
    """Base AGUI Event structure (fallback)"""
    type: str
    id: str
    timestamp: datetime
    data: Dict[str, Any]


class A2AAGUITranslator:
    """Translates between A2A protocol and AGUI events"""
    
    def __init__(self):
        self.active_runs: Dict[str, Dict[str, Any]] = {}
        
    def a2a_to_agui_input(self, a2a_context: Dict[str, Any]) -> Dict[str, Any]:
        """Convert A2A context to AGUI RunAgentInput"""
        try:
            # Extract A2A message information
            message_text = a2a_context.get("message", "")
            session_id = a2a_context.get("session_id", str(uuid.uuid4()))
            user_id = a2a_context.get("user_id", "default")
            metadata = a2a_context.get("metadata", {})
            
            # Create AGUI message
            if AGUI_AVAILABLE:
                agui_message = Message(
                    id=str(uuid.uuid4()),
                    role="user",
                    content=message_text,
                    timestamp=datetime.now()
                )
                
                agui_context = Context(
                    session_id=session_id,
                    user_id=user_id,
                    metadata=metadata
                )
                
                run_input = RunAgentInput(
                    messages=[agui_message],
                    context=agui_context
                )
            else:
                # Fallback structure
                agui_message = AGUIMessage(
                    id=str(uuid.uuid4()),
                    role="user",
                    content=message_text,
                    timestamp=datetime.now(),
                    metadata=metadata
                )
                
                run_input = AGUIRunInput(
                    messages=[agui_message],
                    context={
                        "session_id": session_id,
                        "user_id": user_id,
                        "metadata": metadata
                    },
                    agent_id=metadata.get("target_agent_id", "unknown"),
                    session_id=session_id
                )
            
            return {
                "run_input": run_input,
                "session_id": session_id,
                "user_id": user_id,
                "original_a2a": a2a_context
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to convert A2A to AGUI input: {e}")
            raise
    
    def agui_to_a2a_response(self, agui_response: Any, session_id: str) -> Dict[str, Any]:
        """Convert AGUI response to A2A format"""
        try:
            # Handle different types of AGUI responses
            if isinstance(agui_response, str):
                # Simple text response
                return {
                    "content": agui_response,
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "type": "text_message"
                }
            elif isinstance(agui_response, dict):
                # Structured response
                return {
                    "content": agui_response.get("content", ""),
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "type": agui_response.get("type", "text_message"),
                    "metadata": agui_response.get("metadata", {})
                }
            else:
                # Unknown response type
                return {
                    "content": str(agui_response),
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "type": "unknown"
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to convert AGUI to A2A response: {e}")
            return {
                "content": f"Error processing response: {e}",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "type": "error"
            }
    
    async def create_agui_events_from_a2a(self, a2a_context: Dict[str, Any]) -> AsyncGenerator[Any, None]:
        """Create AGUI event stream from A2A context"""
        try:
            run_id = str(uuid.uuid4())
            session_id = a2a_context.get("session_id", str(uuid.uuid4()))
            
            # Track this run
            self.active_runs[run_id] = {
                "session_id": session_id,
                "started_at": datetime.now(),
                "a2a_context": a2a_context
            }
            
            # 1. Emit run started event
            if AGUI_AVAILABLE:
                yield AgentRunStartedEvent(
                    id=run_id,
                    timestamp=datetime.now(),
                    run_input=self.a2a_to_agui_input(a2a_context)["run_input"]
                )
            else:
                yield AGUIEvent(
                    type="agent_run_started",
                    id=run_id,
                    timestamp=datetime.now(),
                    data={"session_id": session_id}
                )
            
            # 2. Process the A2A message and create response
            # This would typically involve calling the actual agent
            message_text = a2a_context.get("message", "")
            
            # For demonstration, create a simple echo response
            # In real implementation, this would call the actual AGUI agent
            response_text = f"Processed A2A message: {message_text}"
            
            # 3. Emit message event
            if AGUI_AVAILABLE:
                yield MessageEvent(
                    id=str(uuid.uuid4()),
                    timestamp=datetime.now(),
                    content=response_text,
                    role="assistant"
                )
            else:
                yield AGUIEvent(
                    type="message",
                    id=str(uuid.uuid4()),
                    timestamp=datetime.now(),
                    data={
                        "content": response_text,
                        "role": "assistant",
                        "session_id": session_id
                    }
                )
            
            # 4. Emit run finished event
            if AGUI_AVAILABLE:
                yield AgentRunFinishedEvent(
                    id=run_id,
                    timestamp=datetime.now(),
                    result={"content": response_text}
                )
            else:
                yield AGUIEvent(
                    type="agent_run_finished",
                    id=run_id,
                    timestamp=datetime.now(),
                    data={
                        "result": {"content": response_text},
                        "session_id": session_id
                    }
                )
            
            # Clean up
            if run_id in self.active_runs:
                del self.active_runs[run_id]
                
        except Exception as e:
            logger.error(f"❌ Failed to create AGUI events from A2A: {e}")
            
            # Emit error event
            if AGUI_AVAILABLE:
                yield AgentRunErrorEvent(
                    id=run_id,
                    timestamp=datetime.now(),
                    error=str(e)
                )
            else:
                yield AGUIEvent(
                    type="agent_run_error",
                    id=run_id,
                    timestamp=datetime.now(),
                    data={"error": str(e)}
                )
    
    def extract_message_content(self, a2a_request: Dict[str, Any]) -> str:
        """Extract message content from A2A request"""
        try:
            params = a2a_request.get("params", {})
            message = params.get("message", {})
            
            # Handle different A2A message formats
            if "parts" in message:
                # Multi-part message
                text_parts = []
                for part in message["parts"]:
                    if part.get("kind") == "text":
                        text_parts.append(part.get("text", ""))
                return " ".join(text_parts)
            elif "content" in message:
                # Simple content message
                return str(message["content"])
            elif "text" in message:
                # Direct text message
                return str(message["text"])
            else:
                # Fallback
                return str(message)
                
        except Exception as e:
            logger.error(f"❌ Failed to extract message content: {e}")
            return ""
    
    def create_a2a_response(self, agui_events: List[Any], request_id: str) -> Dict[str, Any]:
        """Create A2A JSON-RPC response from AGUI events"""
        try:
            # Extract content from events
            content_parts = []
            final_result = None
            
            for event in agui_events:
                if AGUI_AVAILABLE:
                    if isinstance(event, MessageEvent):
                        content_parts.append(event.content)
                    elif isinstance(event, AgentRunFinishedEvent):
                        final_result = event.result
                else:
                    # Fallback handling
                    if event.type == "message":
                        content_parts.append(event.data.get("content", ""))
                    elif event.type == "agent_run_finished":
                        final_result = event.data.get("result")
            
            # Combine content
            if content_parts:
                combined_content = " ".join(content_parts)
            elif final_result and "content" in final_result:
                combined_content = final_result["content"]
            else:
                combined_content = "No response generated"
            
            # Create A2A response
            return {
                "jsonrpc": "2.0",
                "result": {
                    "id": str(uuid.uuid4()),
                    "content": combined_content,
                    "timestamp": datetime.now().isoformat(),
                    "events_processed": len(agui_events)
                },
                "id": request_id
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to create A2A response: {e}")
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {e}"
                },
                "id": request_id
            }
    
    def get_active_runs(self) -> Dict[str, Dict[str, Any]]:
        """Get currently active runs"""
        return self.active_runs.copy()
    
    def cleanup_old_runs(self, max_age_minutes: int = 30):
        """Clean up old runs that may have been orphaned"""
        cutoff_time = datetime.now().timestamp() - (max_age_minutes * 60)
        
        runs_to_remove = []
        for run_id, run_info in self.active_runs.items():
            if run_info["started_at"].timestamp() < cutoff_time:
                runs_to_remove.append(run_id)
        
        for run_id in runs_to_remove:
            del self.active_runs[run_id]
            logger.info(f"🧹 Cleaned up orphaned run: {run_id}")
        
        return len(runs_to_remove)