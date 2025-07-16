import sqlite3
from typing import List, Optional
from mapper.models import Session

class SessionMapper:
    def __init__(self, db_path: str = 'isek_database.db'):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
    
    def _init_db(self):
        """初始化数据库，如果表不存在则创建"""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS session (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                agent_id INTEGER,
                agent_name TEXT,
                agent_description TEXT,
                agent_address TEXT,
                created_at TEXT,
                updated_at TEXT,
                message_count INTEGER DEFAULT 0,
                creator_id INTEGER,
                updater_id INTEGER
            )
        ''')
        self.conn.commit()
    
    def create_session(self, session: Session) -> Session:
        """创建新会话"""
        if not session.creator_id:
            raise ValueError("creator_id is required")
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO session (
                title, agent_id, agent_name, agent_description, 
                agent_address, created_at, updated_at, message_count, creator_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session.title,
            session.agent_id,
            session.agent_name,
            session.agent_description,
            session.agent_address,
            session.created_at,
            session.updated_at,
            session.message_count,
            session.creator_id
        ))
        self.conn.commit()
        session.id = cursor.lastrowid
        return session
    
    def get_sessions(self, creator_id: int) -> List[Session]:
        """获取指定creator_id的所有会话"""
        if creator_id is None:
            raise ValueError("creator_id is required")
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM session WHERE creator_id = ?', (creator_id,))
        sessions = []
        for row in cursor.fetchall():
            session = Session.from_dict(row)
            sessions.append(session)
        return sessions
    
    def delete_session(self, session_id: int, creator_id: int) -> bool:
        """删除会话，必须验证creator_id权限"""
        if creator_id is None:
            raise ValueError("creator_id is required")
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM session WHERE id = ? AND creator_id = ?', (session_id, creator_id))
        self.conn.commit()
        return cursor.rowcount > 0

    def get_by_id(self, session_id: int, creator_id: int) -> Optional[Session]:
        """根据ID获取session"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM session WHERE id = ? AND creator_id = ?',
                      (session_id, creator_id))
        row = cursor.fetchone()
        return Session.from_dict(row) if row else None
    


