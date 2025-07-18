import sqlite3
from typing import List, Optional
from mapper.models import Session

class SessionMapper:
    def __init__(self, db_path: str = 'isek_database.db'):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
    
    def _init_db(self):
        """初始化数据库，如果表不存在则创建"""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS session (
                id TEXT PRIMARY KEY,
                title TEXT,
                agentId INTEGER,
                agentName TEXT,
                agentDescription TEXT,
                agentAddress TEXT,
                createdAt TEXT,
                updatedAt TEXT,
                messageCount INTEGER DEFAULT 0,
                creatorId TEXT,
                updaterId TEXT
            )
        ''')
        self.conn.commit()
    
    def create_session(self, session: Session) -> Session:
        """创建新会话"""
        if not session.creatorId:
            raise ValueError("creatorId is required")
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO session (
                id, title, agentId, agentName, agentDescription, 
                agentAddress, createdAt, updatedAt, messageCount, creatorId
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session.id,
            session.title,
            session.agentId,
            session.agentName,
            session.agentDescription,
            session.agentAddress,
            session.createdAt,
            session.updatedAt,
            session.messageCount,
            session.creatorId
        ))
        self.conn.commit()
        return session
    
    def get_sessions(self, creator_id: str) -> List[Session]:
        """获取指定creator_id的所有会话"""
        if creator_id is None:
            raise ValueError("creator_id is required")
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM session WHERE creatorId = ?', (creator_id,))
        sessions = []
        for row in cursor.fetchall():
            session = Session.from_dict(row)
            sessions.append(session)
        return sessions
    
    def delete_session(self, session_id: str, creator_id: str) -> bool:
        """删除会话，必须验证creator_id权限"""
        if creator_id is None:
            raise ValueError("creator_id is required")
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM session WHERE id = ? AND creatorId = ?', (session_id, creator_id))
        self.conn.commit()
        return cursor.rowcount > 0

    def get_by_id(self, session_id: str, creator_id: str) -> Optional[Session]:
        """根据ID获取session"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM session WHERE id = ? AND creatorId = ?',
                      (session_id, creator_id))
        row = cursor.fetchone()
        return Session.from_dict(row) if row else None
    


