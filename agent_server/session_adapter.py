from agno.agent import Agent
from agno.models.deepseek import DeepSeek
from agno.models.openai import OpenAIChat

from isek.adapter.base import Adapter, AdapterCard
from isek.node.etcd_registry import EtcdRegistry
from isek.node.node_v2 import Node
from typing import List
from mapper.models import Session, Message
import dotenv
from isek.utils.log import LoggerManager
from isek.utils.log import log
import json

LoggerManager.plain_mode()
dotenv.load_dotenv()
class SessionAdapter(Adapter):

    def __init__(self):
        from service import sessionService, taskService
        self.sessionService = sessionService
        self.taskService = taskService

    def get_user_sessions(self, creator_id: str) -> List[Session]:
        """获取用户所有会话"""
        return self.sessionService.get_user_sessions(creator_id)

    def get_session_by_id(self, session_id: str, creator_id: str) -> Session:
        """获取用户所有会话"""
        return self.sessionService.get_session_by_id(session_id, creator_id)

    def create_session(self, session: Session) -> Session:
        """创建新会话"""
        return self.sessionService.create_session(session)

    def delete_session(self, session_id: str, creator_id: str) -> bool:
        """删除会话，同时删除关联的消息"""
        return self.sessionService.delete_session(session_id, creator_id)

    def get_session_messages(self, session_id: str, creator_id: str) -> List[Message]:
        """根据会话ID获取消息，需验证用户权限"""
        return self.sessionService.get_session_messages(session_id, creator_id)

    def create_message(self, message: Message, creator_id: str) -> Message:
        """创建消息，需验证会话属于该用户"""
        return self.sessionService.create_message(message, creator_id)
