"""
AGUI Middleware Main Class
Orchestrates ISEK client, A2A translation, and AGUI protocol handling
"""

import asyncio
import logging
import yaml
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from .isek_client import ISEKClient, ISEKNodeConfig
from .a2a_translator import A2AAGUITranslator
from .agent_wrapper import ISEKAgentWrapper, ISEKAgentInfo

logger = logging.getLogger(__name__)


class AGUIMiddleware:
    """
    Main AGUI Middleware class that orchestrates:
    1. ISEK client for A2A communication
    2. A2A to AGUI protocol translation
    3. Agent discovery and management
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.isek_client: Optional[ISEKClient] = None
        self.translator = A2AAGUITranslator()
        self.agents: Dict[str, ISEKAgentWrapper] = {}
        self.is_running = False
        
    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"✅ Configuration loaded from {config_path}")
            return config
        except Exception as e:
            logger.error(f"❌ Failed to load configuration: {e}")
            # Return default configuration
            return {
                "middleware": {"name": "AGUI-ISEK Middleware", "port": 8080},
                "isek": {
                    "node_id": "agui_middleware_node",
                    "host": "0.0.0.0",
                    "port": 8082,
                    "p2p_enabled": False,
                    "registry": {"host": "47.236.116.81", "port": 2379}
                },
                "agui": {"max_concurrent_sessions": 10, "stream_buffer_size": 1024},
                "logging": {"level": "INFO"}
            }
    
    async def initialize(self):
        """Initialize the middleware"""
        try:
            logger.info("🚀 Initializing AGUI Middleware...")
            
            # Setup logging
            log_level = self.config.get("logging", {}).get("level", "INFO")
            logging.getLogger().setLevel(getattr(logging, log_level))
            
            # Create ISEK node configuration
            isek_config_data = self.config.get("isek", {})
            isek_config = ISEKNodeConfig(
                node_id=isek_config_data.get("node_id", "agui_middleware_node"),
                host=isek_config_data.get("host", "0.0.0.0"),
                port=isek_config_data.get("port", 8082),
                p2p_enabled=isek_config_data.get("p2p_enabled", False),
                registry_host=isek_config_data.get("registry", {}).get("host", "47.236.116.81"),
                registry_port=isek_config_data.get("registry", {}).get("port", 2379)
            )
            
            # Create ISEK client with callback
            self.isek_client = ISEKClient(isek_config, self._handle_a2a_message)
            
            # Initialize ISEK client
            await self.isek_client.initialize()
            
            # Start ISEK node server in background
            await self.isek_client.start_server(daemon=True)
            
            # Discover available agents
            await self._discover_and_wrap_agents()
            
            self.is_running = True
            logger.info("✅ AGUI Middleware initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize AGUI Middleware: {e}")
            raise
    
    async def _handle_a2a_message(self, a2a_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming A2A messages and convert to AGUI events
        This is the callback used by ISEK client
        """
        try:
            logger.info(f"📨 Handling A2A message: {a2a_context.get('message', '')[:100]}...")
            
            # Use translator to convert A2A to AGUI format
            agui_input = self.translator.a2a_to_agui_input(a2a_context)
            
            # Process with AGUI protocol (simplified for now)
            # In real implementation, this would route to appropriate agent
            response_content = f"Processed via AGUI: {a2a_context.get('message', '')}"
            
            # Convert back to A2A format
            agui_response = {"content": response_content, "type": "text_message"}
            a2a_response = self.translator.agui_to_a2a_response(
                agui_response, 
                agui_input["session_id"]
            )
            
            logger.info("✅ A2A message processed successfully")
            return a2a_response
            
        except Exception as e:
            logger.error(f"❌ Failed to handle A2A message: {e}")
            return {
                "content": f"Error processing message: {e}",
                "session_id": a2a_context.get("session_id", "unknown"),
                "timestamp": datetime.now().isoformat(),
                "type": "error"
            }
    
    async def _discover_and_wrap_agents(self):
        """Discover ISEK agents and wrap them for AGUI compatibility"""
        try:
            logger.info("🔍 Discovering and wrapping ISEK agents...")
            
            # Get discovered agents from ISEK client
            discovered_agents = await self.isek_client.discover_agents()
            
            # Wrap each agent for AGUI compatibility
            for agent_id, agent_data in discovered_agents.items():
                agent_info = ISEKAgentInfo(
                    id=agent_id,
                    name=agent_data.get("name", agent_id),
                    description=agent_data.get("description", "ISEK Agent"),
                    url=agent_data.get("url", ""),
                    capabilities=agent_data.get("capabilities", {})
                )
                
                wrapped_agent = ISEKAgentWrapper(agent_info, self.isek_client)
                self.agents[agent_id] = wrapped_agent
                
                logger.info(f"   ✅ Wrapped agent: {agent_id} ({agent_info.name})")
            
            logger.info(f"✅ Wrapped {len(self.agents)} agents for AGUI compatibility")
            
        except Exception as e:
            logger.error(f"❌ Failed to discover and wrap agents: {e}")
    
    async def get_agents(self) -> List[Dict[str, Any]]:
        """Get list of available agents in AGUI format"""
        try:
            agents_list = []
            
            for agent_id, agent_wrapper in self.agents.items():
                agent_info = {
                    "id": agent_wrapper.id,
                    "name": agent_wrapper.name,
                    "description": agent_wrapper.description,
                    "capabilities": await agent_wrapper.get_capabilities(),
                    "status": await agent_wrapper.get_status(),
                    "type": "isek_agent",
                    "middleware": "agui-isek"
                }
                agents_list.append(agent_info)
            
            return agents_list
            
        except Exception as e:
            logger.error(f"❌ Failed to get agents list: {e}")
            return []
    
    async def run_agent(self, agent_id: str, input_data: Any) -> Any:
        """Run a specific agent with AGUI input"""
        try:
            if agent_id not in self.agents:
                raise ValueError(f"Agent {agent_id} not found")
            
            agent = self.agents[agent_id]
            logger.info(f"🚀 Running agent: {agent_id}")
            
            # Run agent and collect events
            events = []
            async for event in agent.run(input_data):
                events.append(event)
                logger.debug(f"📤 Agent event: {event}")
            
            logger.info(f"✅ Agent {agent_id} completed with {len(events)} events")
            return events
            
        except Exception as e:
            logger.error(f"❌ Failed to run agent {agent_id}: {e}")
            raise
    
    async def send_message_to_agent(self, agent_id: str, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Send a message to a specific agent"""
        try:
            if self.isek_client is None:
                raise RuntimeError("ISEK client not initialized")
            
            response = await self.isek_client.send_a2a_message(
                agent_id=agent_id,
                message=message,
                session_id=session_id
            )
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Failed to send message to agent {agent_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def refresh_agents(self):
        """Refresh the list of available agents"""
        try:
            logger.info("🔄 Refreshing agents list...")
            
            # Clear current agents
            self.agents.clear()
            
            # Re-discover and wrap agents
            await self._discover_and_wrap_agents()
            
            logger.info("✅ Agents list refreshed")
            
        except Exception as e:
            logger.error(f"❌ Failed to refresh agents: {e}")
    
    async def get_middleware_status(self) -> Dict[str, Any]:
        """Get middleware status information"""
        try:
            return {
                "name": self.config.get("middleware", {}).get("name", "AGUI-ISEK Middleware"),
                "version": self.config.get("middleware", {}).get("version", "1.0.0"),
                "status": "running" if self.is_running else "stopped",
                "agents_count": len(self.agents),
                "agents": list(self.agents.keys()),
                "isek_node_id": self.isek_client.config.node_id if self.isek_client else None,
                "uptime": datetime.now().isoformat(),
                "configuration": {
                    "isek": self.config.get("isek", {}),
                    "agui": self.config.get("agui", {})
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get middleware status: {e}")
            return {"status": "error", "error": str(e)}
    
    async def shutdown(self):
        """Shutdown the middleware"""
        try:
            logger.info("🛑 Shutting down AGUI Middleware...")
            
            self.is_running = False
            
            # Cleanup agents
            for agent in self.agents.values():
                agent.cleanup_old_sessions()
            self.agents.clear()
            
            # Shutdown ISEK client
            if self.isek_client:
                await self.isek_client.shutdown()
            
            # Cleanup translator
            self.translator.cleanup_old_runs()
            
            logger.info("✅ AGUI Middleware shutdown complete")
            
        except Exception as e:
            logger.error(f"❌ Error during shutdown: {e}")
            raise