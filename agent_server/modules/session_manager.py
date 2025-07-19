"""
Default implementation of session management module
"""

from typing import List, Optional
from .base import BaseSessionManager
from mapper.models import Session, Message
from service.session_service import SessionService
from isek.utils.log import log


class DefaultSessionManager(BaseSessionManager):
    """Default implementation of session management"""
    
    def __init__(self):
        self.session_service = SessionService()
        log.info("DefaultSessionManager initialized")
    
    def get_user_sessions(self, creator_id: str) -> List[Session]:
        """Get all sessions for a user"""
        try:
            return self.session_service.get_user_sessions(creator_id)
        except Exception as e:
            log.error(f"Error getting user sessions: {e}")
            return []
    
    def get_session_by_id(self, session_id: str, creator_id: str) -> Optional[Session]:
        """Get a specific session by ID"""
        try:
            return self.session_service.get_session_by_id(session_id, creator_id)
        except Exception as e:
            log.error(f"Error getting session by ID: {e}")
            return None
    
    def create_session(self, session: Session) -> Session:
        """Create a new session"""
        try:
            return self.session_service.create_session(session)
        except Exception as e:
            log.error(f"Error creating session: {e}")
            raise
    
    def delete_session(self, session_id: str, creator_id: str) -> bool:
        """Delete a session"""
        try:
            return self.session_service.delete_session(session_id, creator_id)
        except Exception as e:
            log.error(f"Error deleting session: {e}")
            return False
    
    def get_session_messages(self, session_id: str, creator_id: str) -> List[Message]:
        """Get all messages in a session"""
        try:
            return self.session_service.get_session_messages(session_id, creator_id)
        except Exception as e:
            log.error(f"Error getting session messages: {e}")
            return []
    
    def create_message(self, message: Message, creator_id: str) -> Message:
        """Create a new message in a session"""
        try:
            return self.session_service.create_message(message, creator_id)
        except Exception as e:
            log.error(f"Error creating message: {e}")
            raise