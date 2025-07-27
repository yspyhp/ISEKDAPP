"""
AGUI Adapter with integrated A2A Translation
Adapter layer that handles AGUI ↔ A2A conversion and communication with ISEK nodes
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass
from datetime import datetime

# ISEK adapter base
from isek.adapter.base import Adapter, AdapterCard

# A2A and ISEK imports
from isek.node.node_v2 import Node
from isek.node.etcd_registry import EtcdRegistry

# Import A2A Client components (no server components needed)
try:
    from a2a.client import A2AClient
    from a2a.types import MessageSendParams, SendMessageRequest
    A2A_CLIENT_AVAILABLE = True
except ImportError:
    A2A_CLIENT_AVAILABLE = False
    logger.warning("A2A Client not available")

# Try to import AGUI SDK components
try:
    from ag_ui.core import (
        RunAgentInput, Message, Context,
        AgentRunStartedEvent, AgentRunFinishedEvent, AgentRunErrorEvent,
        MessageEvent, ToolCallEvent, StateUpdateEvent
    )
    AGUI_AVAILABLE = True
except ImportError:
    AGUI_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ISEKAgentInfo:
    """Information about discovered ISEK agent"""
    id: str
    name: str
    description: str
    url: str
    capabilities: Dict[str, Any]
    status: str = "available"
    metadata: Dict[str, Any] = None


class AGUIAdapter(Adapter):
    """
    AGUI Adapter with integrated A2A Translation
    
    Architecture flow:
    Service → Adapter (this) → Translator → Node → Server Node → Server Adapter
    """
    
    def __init__(self, isek_node_config: Dict[str, Any]):
        """
        Initialize AGUI Adapter
        
        Args:
            isek_node_config: Configuration for ISEK node connection
        """
        self.isek_config = isek_node_config
        self.discovered_agents: Dict[str, ISEKAgentInfo] = {}
        self.node: Optional[Node] = None
        self.registry: Optional[EtcdRegistry] = None
        self.active_requests: Dict[str, Dict[str, Any]] = {}
        
        # A2A Protocol components
        self.a2a_client: Optional[A2AClient] = None
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        
    async def initialize(self):
        """Initialize the adapter and ISEK node connection"""
        try:
            logger.info("🔧 Initializing AGUI Adapter...")
            
            # Create ETCD registry connection
            registry_config = self.isek_config.get("registry", {})
            self.registry = EtcdRegistry(
                host=registry_config.get("host", "47.236.116.81"),
                port=registry_config.get("port", 2379)
            )
            
            # Initialize A2A Client
            if A2A_CLIENT_AVAILABLE:
                logger.info("🔧 A2A Client available for remote agent communication")
            else:
                logger.warning("⚠️ A2A Client not available, using HTTP JSON-RPC fallback")
            
            # Discover available ISEK agents
            await self.discover_agents()
            
            logger.info("✅ AGUI Adapter initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize AGUI Adapter: {e}")
            raise
    
    async def discover_agents(self):
        """Discover available ISEK agents via ETCD"""
        try:
            logger.info("🔍 Discovering ISEK agents...")
            
            # For now, we'll use a simple discovery mechanism
            # In a full implementation, this would query ETCD for registered nodes
            
            # Mock discovery for demonstration
            # In real implementation, query ETCD registry for registered agents
            mock_agents = [
                {
                    "id": "lyra_agent",
                    "name": "Lyra Agent",
                    "description": "AI Prompt Optimization Specialist", 
                    "url": "http://localhost:8889",
                    "capabilities": {"prompt_optimization": True, "text_generation": True}
                }
            ]
            
            self.discovered_agents = {}
            for agent_data in mock_agents:
                agent_info = ISEKAgentInfo(
                    id=agent_data["id"],
                    name=agent_data["name"],
                    description=agent_data["description"],
                    url=agent_data["url"],
                    capabilities=agent_data["capabilities"]
                )
                self.discovered_agents[agent_info.id] = agent_info
            
            logger.info(f"✅ Discovered {len(self.discovered_agents)} ISEK agents")
            for agent_id, agent in self.discovered_agents.items():
                logger.info(f"   - {agent_id}: {agent.name} ({agent.url})")
                
        except Exception as e:
            logger.error(f"❌ Agent discovery failed: {e}")
    
    async def process_agui_request(self, adapter_input: Dict[str, Any]) -> AsyncGenerator[Any, None]:
        """
        Process AGUI request and convert to A2A communication
        
        Args:
            adapter_input: Input from AGUI service layer
            
        Yields:
            AGUI-compatible events
        """
        request_id = adapter_input.get("request_id", str(uuid.uuid4()))
        agent_id = adapter_input.get("agent_id")
        session_id = adapter_input.get("session_id", str(uuid.uuid4()))
        
        try:
            logger.info(f"🔄 Processing AGUI request: {request_id} for agent: {agent_id}")
            
            # Track request
            self.active_requests[request_id] = {
                "agent_id": agent_id,
                "session_id": session_id,
                "started_at": datetime.now(),
                "status": "processing"
            }
            
            # 1. Emit run started event
            yield self._create_run_started_event(request_id, adapter_input)
            
            # 2. Convert AGUI messages to A2A format
            a2a_message = await self._convert_agui_to_a2a(adapter_input)
            
            # 3. Send A2A message to target agent
            logger.info(f"📤 Sending A2A message to {agent_id}: {a2a_message[:100]}...")
            
            a2a_response = await self._send_a2a_message(agent_id, a2a_message, session_id)
            
            # 4. Convert A2A response back to AGUI events
            if a2a_response.get("success"):
                async for event in self._convert_a2a_to_agui_events(a2a_response, request_id):
                    yield event
            else:
                # Handle A2A error
                error_msg = a2a_response.get("error", "Unknown A2A error")
                yield self._create_error_event(request_id, error_msg)
            
            # 5. Emit run finished event
            yield self._create_run_finished_event(request_id, {"status": "completed"})
            
            # Update request status
            if request_id in self.active_requests:
                self.active_requests[request_id]["status"] = "completed"
                self.active_requests[request_id]["completed_at"] = datetime.now()
                
        except Exception as e:
            logger.error(f"❌ Failed to process AGUI request {request_id}: {e}")
            yield self._create_error_event(request_id, str(e))
            
            # Update request status
            if request_id in self.active_requests:
                self.active_requests[request_id]["status"] = "error"
                self.active_requests[request_id]["error"] = str(e)
    
    async def _convert_agui_to_a2a(self, adapter_input: Dict[str, Any]) -> str:
        """Convert AGUI input to A2A message format"""
        try:
            messages = adapter_input.get("messages", [])
            
            # Extract the latest user message
            user_message = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    user_message = msg.get("content", "")
                    break
            
            if not user_message and messages:
                # Fallback to last message
                user_message = str(messages[-1].get("content", ""))
            
            return user_message or "Hello"
            
        except Exception as e:
            logger.error(f"❌ Failed to convert AGUI to A2A: {e}")
            return "Error converting message"
    
    async def _send_a2a_message(self, agent_id: str, message: str, session_id: str) -> Dict[str, Any]:
        """Send A2A message to target agent using A2A Protocol"""
        try:
            if agent_id not in self.discovered_agents:
                return {"success": False, "error": f"Agent {agent_id} not found"}
            
            agent = self.discovered_agents[agent_id]
            
            # Use A2A Protocol if available
            if A2A_PROTOCOL_AVAILABLE and self.task_store:
                # Create RequestContext for A2A protocol
                request_context = RequestContext(
                    task_id=str(uuid.uuid4()),
                    session_id=session_id,
                    user_input=message,
                    current_task=None
                )
                self.request_contexts[session_id] = request_context
                
                # Initialize A2A client if not already done
                if not self.a2a_client:
                    self.a2a_client = A2AClient(base_url=agent.url)
                
                # Create A2A message parameters
                message_params = MessageSendParams(
                    message={
                        "role": "user",
                        "parts": [{"kind": "text", "text": message}],
                        "messageId": str(uuid.uuid4())
                    },
                    metadata={
                        "session_id": session_id,
                        "sender": "agui_adapter",
                        "request_context": request_context.__dict__
                    }
                )
                
                # Send via A2A protocol
                try:
                    response = await self.a2a_client.send_message(message_params)
                    return {"success": True, "response": response, "protocol": "a2a"}
                except Exception as a2a_error:
                    logger.warning(f"A2A protocol failed, falling back to HTTP: {a2a_error}")
            
            # Fallback to HTTP JSON-RPC
            a2a_request = {
                "jsonrpc": "2.0",
                "method": "message/send",
                "params": {
                    "message": {
                        "role": "user",
                        "parts": [{"kind": "text", "text": message}],
                        "messageId": str(uuid.uuid4())
                    },
                    "metadata": {
                        "session_id": session_id,
                        "sender": "agui_adapter"
                    }
                },
                "id": str(uuid.uuid4())
            }
            
            # Send HTTP request to agent
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    agent.url,
                    json=a2a_request,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        return {"success": True, "response": result, "protocol": "http"}
                    else:
                        error_text = await response.text()
                        return {"success": False, "error": f"HTTP {response.status}: {error_text}"}
                        
        except Exception as e:
            logger.error(f"❌ Failed to send A2A message: {e}")
            return {"success": False, "error": str(e)}
    
    async def _convert_a2a_to_agui_events(self, a2a_response: Dict[str, Any], request_id: str) -> AsyncGenerator[Any, None]:
        """Convert A2A response to AGUI events"""
        try:
            response_data = a2a_response.get("response", {})
            
            if "result" in response_data:
                # Successful A2A response
                result = response_data["result"]
                task_id = result.get("id", "unknown")
                context_id = result.get("contextId", "unknown")
                status = result.get("status", {}).get("state", "unknown")
                
                # Create message event with task information
                content = f"Task created successfully!\n" \
                         f"Task ID: {task_id}\n" \
                         f"Context ID: {context_id}\n" \
                         f"Status: {status}"
                
                yield self._create_message_event(content, "assistant")
                
            elif "error" in response_data:
                # A2A error response
                error = response_data["error"]
                error_message = error.get("message", "Unknown error")
                yield self._create_message_event(f"Error: {error_message}", "assistant")
                
            else:
                # Unknown response format
                yield self._create_message_event(f"Received response: {response_data}", "assistant")
                
        except Exception as e:
            logger.error(f"❌ Failed to convert A2A to AGUI events: {e}")
            yield self._create_error_event(request_id, str(e))
    
    def _create_run_started_event(self, run_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create AGUI run started event"""
        if AGUI_AVAILABLE:
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
            "data": {"agent_id": input_data.get("agent_id"), "session_id": input_data.get("session_id")}
        }
    
    def _create_message_event(self, content: str, role: str = "assistant") -> Dict[str, Any]:
        """Create AGUI message event"""
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
            "data": {"content": content, "role": role}
        }
    
    def _create_run_finished_event(self, run_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Create AGUI run finished event"""
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
            "data": {"result": result}
        }
    
    def _create_error_event(self, run_id: str, error_message: str) -> Dict[str, Any]:
        """Create AGUI error event"""
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
            "data": {"error": error_message}
        }
    
    # Adapter interface methods
    async def get_available_agents(self) -> List[Dict[str, Any]]:
        """Get list of available agents"""
        agents = []
        for agent_id, agent_info in self.discovered_agents.items():
            agents.append({
                "id": agent_info.id,
                "name": agent_info.name,
                "description": agent_info.description,
                "capabilities": agent_info.capabilities,
                "status": agent_info.status,
                "url": agent_info.url
            })
        return agents
    
    async def can_handle_agent(self, agent_id: str) -> bool:
        """Check if this adapter can handle the specified agent"""
        return agent_id in self.discovered_agents
    
    async def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get status of specific agent"""
        if agent_id in self.discovered_agents:
            agent = self.discovered_agents[agent_id]
            return {
                "id": agent.id,
                "name": agent.name,
                "status": agent.status,
                "url": agent.url,
                "last_checked": datetime.now().isoformat()
            }
        return None
    
    def get_adapter_card(self) -> AdapterCard:
        """Get adapter card for ISEK compatibility"""
        return AdapterCard(
            name="AGUI Adapter",
            bio="Bridges AGUI protocol with ISEK agents via A2A communication",
            lore="Provides seamless integration between AGUI frontends and ISEK backend agents",
            knowledge="AGUI protocol, A2A messaging, ISEK nodes, event streaming",
            routine="Convert AGUI requests to A2A messages, send to ISEK agents, convert responses back to AGUI events"
        )
    
    def run(self, prompt: str, **kwargs) -> str:
        """Synchronous run method (for ISEK compatibility)"""
        # This is a compatibility method - actual processing is async
        return f"AGUI Adapter processed: {prompt}"
    
    def get_adapter_stats(self) -> Dict[str, Any]:
        """Get adapter statistics"""
        return {
            "discovered_agents": len(self.discovered_agents),
            "active_requests": len(self.active_requests),
            "agent_list": list(self.discovered_agents.keys())
        }