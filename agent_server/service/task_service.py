from typing import Optional
from mapper.task_mapper import TaskMapper
from mapper.session_mapper import SessionMapper
from mapper.models import Task

class TaskService:
    """任务管理服务"""
    
    def __init__(self, db_path: str = 'isek_database.db'):
        from mapper import sessionMapper, taskMapper
        self.session_mapper = sessionMapper
        self.task_mapper = taskMapper
    
    def create_task(self, task: Task, creator_id: str) -> Optional[Task]:
        """Create new task with creator_id validation"""
        if not creator_id:
            return None
        
        # Verify session belongs to user
        session = self.session_mapper.get_by_id(task.sessionId, creator_id)
        if not session:
            raise PermissionError("Unauthorized access to session")
            
        return self.task_mapper.create(task, creator_id)
    
    def start_processing(self, task_id: str, session_id: str, updater_id: str) -> bool:
        """Set task status to processing with updater_id validation"""
        if not updater_id:
            return False
            
        # Verify session belongs to user
        session = self.session_mapper.get_by_id(session_id, updater_id)
        if not session:
            raise PermissionError("Unauthorized access to session")
            
        return self.task_mapper.processing(task_id, updater_id)
    
    def finish_task(self, task_id: str, session_id: str, updater_id: str, result: str) -> bool:
        """Complete task with updater_id validation"""
        if not updater_id:
            return False
            
        # Verify session belongs to user
        session = self.session_mapper.get_by_id(session_id, updater_id)
        if not session:
            raise PermissionError("Unauthorized access to session")
            
        return self.task_mapper.finish(task_id, updater_id, result)
    
    def get_task_by_id(self, task_id: str, session_id: str, creator_id: str) -> Optional[Task]:
        """根据ID获取任务，需要验证creator_id"""
        if not creator_id:
            return None
            
        # Verify session belongs to user
        session = self.session_mapper.get_by_id(session_id, creator_id)
        if not session:
            raise PermissionError("Unauthorized access to session")
            
        return self.task_mapper.get_by_id(task_id, creator_id)