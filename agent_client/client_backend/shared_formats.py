"""
Shared message formats between client and server
This should match the formats in agent_server/shared/message_formats.py
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
import json


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


def create_chat_message_json(session_id: str, user_id: str, messages: List[Dict], 
                            system_prompt: str = "", user_message: str = "") -> str:
    """Create a standardized chat message JSON"""
    msg = ChatMessage(
        session_id=session_id,
        user_id=user_id,
        messages=messages,
        system_prompt=system_prompt,
        user_message=user_message
    )
    return json.dumps({
        "type": msg.type,
        "session_id": msg.session_id,
        "user_id": msg.user_id,
        "messages": msg.messages,
        "system_prompt": msg.system_prompt,
        "user_message": msg.user_message,
        "timestamp": msg.timestamp,
        "request_id": msg.request_id
    })


def create_session_lifecycle_message_json(session_id: str, user_id: str, action: str) -> str:
    """Create a standardized session lifecycle message JSON"""
    msg = SessionLifecycleMessage(
        session_id=session_id,
        user_id=user_id,
        action=action
    )
    return json.dumps({
        "type": msg.type,
        "session_id": msg.session_id,
        "user_id": msg.user_id,
        "action": msg.action,
        "timestamp": msg.timestamp,
        "request_id": msg.request_id
    })


def create_task_message_json(session_id: str, user_id: str, task_type: str, task_data: Dict[str, Any]) -> str:
    """Create a standardized task message JSON"""
    msg = TaskMessage(
        session_id=session_id,
        user_id=user_id,
        task_type=task_type,
        task_data=task_data
    )
    return json.dumps({
        "type": msg.type,
        "session_id": msg.session_id,
        "user_id": msg.user_id,
        "task_type": msg.task_type,
        "task_data": msg.task_data,
        "timestamp": msg.timestamp,
        "request_id": msg.request_id
    })


def parse_agent_response(response_json: str) -> Dict[str, Any]:
    """Parse standardized agent response"""
    try:
        data = json.loads(response_json)
        return {
            "success": data.get("success", False),
            "content": data.get("content", ""),
            "tool_calls": data.get("tool_calls", []),
            "timestamp": data.get("timestamp", ""),
            "request_id": data.get("request_id", ""),
            "error": data.get("error", "")
        }
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "content": "",
            "tool_calls": [],
            "timestamp": datetime.now().isoformat(),
            "request_id": "",
            "error": f"Failed to parse response: {str(e)}"
        }