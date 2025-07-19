#!/usr/bin/env python3
"""
ISEK Client - Interface to ISEK Node for data retrieval
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import uuid

from isek.node.node_v2 import Node
from isek.node.etcd_registry import EtcdRegistry
from shared_formats import (
    create_chat_message_json, create_session_lifecycle_message_json, 
    parse_agent_response
)

@dataclass
class SessionLifecycleMessage:
    session_id: str
    action: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Data Models ---

@dataclass
class AgentConfig:
    """Agent configuration data model"""
    id: str
    name: str
    description: str
    system_prompt: str
    model: str
    address: str
    capabilities: List[str] = field(default_factory=list)
    status: str = "active"

@dataclass 
class NetworkStatus:
    """Network status data model"""
    connected: bool
    agents_count: int
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    node_id: Optional[str] = None
    node_address: Optional[str] = None

@dataclass
class SessionConfig:
    """Session configuration data model"""
    id: str
    title: str
    agent_id: str
    agent_name: str
    agent_description: str
    agent_address: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    message_count: int = 0
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MessageConfig:
    """Message configuration data model"""
    id: str
    session_id: str
    content: str
    role: str  # "user" or "assistant"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_results: Optional[List[Dict[str, Any]]] = None



# --- ISEK Client Class ---

class ISEKClient:
    """
    ISEK Client that integrates with ISEK Node to provide data for API endpoints
    """
    
    def __init__(self, node_id: str = "isek_client_node", registry_host: str = "47.236.116.81", registry_port: int = 2379):
        """Initialize ISEK client with node configuration"""
        self.node_id = node_id
        self.registry_host = registry_host
        self.registry_port = registry_port
        self.node = None
        self.etcd_registry = None
        self._agents_cache: List[AgentConfig] = []
        self._network_status: NetworkStatus = NetworkStatus(connected=False, agents_count=0)
        self._sessions_cache: Dict[str, SessionConfig] = {}
        self._messages_cache: Dict[str, List[MessageConfig]] = {}
        
    async def initialize_node(self):
        """Initialize ISEK node with etcd registry"""
        try:
            # Create etcd registry
            self.etcd_registry = EtcdRegistry(host=self.registry_host, port=self.registry_port)
            
            # Create ISEK Node with registry
            self.node = Node(node_id=self.node_id, registry=self.etcd_registry)
            
            # Build server in daemon mode
            self.node.build_server(daemon=True)
            
            self._network_status = NetworkStatus(
                connected=True, 
                agents_count=0,
                node_id=self.node_id,
                node_address=f"{self.registry_host}:{self.registry_port}"
            )
            logger.info(f"Initialized ISEK node with ID: {self.node_id} and registry: {self.registry_host}:{self.registry_port}")
        except Exception as e:
            logger.error(f"Failed to initialize ISEK node: {e}")
            self._network_status = NetworkStatus(connected=False, agents_count=0)
    
    async def discover_agents(self) -> List[AgentConfig]:
        """Discover available agents through ISEK node registry"""
        try:
            if not self._network_status.connected:
                await self.initialize_node()
            
            # Get all nodes from registry
            if self.node and hasattr(self.node, 'all_nodes'):
                all_nodes: Dict[str, Dict[str, Any]] = self.node.all_nodes
                agents = []
                
                for node_id, node_details in all_nodes.items():
                    if node_id != self.node_id:  # Exclude self
                        # Create agent config from node details
                        agent = AgentConfig(
                            id=node_id,
                            name=node_details.get('name', node_id),
                            description=node_details.get('description', f"Agent {node_id}"),
                            system_prompt=node_details.get('system_prompt', "You are a helpful AI assistant."),
                            model=node_details.get('model', "gpt-4"),
                            address=node_id,
                            capabilities=node_details.get('capabilities', ["text_generation"]),
                            status="active"
                        )
                        agents.append(agent)
                
                self._agents_cache = agents
                self._network_status.agents_count = len(agents)
                logger.info(f"Discovered {len(agents)} agents through registry")
                return agents
            else:
                logger.warning("Node not initialized or all_nodes not available")
                return []
            
        except Exception as e:
            logger.error(f"Failed to discover agents: {e}")
            return []
    
    def get_agent_by_id(self, agent_id: str) -> Optional[AgentConfig]:
        """Get specific agent by ID from cache"""
        return next((agent for agent in self._agents_cache if agent.id == agent_id), None)
    
    def get_network_status(self) -> NetworkStatus:
        """Get current network connection status"""
        return self._network_status
    
    async def send_message_to_agent(self, session_id: str, system_prompt: str = "") -> str:
        """Send message to agent bound to this session using standardized format"""
        try:
            session = self.get_session(session_id)
            if not session:
                return "Error: Session not found"
            
            agent = self.get_agent_by_id(session.agent_id)
            if not agent:
                return "Error: Agent not found"
            
            if not self.node:
                await self.initialize_node()
            
            # Get conversation history and latest user message
            history = self.get_conversation_history(session_id)
            user_message = ""
            for msg in reversed(history):
                if msg["role"] == "user":
                    user_message = msg["content"]
                    break
            
            # Create standardized message using client's node_id as user_id
            message = create_chat_message_json(
                session_id=session_id,
                user_id=self.node_id,  # client's node_id is user_id
                messages=history,
                system_prompt=system_prompt or agent.system_prompt,
                user_message=user_message
            )
            
            # Send to agent (agent.address is the server's node_id)
            response = self.node.send_message(agent.address, message)
            
            if response:
                # Parse standardized response
                parsed_response = parse_agent_response(response)
                if parsed_response["success"]:
                    return parsed_response["content"]
                else:
                    return f"Error: {parsed_response['error']}"
            
            return "Error: No response from agent"
                
        except Exception as e:
            logger.error(f"Failed to send message for session {session_id}: {e}")
            return "Error: Unable to communicate with agent"
    
    def is_agent_available(self, agent_id: str) -> bool:
        """Check if agent is available and active"""
        agent = self.get_agent_by_id(agent_id)
        return agent is not None and agent.status == "active"
    
    # --- Tool Call Parsing Methods ---
    
    def parse_agent_response(self, response: str) -> Dict[str, Any]:
        """Parse agent response to extract content and tool calls"""
        try:
            # Try to parse as JSON first
            if response.strip().startswith('{'):
                data = json.loads(response)
                return {
                    "content": data.get("content", response),
                    "tool_calls": data.get("tool_calls", []),
                    "success": True
                }
            else:
                # Check for team formation keywords to simulate tool calls (for testing)
                if self._should_trigger_team_formation(response):
                    return self._simulate_team_formation_response(response)
                
                # Plain text response
                return {
                    "content": response,
                    "tool_calls": [],
                    "success": True
                }
        except json.JSONDecodeError:
            # If not valid JSON, treat as plain text
            # Check for team formation keywords to simulate tool calls (for testing)
            if self._should_trigger_team_formation(response):
                return self._simulate_team_formation_response(response)
            
            return {
                "content": response,
                "tool_calls": [],
                "success": True
            }
    
    def _should_trigger_team_formation(self, response: str) -> bool:
        """Check if response should trigger team formation tool call (for testing)"""
        keywords = ["组队", "小队", "recruit", "team", "招聘", "组建", "协作"]
        return any(keyword in response.lower() for keyword in keywords)
    
    def _simulate_team_formation_response(self, original_response: str) -> Dict[str, Any]:
        """Simulate team formation tool call response (for testing)"""
        tool_call = {
            "id": f"call_{uuid.uuid4().hex[:8]}",
            "type": "function",
            "function": {
                "name": "team-formation",
                "arguments": {
                    "task": "AI项目开发小队",
                    "requiredRoles": ["工程师", "数据科学家", "前端开发", "项目经理"],
                    "maxMembers": 4
                }
            }
        }
        
        return {
            "content": "正在为您组建AI项目开发小队...",
            "tool_calls": [tool_call],
            "success": True
        }
    
    def format_tool_calls_for_frontend(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format tool calls for frontend consumption"""
        formatted_calls = []
        for tool_call in tool_calls:
            formatted_call = {
                "id": tool_call.get("id", str(uuid.uuid4())),
                "type": tool_call.get("type", "function"),
                "function": {
                    "name": tool_call.get("function", {}).get("name", "unknown"),
                    "arguments": tool_call.get("function", {}).get("arguments", {})
                }
            }
            formatted_calls.append(formatted_call)
        return formatted_calls
    
    # --- Session Management Methods ---
    
    def create_session(self, agent_id: str, title: str = None, user_id: str = None) -> SessionConfig:
        """Create a new chat session"""
        agent = self.get_agent_by_id(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        session_id = str(uuid.uuid4())
        session = SessionConfig(
            id=session_id,
            title=title or f"Chat with {agent.name}",
            agent_id=agent_id,
            agent_name=agent.name,
            agent_description=agent.description,
            agent_address=agent.address,
            user_id=user_id
        )
        
        self._sessions_cache[session_id] = session
        self._messages_cache[session_id] = []
        
        # Notify agent about new session
        asyncio.create_task(self._notify_agent_session_created(agent_id, session_id))
        
        return session
    
    def get_session(self, session_id: str) -> Optional[SessionConfig]:
        """Get session by ID"""
        return self._sessions_cache.get(session_id)
    
    def get_all_sessions(self, user_id: str = None, agent_id: str = None) -> List[SessionConfig]:
        """Get all sessions, optionally filtered by user or agent"""
        sessions = list(self._sessions_cache.values())
        
        if user_id:
            sessions = [s for s in sessions if s.user_id == user_id]
        if agent_id:
            sessions = [s for s in sessions if s.agent_id == agent_id]
        
        # Update message counts
        for session in sessions:
            session.message_count = len(self._messages_cache.get(session.id, []))
        
        return sessions
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages"""
        if session_id not in self._sessions_cache:
            return False
        
        session = self._sessions_cache[session_id]
        agent_id = session.agent_id
        
        del self._sessions_cache[session_id]
        if session_id in self._messages_cache:
            del self._messages_cache[session_id]
        
        # Notify agent about session deletion
        asyncio.create_task(self._notify_agent_session_deleted(agent_id, session_id))
        
        return True
    
    # --- Message Management Methods ---
    
    def add_message(self, session_id: str, content: str, role: str, metadata: Dict[str, Any] = None, 
                    tool_calls: List[Dict[str, Any]] = None, tool_results: List[Dict[str, Any]] = None) -> MessageConfig:
        """Add a message to a session"""
        if session_id not in self._sessions_cache:
            raise ValueError(f"Session {session_id} not found")
        
        message = MessageConfig(
            id=str(uuid.uuid4()),
            session_id=session_id,
            content=content,
            role=role,
            metadata=metadata or {},
            tool_calls=tool_calls,
            tool_results=tool_results
        )
        
        if session_id not in self._messages_cache:
            self._messages_cache[session_id] = []
        
        self._messages_cache[session_id].append(message)
        
        # Update session
        session = self._sessions_cache[session_id]
        session.updated_at = datetime.now().isoformat()
        session.message_count = len(self._messages_cache[session_id])
        
        return message
    
    def get_session_messages(self, session_id: str) -> List[MessageConfig]:
        """
        Get all messages in a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of MessageConfig objects
        """
        return self._messages_cache.get(session_id, [])
    
    
    def clear_session_messages(self, session_id: str) -> bool:
        """
        Clear all messages from a session (restart conversation)
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if cleared successfully, False if session not found
        """
        if session_id not in self._sessions_cache:
            return False
        
        session = self._sessions_cache[session_id]
        agent_id = session.agent_id
        
        self._messages_cache[session_id] = []
        
        # Update session message count and timestamp
        session.message_count = 0
        session.updated_at = datetime.now().isoformat()
        
        # Notify agent to clear server-side session
        asyncio.create_task(self._notify_agent_session_cleared(agent_id, session_id))
        
        return True
    
    def get_conversation_history(self, session_id: str, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get conversation history in format suitable for AI models
        
        Args:
            session_id: Session identifier
            limit: Optional limit on number of messages (most recent first)
            
        Returns:
            List of message dictionaries with role and content
        """
        messages = self.get_session_messages(session_id)
        
        if limit:
            messages = messages[-limit:]  # Get most recent messages
        
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp
            }
            for msg in messages
        ]
    
    # --- Session Analytics Methods ---
    
    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """
        Get basic statistics for a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with session statistics
        """
        session = self._sessions_cache.get(session_id)
        if not session:
            return {}
        
        messages = self._messages_cache.get(session_id, [])
        user_messages = [m for m in messages if m.role == "user"]
        assistant_messages = [m for m in messages if m.role == "assistant"]
        
        return {
            "session_id": session_id,
            "total_messages": len(messages),
            "user_messages": len(user_messages),
            "assistant_messages": len(assistant_messages),
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "agent_info": {
                "id": session.agent_id,
                "name": session.agent_name,
                "description": session.agent_description
            }
        }
    
    # --- Agent Session Notification Methods ---
    
    async def _notify_agent_lifecycle(self, agent_id: str, session_id: str, action: str):
        """Unified method to notify agent about session lifecycle events using standardized format"""
        try:
            if not self._network_status.connected or not self.node:
                return
            
            # Create standardized session lifecycle message
            message_string = create_session_lifecycle_message_json(
                session_id=session_id,
                user_id=self.node_id,  # client's node_id as user_id
                action=action
            )
            
            agent = self.get_agent_by_id(agent_id)
            if agent:
                # Send to agent (agent.address is the server's node_id)
                self.node.send_message(agent.address, message_string)
                logger.info(f"Notified agent {agent_id} about session {session_id} {action}")
        except Exception as e:
            logger.error(f"Failed to notify agent {agent_id} about session {action}: {e}")
    
    async def _notify_agent_session_created(self, agent_id: str, session_id: str):
        await self._notify_agent_lifecycle(agent_id, session_id, "created")
    
    async def _notify_agent_session_deleted(self, agent_id: str, session_id: str):
        await self._notify_agent_lifecycle(agent_id, session_id, "deleted")
    
    async def _notify_agent_session_cleared(self, agent_id: str, session_id: str):
        await self._notify_agent_lifecycle(agent_id, session_id, "cleared")

# --- Client Factory ---

_client_instance = None

def get_client(node_id: str = "isek_client_node", registry_host: str = "47.236.116.81", registry_port: int = 2379) -> ISEKClient:
    """
    Get or create the ISEK client instance (singleton pattern)
    
    Args:
        node_id: Node identifier for the ISEK client
        registry_host: Host for etcd registry
        registry_port: Port for etcd registry
    
    Returns:
        ISEKClient instance
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = ISEKClient(node_id=node_id, registry_host=registry_host, registry_port=registry_port)
    return _client_instance

async def initialize_client():
    """Initialize the client instance"""
    client = get_client()
    await client.initialize_node()
    await client.discover_agents()
    return client

# For backwards compatibility
isek_client = get_client()