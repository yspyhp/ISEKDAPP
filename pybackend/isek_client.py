#!/usr/bin/env python3
"""
ISEK Network Client
Connect to local ISEK node and communicate with agents in the network
Reference: https://github.com/isekOS/ISEK/blob/main/examples/lv9_agent_on_node_client.py
"""

import os
import json
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from datetime import datetime
import dotenv

class IsekNodeClient:
    """ISEK Node Client - Connect to local ISEK node"""
    
    def __init__(self):
        # Load environment variables
        dotenv.load_dotenv()
        
        # ISEK node configuration
        self.node_url = os.getenv('ISEK_NODE_URL', 'http://localhost:8000')
        self.session = None
        self.agents_cache = {}
        
        # Mock user ID for all requests
        self.mock_user_id = "isek-ui-backend-user-001"
    
    async def initialize(self):
        """Initialize connection with ISEK node"""
        try:
            # Create aiohttp session
            self.session = aiohttp.ClientSession()
            
            # Test connection
            async with self.session.get(f"{self.node_url}/health") as response:
                if response.status == 200:
                    print(f"Successfully connected to ISEK node: {self.node_url}")
                    return True
                else:
                    print(f"ISEK node connection failed: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"Failed to connect to ISEK node: {e}")
            return False
    
    async def discover_agents(self) -> List[Dict[str, Any]]:
        """Discover agents in the network through ISEK node"""
        try:
            if not self.session:
                await self.initialize()
            
            if not self.session:
                return self.get_fallback_agents()
            
            # Call ISEK node's agent discovery interface
            async with self.session.get(f"{self.node_url}/agents") as response:
                if response.status == 200:
                    agents_data = await response.json()
                    print(f"DEBUG: Raw agents data from ISEK node: {len(agents_data)} agents")
                    for agent in agents_data:
                        print(f"DEBUG: Raw agent: {agent.get('name', 'Unknown')} (ID: {agent.get('id', 'Unknown')})")
                    
                    # Convert to frontend required format
                    formatted_agents = []
                    for agent in agents_data:
                        formatted_agent = {
                            "id": agent.get("id", f"agent-{len(formatted_agents)}"),
                            "name": agent.get("name", "Unknown Agent"),
                            "description": agent.get("description", "Agent in ISEK network"),
                            "systemPrompt": agent.get("system_prompt", "I am an agent in the ISEK network"),
                            "model": agent.get("model", "gpt-4o-mini"),
                            "address": agent.get("address", ""),
                            "isek_id": agent.get("id"),
                            "capabilities": agent.get("capabilities", []),
                            "status": agent.get("status", "online"),
                            "network": "isek"
                        }
                        formatted_agents.append(formatted_agent)
                        self.agents_cache[formatted_agent["id"]] = formatted_agent
                        print(f"DEBUG: Formatted agent: {formatted_agent['name']} (ID: {formatted_agent['id']})")
                    
                    print(f"DEBUG: Final formatted agents count: {len(formatted_agents)}")
                    return formatted_agents
                else:
                    print(f"Failed to get agent list: {response.status}")
                    return self.get_fallback_agents()
                    
        except Exception as e:
            print(f"Failed to discover agents: {e}")
            return self.get_fallback_agents()
    
    def get_fallback_agents(self) -> List[Dict[str, Any]]:
        """Fallback agents when ISEK node is unavailable"""
        return [
            {
                "id": "isek-assistant-001",
                "name": "ISEK Assistant",
                "description": "Friendly assistant in the ISEK network, good at answering various questions",
                "systemPrompt": "I am a friendly assistant in the ISEK network, happy to serve you.",
                "model": "gpt-4o-mini",
                "address": "isek://agent/assistant-001",
                "isek_id": "assistant-001",
                "capabilities": ["chat", "help", "general"],
                "status": "online",
                "network": "isek"
            },
            {
                "id": "isek-expert-002",
                "name": "ISEK Tech Expert",
                "description": "Technical expert in the ISEK network, good at solving technical problems",
                "systemPrompt": "I am a technical expert in the ISEK network, good at solving various technical problems.",
                "model": "gpt-4o-mini",
                "address": "isek://agent/expert-002",
                "isek_id": "expert-002",
                "capabilities": ["tech_support", "analysis", "debugging"],
                "status": "online",
                "network": "isek"
            }
        ]
    
    async def send_message_to_agent(self, agent_id: str, messages: List[Dict], system: str = "", session_id: str = "") -> str:
        """Send message to agent through ISEK node"""
        try:
            if not self.session:
                await self.initialize()
            
            if not self.session:
                agent_info = self.agents_cache.get(agent_id, {})
                return self.get_mock_response(agent_info, messages)
            
            # Get agent information
            agent_info = self.agents_cache.get(agent_id)
            if not agent_info:
                # Try to rediscover agents
                await self.discover_agents()
                agent_info = self.agents_cache.get(agent_id)
            
            if not agent_info:
                return "Agent unavailable or not found"
            
            # Send message through ISEK node
            payload = {
                "agent_id": agent_info["isek_id"],
                "session_id": session_id,
                "user_id": self.mock_user_id,
                "messages": messages,
                "system_prompt": system or agent_info["systemPrompt"]
            }
            
            async with self.session.post(
                f"{self.node_url}/chat",
                json=payload
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("response", "Agent response")
                else:
                    print(f"Failed to send message: {response.status}")
                    # Return mock response
                    return self.get_mock_response(agent_info, messages)
                    
        except Exception as e:
            print(f"Failed to send message to agent: {e}")
            # Return mock response
            agent_info = self.agents_cache.get(agent_id, {})
            return self.get_mock_response(agent_info, messages)
    
    def get_mock_response(self, agent_info: Dict, messages: List[Dict]) -> str:
        """Mock response when ISEK node is unavailable"""
        user_message = messages[-1]["content"] if messages else "Hello"
        agent_name = agent_info.get("name", "ISEK Agent")
        
        if "assistant" in agent_info.get("id", ""):
            return f"Hello! I am {agent_name}, happy to serve you. You said: {user_message}"
        elif "expert" in agent_info.get("id", ""):
            return f"From a technical perspective, {user_message} can be solved like this..."
        else:
            return f"I am {agent_name}, you said: {user_message}"
    
    def get_network_status(self) -> Dict[str, Any]:
        """Get network status"""
        return {
            "connected": self.session is not None,
            "node_url": self.node_url,
            "agents_count": len(self.agents_cache),
            "timestamp": datetime.now().isoformat()
        }
    
    async def shutdown(self):
        """Close ISEK node connection"""
        try:
            if self.session:
                await self.session.close()
            print("ISEK node client closed")
        except Exception as e:
            print(f"Failed to close ISEK node client: {e}")

# Global ISEK node client instance
isek_client = IsekNodeClient() 