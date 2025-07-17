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
    id: Optional[str] = None
    title: str = ""
    agentId: str = ""
    agentName: str = ""
    agentDescription: str = ""
    agentAddress: str = ""
    createdAt: str = datetime.now().isoformat()
    updatedAt: str = datetime.now().isoformat()
    messageCount: int = 0
    creatorId: str = ""
    updaterId: str = ""
    
    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建Session对象"""
        return cls(**data)

@dataclass
class Message:
    """消息数据模型"""
    id: Optional[str] = None
    sessionId: str = ""
    content: str = ""
    role: str = ""  # user/assistant
    timestamp: str = datetime.now().isoformat()
    creatorId: str = ""
    
    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建Message对象"""
        return cls(**data)

@dataclass
class Task:
    """任务数据模型"""
    id: Optional[str] = None
    sessionId: str = ""
    title: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.INIT
    progress: int = 0
    createdAt: str = datetime.now().isoformat()
    updatedAt: str = datetime.now().isoformat()
    creatorId: str = ""
    updaterId: str = ""
    result: str = ""
    
    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建Task对象"""
        return cls(**data)