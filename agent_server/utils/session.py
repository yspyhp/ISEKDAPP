"""
Session Management Utilities
会话管理工具类 - 基于a2a native服务的增强会话管理
"""

from typing import List, Optional, Dict
from datetime import datetime

try:
    from a2a.sessions import InMemorySessionService
    A2A_AVAILABLE = True
except ImportError:
    A2A_AVAILABLE = False
    # Fallback base class
    class InMemorySessionService:
        def __init__(self):
            self._sessions = {}


class ConversationTurn:
    """对话轮次数据结构"""
    def __init__(self, user_input: str, agent_response: str, timestamp: datetime = None):
        self.user_input = user_input
        self.agent_response = agent_response
        self.timestamp = timestamp or datetime.now()
        self.metadata = {}
    
    def to_dict(self) -> dict:
        return {
            "user_input": self.user_input,
            "agent_response": self.agent_response,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


class SessionStore(InMemorySessionService):
    """增强的会话存储管理器 - 基于a2a native服务"""
    
    def __init__(self):
        super().__init__()
        self.sessions = {}  # session_id -> session_data (ISEK扩展)
        self.conversation_history = {}  # session_id -> List[ConversationTurn]
        
    def create_session(self, session_id: str, user_id: str = "default") -> dict:
        """创建新会话"""
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "message_count": 0,
            "status": "active"
        }
        self.sessions[session_id] = session_data
        self.conversation_history[session_id] = []
        return session_data
    
    def get_session(self, session_id: str) -> Optional[dict]:
        """获取会话信息"""
        return self.sessions.get(session_id)
    
    def update_session_activity(self, session_id: str):
        """更新会话活动时间"""
        if session_id in self.sessions:
            self.sessions[session_id]["last_activity"] = datetime.now()
            self.sessions[session_id]["message_count"] += 1
    
    def add_conversation_turn(self, session_id: str, user_input: str, agent_response: str):
        """添加对话轮次"""
        # 确保会话存在
        if session_id not in self.conversation_history:
            self.create_session(session_id)
        
        # 添加对话轮次
        turn = ConversationTurn(user_input, agent_response)
        self.conversation_history[session_id].append(turn)
        
        # 更新会话活动
        self.update_session_activity(session_id)
    
    def get_conversation_history(self, session_id: str, limit: int = 10) -> List[ConversationTurn]:
        """获取对话历史"""
        if session_id not in self.conversation_history:
            return []
        
        history = self.conversation_history[session_id]
        return history[-limit:] if limit > 0 else history
    
    def get_conversation_context(self, session_id: str, limit: int = 5) -> str:
        """获取对话上下文字符串"""
        history = self.get_conversation_history(session_id, limit)
        if not history:
            return ""
        
        context_parts = []
        for turn in history:
            context_parts.append(f"User: {turn.user_input}")
            context_parts.append(f"Assistant: {turn.agent_response}")
        
        return "\n".join(context_parts)
    
    def clear_session(self, session_id: str):
        """清空会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
        if session_id in self.conversation_history:
            del self.conversation_history[session_id]
    
    def get_session_summary(self, session_id: str) -> dict:
        """获取会话摘要"""
        session = self.get_session(session_id)
        if not session:
            return {}
        
        history_count = len(self.conversation_history.get(session_id, []))
        
        return {
            "session_id": session_id,
            "user_id": session["user_id"],
            "created_at": session["created_at"],
            "last_activity": session["last_activity"],
            "message_count": session["message_count"],
            "conversation_turns": history_count,
            "status": session["status"]
        }


class SessionManager:
    """会话管理器 - 专注于会话管理，不涉及Memory"""
    
    def __init__(self):
        self.session_store = SessionStore()
        self.active_contexts = {}  # A2A context_id到session_id的映射
        
    def create_session_context(self, context_id: str, user_id: str = "default") -> dict:
        """为A2A上下文创建会话"""
        # 使用context_id作为session_id，保持简单映射
        session_data = self.session_store.create_session(context_id, user_id)
        self.active_contexts[context_id] = context_id
        return session_data
        
    def get_session_context(self, context_id: str) -> Optional[dict]:
        """获取会话上下文"""
        session_id = self.active_contexts.get(context_id, context_id)
        return self.session_store.get_session(session_id)
        
    def update_session_activity(self, context_id: str):
        """更新会话活动时间"""
        session_id = self.active_contexts.get(context_id, context_id)
        self.session_store.update_session_activity(session_id)
            
    def get_conversation_history(self, context_id: str, limit: int = 10) -> List[ConversationTurn]:
        """获取对话历史"""
        session_id = self.active_contexts.get(context_id, context_id)
        return self.session_store.get_conversation_history(session_id, limit)
    
    def get_conversation_context(self, context_id: str, limit: int = 5) -> str:
        """获取对话上下文字符串"""
        session_id = self.active_contexts.get(context_id, context_id)
        return self.session_store.get_conversation_context(session_id, limit)
        
    def save_conversation_turn(self, context_id: str, user_input: str, agent_response: str):
        """保存对话轮次"""
        session_id = self.active_contexts.get(context_id, context_id)
        self.session_store.add_conversation_turn(session_id, user_input, agent_response)
    
    def get_session_summary(self, context_id: str) -> dict:
        """获取会话摘要"""
        session_id = self.active_contexts.get(context_id, context_id)
        return self.session_store.get_session_summary(session_id)