from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from enum import Enum, auto

class TaskStatus(Enum):
    """任务状态枚举"""
    INIT = auto()
    PROCESSING = auto()
    FINISH = auto()

@dataclass
class Session:
    """会话数据模型"""
    id: Optional[int] = None
    title: str = ""
    agent_id: int = 0
    agent_name: str = ""
    agent_description: str = ""
    agent_address: str = ""
    created_at: str = datetime.now().isoformat()
    updated_at: str = datetime.now().isoformat()
    message_count: int = 0
    creator_id: int = 0
    updater_id: int = 0
    
    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建Session对象"""
        return cls(**data)

@dataclass
class Message:
    """消息数据模型"""
    id: Optional[int] = None
    session_id: int = 0
    content: str = ""
    role: str = ""  # user/assistant
    timestamp: str = datetime.now().isoformat()
    creator_id: int = 0
    
    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建Message对象"""
        return cls(**data)

@dataclass
class Task:
    """任务数据模型"""
    id: Optional[int] = None
    session_id: int = 0
    title: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.INIT
    progress: int = 0
    created_at: str = datetime.now().isoformat()
    updated_at: str = datetime.now().isoformat()
    creator_id: int = 0
    updater_id: int = 0
    result: str = ""
    
    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建Task对象"""
        return cls(**data)