import sqlite3
from typing import List
from mapper.models import Message

class MessageMapper:
    def __init__(self, db_path: str = 'isek_database.db'):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
    
    def _init_db(self):
        """初始化数据库，如果表不存在则创建"""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS message (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                content TEXT,
                role TEXT,
                timestamp TEXT
            )
        ''')
        self.conn.commit()
    
    def create_message(self, message: Message) -> Message:
        """创建新消息"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO message (
                session_id, content, role, timestamp
            ) VALUES (?, ?, ?, ?)
        ''', (
            message.session_id,
            message.content,
            message.role,
            message.timestamp
        ))
        self.conn.commit()
        message.id = cursor.lastrowid
        return message
    
    def get_messages_by_session(self, session_id: int) -> List[Message]:
        """根据会话ID获取所有消息"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM message WHERE session_id = ? ORDER BY timestamp', (session_id,))
        messages = []
        for row in cursor.fetchall():
            message = Message.from_dict(row)
            messages.append(message)
        return messages
    
    def delete_messages_by_session(self, session_id: int) -> bool:
        """根据会话ID删除所有消息"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM message WHERE session_id = ?', (session_id,))
        self.conn.commit()
        return cursor.rowcount > 0


