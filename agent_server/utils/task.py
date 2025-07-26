"""
Task Management Utilities
任务管理工具类 - 增强的任务存储和生命周期管理
"""

from typing import Any, Optional, Dict, List
from datetime import datetime
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import Task, TaskState, TaskStatus


class TaskCancelledException(Exception):
    """任务取消异常"""
    pass


class EnhancedTaskStore(InMemoryTaskStore):
    """增强的任务存储，支持完整生命周期管理"""
    
    def __init__(self):
        super().__init__()
        self.task_metadata = {}  # 任务元数据
        self.task_history = {}   # 状态变更历史
        self.task_artifacts = {} # 任务产物
        self.task_progress = {}  # 任务进度
    
    async def create_task(self, task_id: str, context_id: str, metadata: dict = None):
        """创建新任务"""
        self.task_metadata[task_id] = {
            "context_id": context_id,
            "created_at": datetime.now(),
            "metadata": metadata or {}
        }
        self.task_history[task_id] = []
        await self.update_task_status(task_id, TaskState.submitted, metadata)
        
    async def update_task_status(self, task_id: str, status: TaskState, metadata: dict = None):
        """更新任务状态"""
        # 获取现有任务或创建新任务
        existing_task = await self.get(task_id)
        context_id = self.task_metadata.get(task_id, {}).get("context_id", "unknown")
        
        task_status = TaskStatus(state=status)
        
        if existing_task:
            # 更新现有任务
            existing_task.status = task_status
            await self.save(existing_task)
        else:
            # 创建新任务
            new_task_obj = Task(
                id=task_id, 
                contextId=context_id,
                status=task_status
            )
            await self.save(new_task_obj)
        
        # 记录状态变更历史
        if task_id not in self.task_history:
            self.task_history[task_id] = []
            
        self.task_history[task_id].append({
            "status": status,
            "timestamp": datetime.now(),
            "metadata": metadata or {}
        })
        
        # 更新元数据
        if metadata and task_id in self.task_metadata:
            self.task_metadata[task_id]["metadata"].update(metadata)
    
    async def add_task_artifact(self, task_id: str, artifact: Any):
        """添加任务产物"""
        if task_id not in self.task_artifacts:
            self.task_artifacts[task_id] = []
        self.task_artifacts[task_id].append({
            "artifact": artifact,
            "timestamp": datetime.now()
        })
        
    def get_task_progress(self, task_id: str) -> dict:
        """获取任务进度信息"""
        return {
            "current_status": self.get_task_status(task_id),
            "history": self.task_history.get(task_id, []),
            "metadata": self.task_metadata.get(task_id, {}),
            "artifacts": self.task_artifacts.get(task_id, []),
            "progress": self.task_progress.get(task_id, {})
        }
    
    def get_task_status(self, task_id: str) -> Optional[TaskState]:
        """获取任务状态"""
        # 直接从内存中获取任务状态，避免异步调用
        if task_id in self.tasks:
            # 创建一个简单的事件循环来获取任务
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果事件循环正在运行，使用create_task
                    task = loop.create_task(self.get(task_id))
                    # 这里我们无法直接等待，所以返回None
                    return None
                else:
                    # 如果事件循环没有运行，可以使用run_until_complete
                    task = loop.run_until_complete(self.get(task_id))
                    return task.status.state if task and task.status else None
            except Exception:
                # 如果出现任何问题，返回None
                return None
        return None
    
    def update_task_progress(self, task_id: str, progress: float, stage: str = None):
        """更新任务进度"""
        if task_id not in self.task_progress:
            self.task_progress[task_id] = {}
        self.task_progress[task_id].update({
            "progress": progress,
            "stage": stage,
            "updated_at": datetime.now()
        })

    def get_tasks_by_context(self, context_id: str) -> List[str]:
        """根据上下文ID获取任务列表"""
        return [
            task_id for task_id, metadata in self.task_metadata.items()
            if metadata.get("context_id") == context_id
        ]
    
    def get_task_summary(self, task_id: str) -> Dict:
        """获取任务摘要信息"""
        metadata = self.task_metadata.get(task_id, {})
        history = self.task_history.get(task_id, [])
        artifacts = self.task_artifacts.get(task_id, [])
        progress = self.task_progress.get(task_id, {})
        
        return {
            "task_id": task_id,
            "context_id": metadata.get("context_id"),
            "created_at": metadata.get("created_at"),
            "current_status": self.get_task_status(task_id),
            "status_changes": len(history),
            "artifacts_count": len(artifacts),
            "progress": progress.get("progress", 0),
            "current_stage": progress.get("stage")
        }
    
    def clear_completed_tasks(self, older_than_hours: int = 24):
        """清理已完成的任务"""
        cutoff_time = datetime.now() - datetime.timedelta(hours=older_than_hours)
        
        tasks_to_remove = []
        for task_id, metadata in self.task_metadata.items():
            if (metadata.get("created_at", datetime.now()) < cutoff_time and 
                self.get_task_status(task_id) in [TaskState.completed, TaskState.failed, TaskState.cancelled]):
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            self._remove_task_data(task_id)
    
    def _remove_task_data(self, task_id: str):
        """移除任务相关的所有数据"""
        self.task_metadata.pop(task_id, None)
        self.task_history.pop(task_id, None)
        self.task_artifacts.pop(task_id, None)
        self.task_progress.pop(task_id, None)
        
        # 也从基类的存储中移除
        if task_id in self.tasks:
            del self.tasks[task_id]