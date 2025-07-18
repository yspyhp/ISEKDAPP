import sqlite3
from typing import Optional, List
from mapper.models import Task

class TaskMapper:
    """Task数据操作类"""
    
    def __init__(self, db_path: str = 'isek_database.db'):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
    
    def _init_db(self):
        """初始化数据库，如果表不存在则创建"""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task (
                id TEXT PRIMARY KEY,
                sessionId TEXT,
                title TEXT,
                description TEXT,
                status TEXT,
                progress INTEGER,
                createdAt TEXT,
                updatedAt TEXT,
                creatorId TEXT,
                updaterId TEXT,
                result TEXT
            )
        ''')
        self.conn.commit()
    
    def create(self, task: Task, creator_id: str) -> Optional[Task]:
        """创建新任务"""
        if not creator_id:
            return None
            
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO task (
                id, sessionId, title, description, status, progress,
                createdAt, updatedAt, creatorId, updaterId, result
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            task.id,
            task.sessionId,
            task.title,
            task.description,
            task.status,
            task.createdAt,
            task.updatedAt,
            creator_id,
            creator_id
        ))
        self.conn.commit()
        return task
    
    def get_by_id(self, task_id: str, creator_id: str) -> Optional[Task]:
        """根据ID获取任务"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM task WHERE id = ? AND creatorId = ?',
                      (task_id, creator_id))
        row = cursor.fetchone()
        return Task.from_dict(row) if row else None
    
    def get_by_session_id(self, session_id: str, creator_id: str) -> List[Task]:
        """根据会话ID获取任务列表"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM task WHERE sessionId = ? AND creatorId = ?',
                      (session_id, creator_id))
        return [Task.from_dict(row) for row in cursor.fetchall()]
    
    def processing(self, task_id: str, updater_id: str) -> bool:
        """将任务状态设置为processing"""
        if not updater_id:
            return False
            
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE task 
            SET status = ?, updatedAt = datetime('now'), updaterId = ?
            WHERE id = ? AND creatorId = ?
        ''', ('processing', updater_id, task_id, updater_id))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def finish(self, task_id: str, updater_id: str, result: str) -> bool:
        """将任务状态设置为finished"""
        if not updater_id:
            return False
            
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE task 
            SET status = ?, updatedAt = datetime('now'), updaterId = ?, result = ?
            WHERE id = ? AND creatorId = ?
        ''', ('finished', updater_id, result, task_id, updater_id))
        self.conn.commit()
        return cursor.rowcount > 0
    
    