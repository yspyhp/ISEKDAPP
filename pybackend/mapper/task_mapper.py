import sqlite3
from typing import Optional, List
from mapper.models import Task

class TaskMapper:
    """Task数据操作类"""
    
    def __init__(self, db_path: str = 'isek_database.db'):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
    
    def _init_db(self):
        """初始化数据库，如果表不存在则创建"""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                title TEXT,
                description TEXT,
                status TEXT,
                progress INTEGER,
                created_at TEXT,
                updated_at TEXT,
                creator_id INTEGER,
                updater_id INTEGER,
                result TEXT
            )
        ''')
        self.conn.commit()
    
    def create(self, task: Task, creator_id: int) -> Optional[Task]:
        """创建新任务"""
        if not creator_id:
            return None
            
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO task (
                session_id, title, description, status, progress,
                created_at, updated_at, creator_id, updater_id, result
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            task.session_id,
            task.title,
            task.description,
            task.status,
            task.created_at,
            task.updated_at,
            creator_id,
            creator_id
        ))
        self.conn.commit()
        task.id = cursor.lastrowid
        return task
    
    def get_by_id(self, task_id: int, creator_id: int) -> Optional[Task]:
        """根据ID获取任务"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM task WHERE id = ? AND creator_id = ?', 
                      (task_id, creator_id))
        row = cursor.fetchone()
        return Task.from_dict(row) if row else None
    
    def get_by_session_id(self, session_id: int, creator_id: int) -> List[Task]:
        """根据会话ID获取任务列表"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM task WHERE session_id = ? AND creator_id = ?', 
                      (session_id, creator_id))
        return [Task.from_dict(row) for row in cursor.fetchall()]
    
    def processing(self, task_id: int, updater_id: int) -> bool:
        """将任务状态设置为processing"""
        if not updater_id:
            return False
            
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE task 
            SET status = ?, updated_at = datetime('now'), updater_id = ?
            WHERE id = ? AND creator_id = ?
        ''', ('processing', updater_id, task_id, updater_id))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def finish(self, task_id: int, updater_id: int, result: str) -> bool:
        """将任务状态设置为finished"""
        if not updater_id:
            return False
            
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE task 
            SET status = ?, updated_at = datetime('now'), updater_id = ?, result = ?
            WHERE id = ? AND creator_id = ?
        ''', ('finished', updater_id, result, task_id, updater_id))
        self.conn.commit()
        return cursor.rowcount > 0
    
    