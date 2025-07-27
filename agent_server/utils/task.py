"""
Task Management Utilities
任务管理工具类 - 基于a2a native的增强任务存储
"""

from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import Task, TaskState, TaskStatus


class TaskCancelledException(Exception):
    """任务取消异常"""
    pass


class EnhancedTaskStore(InMemoryTaskStore):
    """增强的任务存储 - 继承a2a native，添加ISEK特有功能"""
    
    def __init__(self):
        super().__init__()
        # 仅保留ISEK特有的扩展数据
        self.task_metadata = {}  # ISEK任务元数据
        self.task_progress = {}  # 任务进度信息
    
    async def create_task(self, task_id: str, context_id: str, metadata: dict = None):
        """创建新任务 - 使用a2a native + ISEK扩展"""
        # 存储ISEK特有的元数据
        self.task_metadata[task_id] = {
            "context_id": context_id,
            "created_at": datetime.now(),
            "metadata": metadata or {}
        }
        
        # 使用父类的任务创建逻辑
        task = Task(id=task_id, contextId=context_id, status=TaskStatus(state=TaskState.submitted))
        await self.save(task)
        
    async def update_task_status(self, task_id: str, status: TaskState, metadata: dict = None):
        """更新任务状态 - 简化版，利用a2a native功能"""
        # 获取或创建任务
        existing_task = await self.get(task_id)
        context_id = self.task_metadata.get(task_id, {}).get("context_id", "unknown")
        
        if existing_task:
            # 更新现有任务状态
            existing_task.status = TaskStatus(state=status)
            await self.save(existing_task)
        else:
            # 创建新任务（如果不存在）
            new_task = Task(id=task_id, contextId=context_id, status=TaskStatus(state=status))
            await self.save(new_task)
        
        # 更新ISEK元数据
        if metadata and task_id in self.task_metadata:
            self.task_metadata[task_id]["metadata"].update(metadata)
            self.task_metadata[task_id]["last_updated"] = datetime.now()
    
    def update_task_progress(self, task_id: str, progress: float, stage: str = None):
        """更新任务进度 - ISEK特有功能"""
        if task_id not in self.task_progress:
            self.task_progress[task_id] = {}
        self.task_progress[task_id].update({
            "progress": progress,
            "stage": stage,
            "updated_at": datetime.now()
        })
        
    async def get_task_status(self, task_id: str) -> Optional[TaskState]:
        """获取任务状态 - 使用a2a native方法"""
        task = await self.get(task_id)
        return task.status.state if task and task.status else None
    
    def get_task_progress(self, task_id: str) -> dict:
        """获取任务进度信息"""
        metadata = self.task_metadata.get(task_id, {})
        progress = self.task_progress.get(task_id, {})
        
        return {
            "task_id": task_id,
            "context_id": metadata.get("context_id"),
            "created_at": metadata.get("created_at"),
            "metadata": metadata.get("metadata", {}),
            "progress": progress.get("progress", 0),
            "stage": progress.get("stage"),
            "last_updated": progress.get("updated_at")
        }
    
    def get_tasks_by_context(self, context_id: str) -> List[str]:
        """根据上下文ID获取任务列表"""
        return [
            task_id for task_id, metadata in self.task_metadata.items()
            if metadata.get("context_id") == context_id
        ]
    
    def clear_completed_tasks(self, older_than_hours: int = 24):
        """清理已完成的任务"""
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
        
        tasks_to_remove = []
        for task_id, metadata in self.task_metadata.items():
            if metadata.get("created_at", datetime.now()) < cutoff_time:
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            # 清理ISEK扩展数据
            self.task_metadata.pop(task_id, None)
            self.task_progress.pop(task_id, None)
            # a2a native会处理核心任务数据的清理