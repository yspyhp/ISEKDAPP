from datetime import datetime
from typing import List
from mapper.models import Session, Message

class SessionService:
    def __init__(self):
        from mapper import sessionMapper, messageMapper
        self.session_mapper = sessionMapper
        self.message_mapper = messageMapper
    
    def get_user_sessions(self, creator_id: int) -> List[Session]:
        """获取用户所有会话"""
        if not creator_id:
            raise ValueError("creator_id is required")
        return self.session_mapper.get_sessions(creator_id)
    
    def create_session(self, session: Session) -> Session:
        """创建新会话"""
        if not session.creator_id:
            raise ValueError("creator_id is required")
        
        # 设置默认时间戳
        if not session.created_at:
            session.created_at = datetime.now().isoformat()
        if not session.updated_at:
            session.updated_at = session.created_at
            
        return self.session_mapper.create_session(session)
    
    def delete_session(self, session_id: int, creator_id: int) -> bool:
        """删除会话，同时删除关联的消息"""
        if not creator_id:
            raise ValueError("creator_id is required")
            
        # 先验证会话是否属于该用户
        sessions = self.session_mapper.get_sessions(creator_id)
        if not any(s.id == session_id for s in sessions):
            raise PermissionError("Unauthorized access to session")
            
        # 先删除会话中的消息
        self.message_mapper.delete_messages_by_session(session_id)
        # 再删除会话
        return self.session_mapper.delete_session(session_id, creator_id)
    
    def get_session_messages(self, session_id: int, creator_id: int) -> List[Message]:
        """根据会话ID获取消息，需验证用户权限"""
        if not creator_id:
            raise ValueError("creator_id is required")
            
        # 验证会话是否属于该用户
        sessions = self.session_mapper.get_sessions(creator_id)
        if not any(s.id == session_id for s in sessions):
            raise PermissionError("Unauthorized access to session messages")
            
        return self.message_mapper.get_messages_by_session(session_id)
    
    def create_message(self, message: Message, creator_id: int) -> Message:
        """创建消息，需验证会话属于该用户"""
        if not creator_id:
            raise ValueError("creator_id is required")
        if not message.session_id:
            raise ValueError("session_id is required")
            
        # 验证会话是否属于该用户
        sessions = self.session_mapper.get_sessions(creator_id)
        if not any(s.id == message.session_id for s in sessions):
            raise PermissionError("Unauthorized access to session")
            
        # 设置默认时间戳
        if not message.timestamp:
            message.timestamp = datetime.now().isoformat()
            
        return self.message_mapper.create_message(message)
