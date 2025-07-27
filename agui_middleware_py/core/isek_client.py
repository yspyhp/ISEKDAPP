"""
ISEK Client for AGUI Middleware
Handles ISEK node creation, A2A message processing, and agent discovery
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass
from datetime import datetime

# ISEK imports
from isek.node.node_v2 import Node
from isek.node.etcd_registry import EtcdRegistry
from isek.adapter.base import Adapter, AdapterCard

# A2A Protocol imports
try:
    from agent_server.protocol.a2a_protocol import A2ACompliantAgentExecutor
    from isek.protocol.a2a_protocol import A2AProtocol
    A2A_PROTOCOL_AVAILABLE = True
except ImportError:
    A2A_PROTOCOL_AVAILABLE = False

# A2A types
from a2a.types import MessageSendParams, SendMessageRequest, A2AError
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

logger = logging.getLogger(__name__)


@dataclass
class ISEKNodeConfig:
    """Configuration for ISEK node"""
    node_id: str = "agui_middleware_node"
    host: str = "0.0.0.0"
    port: int = 8082
    p2p_enabled: bool = False
    registry_host: str = "47.236.116.81"
    registry_port: int = 2379


class AGUIMiddlewareAdapter(Adapter):
    """Adapter that bridges AGUI middleware with A2A protocol"""
    
    def __init__(self, middleware_callback):
        self.middleware_callback = middleware_callback
        
    def get_adapter_card(self) -> AdapterCard:
        """Return adapter information"""
        return AdapterCard(
            name="AGUI Middleware Adapter",
            bio="Bridges AGUI protocol with A2A systems",
            lore="Provides seamless integration between AGUI agents and ISEK nodes",
            knowledge="AGUI protocol, A2A messaging, async event streaming",
            routine="Handle A2A messages and convert to AGUI format for processing"
        )
    
    def run(self, prompt: str, **kwargs) -> str:
        """Synchronous run method (legacy compatibility)"""
        # This shouldn't be used in async context, but provided for compatibility
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self._async_run(prompt, **kwargs))
            return result
        finally:
            loop.close()
    
    async def _async_run(self, prompt: str, **kwargs) -> str:
        """Async implementation of run"""
        # Convert to AGUI format and process
        context = {
            "message": prompt,
            "session_id": kwargs.get("session_id", str(uuid.uuid4())),
            "user_id": kwargs.get("user_id", "default"),
            "metadata": kwargs
        }
        
        # Call middleware to process this A2A message
        response = await self.middleware_callback(context)
        return response.get("content", "No response")


class ISEKClient:
    """ISEK Client for AGUI Middleware"""
    
    def __init__(self, config: ISEKNodeConfig, middleware_callback):
        self.config = config
        self.middleware_callback = middleware_callback
        self.node: Optional[Node] = None
        self.registry: Optional[EtcdRegistry] = None
        self.adapter: Optional[AGUIMiddlewareAdapter] = None
        self.discovered_agents: Dict[str, Dict[str, Any]] = {}
        
    async def initialize(self):
        """Initialize ISEK node and register with ETCD"""
        try:
            logger.info(f"🔧 Initializing ISEK client: {self.config.node_id}")
            
            # Create ETCD registry
            self.registry = EtcdRegistry(
                host=self.config.registry_host,
                port=self.config.registry_port
            )
            
            # Create adapter
            self.adapter = AGUIMiddlewareAdapter(self.middleware_callback)
            
            # Create ISEK node
            self.node = Node(
                node_id=self.config.node_id,
                host=self.config.host,
                port=self.config.port,
                p2p=self.config.p2p_enabled,
                adapter=self.adapter,
                registry=self.registry
            )
            
            logger.info(f"✅ ISEK node created: {self.config.node_id}")
            
            # Discover existing agents
            await self.discover_agents()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize ISEK client: {e}")
            raise
    
    async def start_server(self, daemon: bool = True):
        """Start the ISEK node server"""
        try:
            if not self.node:
                raise RuntimeError("ISEK client not initialized")
                
            logger.info(f"🚀 Starting ISEK node server on {self.config.host}:{self.config.port}")
            
            if daemon:
                # Start in background thread
                import threading
                server_thread = threading.Thread(
                    target=lambda: self.node.build_server(daemon=False),
                    daemon=True
                )
                server_thread.start()
                logger.info("✅ ISEK node server started in background")
            else:
                # Start in foreground (blocking)
                self.node.build_server(daemon=False)
                
        except Exception as e:
            logger.error(f"❌ Failed to start ISEK node server: {e}")
            raise
    
    async def discover_agents(self) -> Dict[str, Dict[str, Any]]:
        """Discover available agents via ETCD"""
        try:
            if not self.registry:
                return {}
                
            logger.info("🔍 Discovering available agents...")
            
            # Get all registered nodes
            nodes = await self._get_registry_nodes()
            
            self.discovered_agents = {}
            for node_id, node_info in nodes.items():
                if node_id != self.config.node_id:  # Don't include ourselves
                    self.discovered_agents[node_id] = {
                        "id": node_id,
                        "name": node_info.get("name", node_id),
                        "url": node_info.get("url", ""),
                        "description": node_info.get("description", ""),
                        "capabilities": node_info.get("capabilities", {}),
                        "discovered_at": datetime.now().isoformat()
                    }
            
            logger.info(f"✅ Discovered {len(self.discovered_agents)} agents")
            for agent_id, agent_info in self.discovered_agents.items():
                logger.info(f"   - {agent_id}: {agent_info['name']} ({agent_info['url']})")
            
            return self.discovered_agents
            
        except Exception as e:
            logger.error(f"❌ Agent discovery failed: {e}")
            return {}
    
    async def _get_registry_nodes(self) -> Dict[str, Dict[str, Any]]:
        """Get nodes from ETCD registry"""
        # This would need to be implemented based on ETCD registry format
        # For now, return empty dict - this can be expanded later
        return {}
    
    async def send_a2a_message(self, agent_id: str, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Send A2A message to a discovered agent"""
        try:
            if agent_id not in self.discovered_agents:
                raise ValueError(f"Agent {agent_id} not found in discovered agents")
            
            agent_info = self.discovered_agents[agent_id]
            agent_url = agent_info["url"]
            
            if not agent_url:
                raise ValueError(f"No URL available for agent {agent_id}")
            
            # Create A2A request
            request_payload = {
                "jsonrpc": "2.0",
                "method": "message/send",
                "params": {
                    "message": {
                        "role": "user",
                        "parts": [{"kind": "text", "text": message}],
                        "messageId": str(uuid.uuid4())
                    },
                    "metadata": {
                        "session_id": session_id or str(uuid.uuid4()),
                        "sender_node_id": self.config.node_id
                    }
                },
                "id": str(uuid.uuid4())
            }
            
            # Send HTTP request
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    agent_url,
                    json=request_payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return {
                            "success": True,
                            "response": result,
                            "agent_id": agent_id
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status}",
                            "agent_id": agent_id
                        }
                        
        except Exception as e:
            logger.error(f"❌ Failed to send A2A message to {agent_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "agent_id": agent_id
            }
    
    async def get_agent_list(self) -> List[Dict[str, Any]]:
        """Get list of available agents in AGUI format"""
        agents = []
        for agent_id, agent_info in self.discovered_agents.items():
            agents.append({
                "id": agent_id,
                "name": agent_info["name"],
                "description": agent_info["description"],
                "capabilities": agent_info["capabilities"],
                "status": "available",
                "url": agent_info["url"]
            })
        return agents
    
    async def shutdown(self):
        """Shutdown ISEK client and cleanup resources"""
        logger.info("🛑 Shutting down ISEK client...")
        
        # Additional cleanup can be added here
        self.discovered_agents.clear()
        
        logger.info("✅ ISEK client shutdown complete")