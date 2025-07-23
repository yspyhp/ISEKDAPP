from datetime import datetime
from typing import List
from mapper.models import Session, Message

class SessionService:
    def __init__(self):
        from mapper import sessionMapper, messageMapper
        self.session_mapper = sessionMapper
        self.message_mapper = messageMapper
    
    def get_user_sessions(self, creator_id: str) -> List[Session]:
        """获取用户所有会话"""
        if not creator_id:
            raise ValueError("creator_id is required")
        return self.session_mapper.get_sessions(creator_id)

    def get_session_by_id(self, session_id: str, creator_id: str) -> Session:
        """获取用户所有会话"""
        if not creator_id:
            raise ValueError("creator_id is required")
        return self.session_mapper.get_by_id(session_id, creator_id)
    
    def create_session(self, session: Session) -> Session:
        """创建新会话"""
        if not session.creatorId:
            raise ValueError("creator_id is required")
        
        # Set default timestamp
        if not session.createdAt:
            session.createdAt = datetime.now().isoformat()
        if not session.updatedAt:
            session.updatedAt = session.createdAt
            
        return self.session_mapper.create_session(session)
    
    def delete_session(self, session_id: str, creator_id: str) -> bool:
        """删除会话，同时删除关联的消息"""
        if not creator_id:
            raise ValueError("creator_id is required")
            
        # Verify session belongs to user
        sessions = self.session_mapper.get_sessions(creator_id)
        if not any(s.id == session_id for s in sessions):
            raise PermissionError("Unauthorized access to session")
            
        # Delete messages in session first
        self.message_mapper.delete_messages_by_session(session_id)
        # Then delete session
        return self.session_mapper.delete_session(session_id, creator_id)
    
    def get_session_messages(self, session_id: str, creator_id: str) -> List[Message]:
        """根据会话ID获取消息，需验证用户权限"""
        if not creator_id:
            raise ValueError("creator_id is required")
            
        # Verify session belongs to user
        sessions = self.session_mapper.get_sessions(creator_id)
        if not any(s.id == session_id for s in sessions):
            raise PermissionError("Unauthorized access to session messages")
            
        return self.message_mapper.get_messages_by_session(session_id)
    
    def create_message(self, message: Message, creator_id: str) -> Message:
        """创建消息，需验证会话属于该用户"""
        if not creator_id:
            raise ValueError("creator_id is required")
        if not message.sessionId:
            raise ValueError("session_id is required")
            
        # Verify session belongs to user
        # sessions = self.session_mapper.get_sessions(creator_id)
        # if not any(s.id == message.session_id for s in sessions):
        #     raise PermissionError("Unauthorized access to session")
            
        # Set default timestamp
        if not message.timestamp:
            message.timestamp = datetime.now().isoformat()
            
        return self.message_mapper.create_message(message)

#
# from datetime import datetime
#
# session_json = {
#     'id': 'session1',
#     'title': 'Test Session',
#     'agent_id': 'agent123',
#     'agent_name': 'Test Agent',
#     'agent_description': 'This is a test agent',
#     'agent_address': 'http://localhost:8000',
#     'created_at': datetime.now().isoformat(),
#     'updated_at': datetime.now().isoformat(),
#     'message_count': 0,
#     'creator_id': "123"
# }
# session = Session.from_dict(session_json)
#
# message_json = {
#     'session_id': "session1",
#     'content': 'Hello, this is a test message',
#     'role': 'user',
#     'timestamp': datetime.now().isoformat(),
#     "creator_id": "123"
# }
# message = Message.from_dict(message_json)
#
#
# sessionService = SessionService()
# # print(sessionService.create_session(session))
#
# # print(sessionService.create_message(message, creator_id="123"))
#
# # print(sessionService.get_session_messages(session_id="session1", creator_id="123"))
#
# # print(sessionService.delete_session(session_id=1, creator_id=123))
#
# # print(sessionService.get_session_messages(session_id=1, creator_id=123))
