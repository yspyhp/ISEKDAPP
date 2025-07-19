"""
Shared message formats between client and server
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid


@dataclass
class ChatMessage:
    """Standard chat message format"""
    type: str = "chat"
    session_id: str = ""
    user_id: str = ""  # client's node_id
    messages: List[Dict[str, Any]] = field(default_factory=list)
    system_prompt: str = ""
    user_message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class SessionLifecycleMessage:
    """Session lifecycle message format"""
    type: str = "session_lifecycle"
    session_id: str = ""
    user_id: str = ""  # client's node_id
    action: str = ""  # created, deleted, cleared
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class TaskMessage:
    """Task execution message format"""
    type: str = "task"
    session_id: str = ""
    user_id: str = ""  # client's node_id
    task_type: str = ""
    task_data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class AgentResponse:
    """Standard agent response format"""
    success: bool = True
    content: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    request_id: str = ""
    error: str = ""


@dataclass
class AgentConfigFormat:
    """Agent configuration format matching client expectations"""
    id: str = ""
    name: str = ""
    description: str = ""
    system_prompt: str = ""
    model: str = ""
    address: str = ""  # same as id for server agents
    capabilities: List[str] = field(default_factory=list)
    status: str = "active"


def create_chat_message(session_id: str, user_id: str, messages: List[Dict], 
                       system_prompt: str = "", user_message: str = "") -> Dict[str, Any]:
    """Create a standardized chat message"""
    msg = ChatMessage(
        session_id=session_id,
        user_id=user_id,
        messages=messages,
        system_prompt=system_prompt,
        user_message=user_message
    )
    return {
        "type": msg.type,
        "session_id": msg.session_id,
        "user_id": msg.user_id,
        "messages": msg.messages,
        "system_prompt": msg.system_prompt,
        "user_message": msg.user_message,
        "timestamp": msg.timestamp,
        "request_id": msg.request_id
    }


def create_session_lifecycle_message(session_id: str, user_id: str, action: str) -> Dict[str, Any]:
    """Create a standardized session lifecycle message"""
    msg = SessionLifecycleMessage(
        session_id=session_id,
        user_id=user_id,
        action=action
    )
    return {
        "type": msg.type,
        "session_id": msg.session_id,
        "user_id": msg.user_id,
        "action": msg.action,
        "timestamp": msg.timestamp,
        "request_id": msg.request_id
    }


def create_task_message(session_id: str, user_id: str, task_type: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a standardized task message"""
    msg = TaskMessage(
        session_id=session_id,
        user_id=user_id,
        task_type=task_type,
        task_data=task_data
    )
    return {
        "type": msg.type,
        "session_id": msg.session_id,
        "user_id": msg.user_id,
        "task_type": msg.task_type,
        "task_data": msg.task_data,
        "timestamp": msg.timestamp,
        "request_id": msg.request_id
    }


def create_agent_response(success: bool = True, content: str = "", tool_calls: List[Dict] = None, 
                         error: str = "", request_id: str = "") -> Dict[str, Any]:
    """Create a standardized agent response"""
    response = AgentResponse(
        success=success,
        content=content,
        tool_calls=tool_calls or [],
        error=error,
        request_id=request_id
    )
    return {
        "success": response.success,
        "content": response.content,
        "tool_calls": response.tool_calls,
        "timestamp": response.timestamp,
        "request_id": response.request_id,
        "error": response.error
    }


def create_agent_config(node_id: str, name: str, description: str, system_prompt: str, 
                       model: str, capabilities: List[str]) -> Dict[str, Any]:
    """Create a standardized agent config"""
    config = AgentConfigFormat(
        id=node_id,
        name=name,
        description=description,
        system_prompt=system_prompt,
        model=model,
        address=node_id,  # node_id serves as address for server
        capabilities=capabilities
    )
    return {
        "id": config.id,
        "name": config.name,
        "description": config.description,
        "system_prompt": config.system_prompt,
        "model": config.model,
        "address": config.address,
        "capabilities": config.capabilities,
        "status": config.status
    }