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
import os

from isek.node.node_v2 import Node
from isek.node.etcd_registry import EtcdRegistry
from shared_formats import (
    create_chat_message_json, create_session_lifecycle_message_json, 
    parse_agent_response, AgentConfig
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

def load_config():
    """Load configuration from config.json"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r') as f:
        return json.load(f)

# --- Data Models ---

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
    node_id: str
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
    
    def __init__(self, node_id: str = None, registry_host: str = None, registry_port: int = None):
        """Initialize ISEK client with node configuration"""
        # Load config and use as defaults
        config = load_config()
        
        self.node_id = node_id or config.get("node_id", "isek_client_node")
        self.registry_host = registry_host or config.get("registry_host", "47.236.116.81")
        self.registry_port = registry_port or config.get("registry_port", 2379)
        self.node = None
        self.etcd_registry = None
        self._agents_cache: List[AgentConfig] = []
        self._agents_cache_time: Optional[datetime] = None
        self._cache_ttl_seconds: int = 300  # 5分钟缓存
        self._network_status: NetworkStatus = NetworkStatus(connected=False, agents_count=0)
        self._sessions_cache: Dict[str, SessionConfig] = {}
        self._messages_cache: Dict[str, List[MessageConfig]] = {}
        
    async def initialize_node(self):
        """Initialize ISEK node with etcd registry"""
        try:
            # Create etcd registry
            self.etcd_registry = EtcdRegistry(host=self.registry_host, port=self.registry_port)
            
            # Create ISEK Node with registry (use port 8082 to avoid conflicts)
            self.node = Node(node_id=self.node_id, port=8082, registry=self.etcd_registry)
            
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
    
    def _is_cache_valid(self) -> bool:
        """Check if agents cache is still valid"""
        if not self._agents_cache_time:
            return False
        elapsed = (datetime.now() - self._agents_cache_time).total_seconds()
        return elapsed < self._cache_ttl_seconds
    
    async def discover_agents(self, force_refresh: bool = False) -> List[AgentConfig]:
        """Discover available agents through ISEK node registry"""
        try:
            # Return cached results if valid and not forced refresh
            if not force_refresh and self._is_cache_valid() and self._agents_cache:
                logger.info(f"Returning cached agents: {len(self._agents_cache)} agents")
                return self._agents_cache
            
            if not self._network_status.connected:
                await self.initialize_node()
            
            # Get all nodes from registry
            if self.node and hasattr(self.node, 'all_nodes'):
                all_nodes: Dict[str, Dict[str, Any]] = self.node.all_nodes
                logger.info(f"All nodes discovered: {all_nodes}")
                agents = []
                
                for node_id, node_details in all_nodes.items():
                    logger.info(f"Processing node: {node_id} with details: {node_details}")
                    # Check what's in metadata
                    metadata = node_details.get('metadata', {})
                    logger.info(f"Node {node_id} metadata: {metadata}")
                    if node_id != self.node_id:  # Exclude self
                        # Check if we have adapter card info in metadata
                        metadata = node_details.get('metadata', {})
                        
                        # If metadata has adapter card info, use it directly
                        if metadata.get('name') and metadata.get('bio'):
                            logger.info(f"Using metadata for {node_id}")
                            agent = AgentConfig(
                                name=metadata.get('name', node_id),
                                node_id=node_id,
                                bio=metadata.get('bio', f"Agent {node_id}"),
                                lore=metadata.get('lore', ''),
                                knowledge=metadata.get('knowledge', ''),
                                routine=metadata.get('routine', ''),
                                address=metadata.get('url', '')
                            )
                            agents.append(agent)
                        else:
                            # Request adapter card info from the agent
                            logger.info(f"Metadata incomplete for {node_id}, requesting agent config")
                            try:
                                request_message = json.dumps({
                                    "type": "agent_config_request",
                                    "node_id": node_id
                                })
                                logger.info(f"Requesting agent config from {node_id} with message: {request_message}")
                                
                                agent_config_response = self.node.send_message(node_id, request_message)
                                logger.info(f"Received response from {node_id}: {repr(agent_config_response)}")
                                
                                if agent_config_response and agent_config_response.strip():
                                    try:
                                        config_data = json.loads(agent_config_response)
                                        logger.info(f"Parsed config data: {config_data}")
                                        
                                        agent = AgentConfig(
                                            name=config_data.get('name', node_id),
                                            node_id=node_id,
                                            bio=config_data.get('bio', ''),
                                            lore=config_data.get('lore', ''),
                                            knowledge=config_data.get('knowledge', ''),
                                            routine=config_data.get('routine', ''),
                                            address=metadata.get('url', '')
                                        )
                                        agents.append(agent)
                                        logger.info(f"Successfully created agent config for {node_id}")
                                    except json.JSONDecodeError as json_err:
                                        logger.error(f"JSON decode error for {node_id}: {json_err}. Raw response: {repr(agent_config_response)}")
                                        # Fallback to metadata or basic info
                                        agent = AgentConfig(
                                            name=metadata.get('name', node_id),
                                            node_id=node_id,
                                            bio=metadata.get('bio', f"Agent {node_id}"),
                                            lore=metadata.get('lore', ''),
                                            knowledge=metadata.get('knowledge', ''),
                                            routine=metadata.get('routine', ''),
                                            address=metadata.get('url', '')
                                        )
                                        agents.append(agent)
                                else:
                                    logger.warning(f"Empty or None response from {node_id}")
                                    # Fallback to metadata
                                    agent = AgentConfig(
                                        name=metadata.get('name', node_id),
                                        node_id=node_id,
                                        bio=metadata.get('bio', f"Agent {node_id}"),
                                        lore=metadata.get('lore', ''),
                                        knowledge=metadata.get('knowledge', ''),
                                        routine=metadata.get('routine', ''),
                                        address=metadata.get('url', '')
                                    )
                                    agents.append(agent)
                            except Exception as e:
                                logger.error(f"Failed to get agent config from {node_id}: {e}")
                                import traceback
                                traceback.print_exc()
                                # Fallback to metadata
                                agent = AgentConfig(
                                    name=metadata.get('name', node_id),
                                    node_id=node_id,
                                    bio=metadata.get('bio', f"Agent {node_id}"),
                                    lore=metadata.get('lore', ''),
                                    knowledge=metadata.get('knowledge', ''),
                                    routine=metadata.get('routine', ''),
                                    address=metadata.get('url', '')
                                )
                                agents.append(agent)
                
                self._agents_cache = agents
                self._agents_cache_time = datetime.now()
                self._network_status.agents_count = len(agents)
                logger.info(f"Discovered {len(agents)} agents through registry")
                return agents
            else:
                logger.warning("Node not initialized or all_nodes not available")
                return []
            
        except Exception as e:
            logger.error(f"Failed to discover agents: {e}")
            return []
    
    def get_agent_by_id(self, node_id: str) -> Optional[AgentConfig]:
        """Get specific agent by node_id from cache"""
        return next((agent for agent in self._agents_cache if agent.node_id == node_id), None)
    
    def get_network_status(self) -> NetworkStatus:
        """Get current network connection status"""
        return self._network_status
    
    async def send_message_to_agent(self, session_id: str, system_prompt: str = "") -> str:
        """Send message to agent bound to this session using standardized format"""
        try:
            session = self.get_session(session_id)
            if not session:
                return "Error: Session not found"
            
            agent = self.get_agent_by_id(session.node_id)
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
                system_prompt=system_prompt or f"{agent.knowledge}\n\nRoutine: {agent.routine}",
                user_message=user_message
            )
            
            # Send to agent (agent.node_id is the server's node_id)
            logger.info(f"Sending message to agent {agent.node_id}")
            
            try:
                response = self.node.send_message(agent.node_id, message)
                logger.info(f"Received response: {repr(response)}")
                
                # Check if response indicates delivery failure
                if response and "Message delivery" in response and "failed" in response:
                    logger.error(f"Message delivery failed: {response}")
                    return f"Error: Unable to reach agent {agent.name}. The agent may be offline or unreachable."
                
                if response:
                    # Parse standardized response
                    parsed_response = parse_agent_response(response)
                    logger.info(f"Parsed response: {parsed_response}")
                    if parsed_response["success"]:
                        return parsed_response["content"]
                    else:
                        return f"Error: {parsed_response['error']}"
                
                logger.warning("No response received from agent")
                return "Error: No response from agent"
                
            except Exception as send_error:
                logger.error(f"Exception during message send: {send_error}")
                return f"Error: Failed to communicate with agent {agent.name}"
                
        except Exception as e:
            logger.error(f"Failed to send message for session {session_id}: {e}")
            return "Error: Unable to communicate with agent"
    
    def is_agent_available(self, node_id: str) -> bool:
        """Check if agent is available"""
        agent = self.get_agent_by_id(node_id)
        return agent is not None
    
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
    
    def create_session(self, node_id: str, title: str = None, user_id: str = None) -> SessionConfig:
        """Create a new chat session"""
        logger.info(f"Creating session for node {node_id}, title: {title}")
        agent = self.get_agent_by_id(node_id)
        if not agent:
            logger.error(f"Agent {node_id} not found")
            raise ValueError(f"Agent {node_id} not found")
        
        session_id = str(uuid.uuid4())
        session = SessionConfig(
            id=session_id,
            title=title or f"Chat with {agent.name}",
            node_id=node_id,
            agent_name=agent.name,
            agent_description=agent.bio,
            agent_address=agent.node_id,
            user_id=user_id
        )
        
        self._sessions_cache[session_id] = session
        self._messages_cache[session_id] = []
        
        logger.info(f"Created session {session_id} for agent {agent.name} ({node_id})")
        
        # Notify agent about new session
        asyncio.create_task(self._notify_agent_session_created(node_id, session_id))
        
        return session
    
    def get_session(self, session_id: str) -> Optional[SessionConfig]:
        """Get session by ID"""
        return self._sessions_cache.get(session_id)
    
    def get_all_sessions(self, user_id: str = None, node_id: str = None) -> List[SessionConfig]:
        """Get all sessions from local cache only (fast)"""
        sessions = list(self._sessions_cache.values())
        
        if user_id:
            sessions = [s for s in sessions if s.user_id == user_id]
        if node_id:
            sessions = [s for s in sessions if s.node_id == node_id]
        
        # Update message counts
        for session in sessions:
            session.message_count = len(self._messages_cache.get(session.id, []))
        
        return sessions
    
    async def get_all_sessions_distributed(self, user_id: str = None, node_id: str = None) -> List[SessionConfig]:
        """Get all sessions including from remote agents (slower but comprehensive)"""
        # 先获取本地缓存
        local_sessions = self.get_all_sessions(user_id=user_id, node_id=node_id)
        all_sessions = list(local_sessions)
        
        # 如果网络连接可用，查询远程节点
        if self.node and self._network_status.connected and self._agents_cache:
            current_user_id = user_id or self.node_id
            
            # 并发查询所有agents（优化性能）
            import asyncio
            
            async def query_agent(agent):
                if node_id and agent.node_id != node_id:
                    return []
                
                try:
                    request_message = json.dumps({
                        "type": "session_list_request",
                        "user_id": current_user_id,
                        "timestamp": datetime.now().isoformat(),
                        "request_id": str(uuid.uuid4())
                    })
                    
                    # 使用超时来避免阻塞
                    response = self.node.send_message(agent.node_id, request_message)
                    if response and not ("Error:" in response and "failed" in response):
                        session_data = json.loads(response)
                        if session_data.get("success") and session_data.get("sessions"):
                            return session_data["sessions"]
                except Exception as e:
                    logger.warning(f"Failed to get sessions from {agent.node_id}: {e}")
                return []
            
            # 并发查询所有agents
            tasks = [query_agent(agent) for agent in self._agents_cache]
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for i, result in enumerate(results):
                    if isinstance(result, list):
                        agent = self._agents_cache[i]
                        for remote_session in result:
                            session = SessionConfig(
                                id=remote_session.get("id", ""),
                                title=remote_session.get("title", f"Chat with {agent.name}"),
                                node_id=agent.node_id,
                                agent_name=agent.name,
                                agent_description=agent.bio,
                                agent_address=agent.node_id,
                                created_at=remote_session.get("created_at", ""),
                                updated_at=remote_session.get("updated_at", ""),
                                message_count=remote_session.get("message_count", 0),
                                user_id=current_user_id
                            )
                            
                            # 检查是否已存在于本地缓存中，避免重复
                            if not any(s.id == session.id for s in all_sessions):
                                all_sessions.append(session)
                                
            except Exception as e:
                logger.error(f"Error in distributed session query: {e}")
        
        # 按更新时间排序
        all_sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return all_sessions
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages"""
        if session_id not in self._sessions_cache:
            # Session不在缓存中，可能已被删除或缓存失效，但仍返回True避免404错误
            logger.warning(f"Session {session_id} not found in cache, treating as already deleted")
            return True
        
        session = self._sessions_cache[session_id]
        node_id = session.node_id
        
        del self._sessions_cache[session_id]
        if session_id in self._messages_cache:
            del self._messages_cache[session_id]
        
        # Notify agent about session deletion
        asyncio.create_task(self._notify_agent_session_deleted(node_id, session_id))
        
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
        node_id = session.node_id
        
        self._messages_cache[session_id] = []
        
        # Update session message count and timestamp
        session.message_count = 0
        session.updated_at = datetime.now().isoformat()
        
        # Notify agent to clear server-side session
        asyncio.create_task(self._notify_agent_session_cleared(node_id, session_id))
        
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
                "id": session.node_id,
                "name": session.agent_name,
                "description": session.agent_description
            }
        }
    
    # --- Agent Session Notification Methods ---
    
    async def _notify_agent_lifecycle(self, node_id: str, session_id: str, action: str):
        """Unified method to notify agent about session lifecycle events using standardized format"""
        try:
            logger.info(f"Attempting to notify node {node_id} about session {session_id} {action}")
            
            if not self._network_status.connected:
                logger.warning(f"Network not connected, skipping notification for session {action}")
                return
            
            if not self.node:
                logger.warning(f"Node not initialized, skipping notification for session {action}")
                return
            
            # Create standardized session lifecycle message
            message_string = create_session_lifecycle_message_json(
                session_id=session_id,
                user_id=self.node_id,  # client's node_id as user_id
                action=action
            )
            logger.info(f"Created lifecycle message: {message_string}")
            
            agent = self.get_agent_by_id(node_id)
            if agent:
                logger.info(f"Sending message to node {agent.node_id}")
                # Send to agent (agent.node_id is the server's node_id)
                response = self.node.send_message(agent.node_id, message_string)
                logger.info(f"Notified node {node_id} about session {session_id} {action}, response: {response}")
            else:
                logger.warning(f"Node {node_id} not found in cache, skipping notification")
        except Exception as e:
            logger.error(f"Failed to notify node {node_id} about session {action}: {e}")
            import traceback
            traceback.print_exc()
    
    async def _notify_agent_session_created(self, node_id: str, session_id: str):
        await self._notify_agent_lifecycle(node_id, session_id, "created")
    
    async def _notify_agent_session_deleted(self, node_id: str, session_id: str):
        await self._notify_agent_lifecycle(node_id, session_id, "deleted")
    
    async def _notify_agent_session_cleared(self, node_id: str, session_id: str):
        await self._notify_agent_lifecycle(node_id, session_id, "cleared")

# --- Client Factory ---

_client_instance = None

def get_client(node_id: str = None, registry_host: str = None, registry_port: int = None) -> ISEKClient:
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