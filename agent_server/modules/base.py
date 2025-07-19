"""
Base classes for modular SessionAdapter components
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from mapper.models import Session, Message


class BaseSessionManager(ABC):
    """Abstract base class for session management"""
    
    @abstractmethod
    def get_user_sessions(self, creator_id: str) -> List[Session]:
        """Get all sessions for a user"""
        pass
    
    @abstractmethod
    def get_session_by_id(self, session_id: str, creator_id: str) -> Optional[Session]:
        """Get a specific session by ID"""
        pass
    
    @abstractmethod
    def create_session(self, session: Session) -> Session:
        """Create a new session"""
        pass
    
    @abstractmethod
    def delete_session(self, session_id: str, creator_id: str) -> bool:
        """Delete a session"""
        pass
    
    @abstractmethod
    def get_session_messages(self, session_id: str, creator_id: str) -> List[Message]:
        """Get all messages in a session"""
        pass
    
    @abstractmethod
    def create_message(self, message: Message, creator_id: str) -> Message:
        """Create a new message in a session"""
        pass


class BaseTaskManager(ABC):
    """Abstract base class for task management"""
    
    @abstractmethod
    async def execute_task(self, task_type: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task and return results"""
        pass
    
    @abstractmethod
    def get_available_tasks(self) -> List[str]:
        """Get list of available task types"""
        pass
    
    @abstractmethod
    def validate_task_data(self, task_type: str, task_data: Dict[str, Any]) -> bool:
        """Validate task data for a given task type"""
        pass


class BaseMessageHandler(ABC):
    """Abstract base class for message handling"""
    
    @abstractmethod
    def parse_message(self, message: str) -> Dict[str, Any]:
        """Parse incoming message"""
        pass
    
    @abstractmethod
    def format_response(self, response_data: Dict[str, Any]) -> str:
        """Format response for sending back to client"""
        pass
    
    @abstractmethod
    async def handle_chat_message(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle chat message and generate response"""
        pass
    
    @abstractmethod
    async def handle_session_lifecycle(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle session lifecycle events"""
        pass
    
    @abstractmethod
    def get_message_type(self, parsed_data: Dict[str, Any]) -> str:
        """Extract message type from parsed data"""
        pass