import json
import sqlite3
from typing import List
from mapper.models import Message

class MessageMapper:
    def __init__(self, db_path: str = 'isek_database.db'):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
    
    def _init_db(self):
        """初始化数据库，如果表不存在则创建"""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS message (
                id TEXT PRIMARY KEY,
                sessionId TEXT,
                content TEXT,
                role TEXT,
                timestamp TEXT,
                creatorId TEXT
            )
        ''')
        self.conn.commit()
    
    def create_message(self, message: Message) -> Message:
        """创建新消息"""
        cursor = self.conn.cursor()
        # if isinstance(message.content, list):
        message.content = json.dumps(message.content)
        cursor.execute('''
            INSERT INTO message (
                id, sessionId, content, role, timestamp, creatorId
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            message.id,
            message.sessionId,
            message.content,
            message.role,
            message.timestamp,
            message.creatorId
        ))
        self.conn.commit()
        return message
    
    def get_messages_by_session(self, session_id: str) -> List[Message]:
        """根据会话ID获取所有消息"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM message WHERE sessionId = ? ORDER BY timestamp', (session_id,))
        messages = []
        for row in cursor.fetchall():
            message = Message.from_dict(row)
            message.content = json.loads(message.content)
            messages.append(message)
        return messages
    
    def delete_messages_by_session(self, session_id: str) -> bool:
        """根据会话ID删除所有消息"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM message WHERE sessionId = ?', (session_id,))
        self.conn.commit()
        return cursor.rowcount > 0


