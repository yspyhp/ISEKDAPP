"""
A2A Context and EventQueue Mapping to Session and Task Management
将A2A的RequestContext和EventQueue映射到会话和任务管理
"""

import asyncio
import uuid
from typing import Any, Optional, Dict, List
from datetime import datetime
from dataclasses import dataclass

try:
    from a2a.server.agent_execution import AgentExecutor, RequestContext
    from a2a.server.events import EventQueue
    from a2a.utils import new_agent_text_message
    A2A_AVAILABLE = True
except ImportError:
    # 创建fallback类型
    class RequestContext:
        def __init__(self):
            self.message = None
            self.session_id = None
            self.task_id = None
            self.metadata = {}
    
    class EventQueue:
        async def enqueue_event(self, event):
            pass
    
    A2A_AVAILABLE = False

from isek.utils.log import log


@dataclass
class SessionContext:
    """会话上下文，从RequestContext映射而来"""
    session_id: str
    user_id: str
    created_at: datetime
    last_activity: datetime
    metadata: Dict[str, Any]
    message_history: List[Dict[str, Any]]
    
    @classmethod
    def from_request_context(cls, context: RequestContext) -> 'SessionContext':
        """从A2A RequestContext创建SessionContext"""
        session_id = getattr(context, 'session_id', None) or str(uuid.uuid4())
        user_id = getattr(context, 'user_id', None) or getattr(context, 'metadata', {}).get('user_id', 'unknown')
        metadata = getattr(context, 'metadata', {})
        
        return cls(
            session_id=session_id,
            user_id=user_id,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            metadata=metadata,
            message_history=[]
        )


@dataclass 
class TaskContext:
    """任务上下文，使用EventQueue进行状态管理"""
    task_id: str
    task_type: str
    status: str  # pending, running, completed, failed
    created_at: datetime
    updated_at: datetime
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    progress: float  # 0.0 to 1.0
    error_message: Optional[str] = None
    
    @classmethod
    def from_request_context(cls, context: RequestContext, task_type: str = "general") -> 'TaskContext':
        """从A2A RequestContext创建TaskContext"""
        task_id = getattr(context, 'task_id', None) or str(uuid.uuid4())
        message = getattr(context, 'message', None)
        metadata = getattr(context, 'metadata', {})
        
        input_data = {
            'message': str(message) if message else '',
            'metadata': metadata
        }
        
        return cls(
            task_id=task_id,
            task_type=task_type,
            status="pending",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            input_data=input_data,
            output_data={},
            progress=0.0
        )


class A2AContextMapper:
    """
    A2A上下文映射器
    将RequestContext和EventQueue映射到Session和Task管理
    """
    
    def __init__(self):
        self.sessions: Dict[str, SessionContext] = {}
        self.tasks: Dict[str, TaskContext] = {}
        self.session_tasks: Dict[str, List[str]] = {}  # session_id -> [task_ids]
    
    async def map_context_to_session_and_task(self, 
                                             context: RequestContext, 
                                             event_queue: EventQueue) -> tuple[SessionContext, TaskContext]:
        """
        将A2A的RequestContext和EventQueue映射到Session和Task
        
        Args:
            context: A2A RequestContext
            event_queue: A2A EventQueue
            
        Returns:
            tuple: (SessionContext, TaskContext)
        """
        
        # 1. 从RequestContext提取会话信息
        session_context = await self._extract_session_context(context)
        
        # 2. 从RequestContext创建任务上下文
        task_context = await self._create_task_context(context, session_context)
        
        # 3. 建立会话和任务的关联
        await self._link_session_and_task(session_context, task_context)
        
        # 4. 使用EventQueue进行状态通知
        await self._notify_context_created(event_queue, session_context, task_context)
        
        return session_context, task_context
    
    async def _extract_session_context(self, context: RequestContext) -> SessionContext:
        """从RequestContext提取会话上下文"""
        
        # 尝试从context获取session_id
        session_id = getattr(context, 'session_id', None)
        if not session_id:
            # 从metadata中获取
            metadata = getattr(context, 'metadata', {})
            session_id = metadata.get('session_id')
        
        # 如果会话已存在，更新它
        if session_id and session_id in self.sessions:
            session_context = self.sessions[session_id]
            session_context.last_activity = datetime.utcnow()
            
            # 添加新消息到历史
            message = getattr(context, 'message', None)
            if message:
                session_context.message_history.append({
                    'timestamp': datetime.utcnow().isoformat(),
                    'role': 'user',
                    'content': str(message),
                    'metadata': getattr(context, 'metadata', {})
                })
        else:
            # 创建新会话
            session_context = SessionContext.from_request_context(context)
            self.sessions[session_context.session_id] = session_context
            
            # 添加初始消息
            message = getattr(context, 'message', None)
            if message:
                session_context.message_history.append({
                    'timestamp': datetime.utcnow().isoformat(),
                    'role': 'user', 
                    'content': str(message),
                    'metadata': getattr(context, 'metadata', {})
                })
        
        return session_context
    
    async def _create_task_context(self, context: RequestContext, session_context: SessionContext) -> TaskContext:
        """创建任务上下文"""
        
        # 确定任务类型
        task_type = await self._determine_task_type(context)
        
        # 创建任务上下文
        task_context = TaskContext.from_request_context(context, task_type)
        
        # 添加会话信息到任务
        task_context.input_data['session_id'] = session_context.session_id
        task_context.input_data['user_id'] = session_context.user_id
        
        # 存储任务
        self.tasks[task_context.task_id] = task_context
        
        return task_context
    
    async def _determine_task_type(self, context: RequestContext) -> str:
        """从RequestContext确定任务类型"""
        message = getattr(context, 'message', None)
        metadata = getattr(context, 'metadata', {})
        
        # 从metadata获取任务类型
        if 'task_type' in metadata:
            return metadata['task_type']
        
        # 从消息内容推断任务类型
        if message:
            content = str(message).lower()
            if 'analyze' in content:
                return 'data_analysis'
            elif 'generate' in content and 'image' in content:
                return 'image_generation'
            elif 'task' in content and 'execute' in content:
                return 'task_execution'
            elif 'search' in content:
                return 'knowledge_search'
        
        return 'text_generation'  # 默认类型
    
    async def _link_session_and_task(self, session_context: SessionContext, task_context: TaskContext):
        """建立会话和任务的关联"""
        session_id = session_context.session_id
        task_id = task_context.task_id
        
        if session_id not in self.session_tasks:
            self.session_tasks[session_id] = []
        
        self.session_tasks[session_id].append(task_id)
    
    async def _notify_context_created(self, event_queue: EventQueue, 
                                    session_context: SessionContext, 
                                    task_context: TaskContext):
        """使用EventQueue通知上下文创建"""
        if not A2A_AVAILABLE:
            return
        
        # 发送会话信息
        session_message = f"📝 Session: {session_context.session_id[:8]}... | User: {session_context.user_id}"
        await event_queue.enqueue_event(new_agent_text_message(session_message))
        
        # 发送任务信息
        task_message = f"🎯 Task: {task_context.task_id[:8]}... | Type: {task_context.task_type} | Status: {task_context.status}"
        await event_queue.enqueue_event(new_agent_text_message(task_message))
    
    async def update_task_progress(self, task_id: str, progress: float, 
                                 status: str, event_queue: EventQueue, 
                                 output_data: Dict[str, Any] = None):
        """更新任务进度并通过EventQueue通知"""
        if task_id not in self.tasks:
            return
        
        task = self.tasks[task_id]
        task.progress = progress
        task.status = status
        task.updated_at = datetime.utcnow()
        
        if output_data:
            task.output_data.update(output_data)
        
        # 通过EventQueue发送进度更新
        if A2A_AVAILABLE:
            progress_message = f"⏳ Task {task_id[:8]}... | Progress: {progress*100:.1f}% | Status: {status}"
            await event_queue.enqueue_event(new_agent_text_message(progress_message))
    
    async def complete_task(self, task_id: str, result: Any, event_queue: EventQueue):
        """完成任务并通过EventQueue通知"""
        if task_id not in self.tasks:
            return
        
        task = self.tasks[task_id]
        task.status = "completed"
        task.progress = 1.0
        task.updated_at = datetime.utcnow()
        task.output_data['result'] = result
        
        # 更新相关会话的消息历史
        session_id = task.input_data.get('session_id')
        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
            session.message_history.append({
                'timestamp': datetime.utcnow().isoformat(),
                'role': 'assistant',
                'content': str(result),
                'metadata': {
                    'task_id': task_id,
                    'task_type': task.task_type
                }
            })
            session.last_activity = datetime.utcnow()
        
        # 通过EventQueue发送完成通知
        if A2A_AVAILABLE:
            completion_message = f"✅ Task {task_id[:8]}... completed successfully!"
            await event_queue.enqueue_event(new_agent_text_message(completion_message))
            
            # 发送实际结果
            await event_queue.enqueue_event(new_agent_text_message(str(result)))
    
    async def fail_task(self, task_id: str, error: str, event_queue: EventQueue):
        """任务失败并通过EventQueue通知"""
        if task_id not in self.tasks:
            return
        
        task = self.tasks[task_id]
        task.status = "failed"
        task.updated_at = datetime.utcnow()
        task.error_message = error
        
        # 通过EventQueue发送失败通知
        if A2A_AVAILABLE:
            error_message = f"❌ Task {task_id[:8]}... failed: {error}"
            await event_queue.enqueue_event(new_agent_text_message(error_message))
    
    def get_session_context(self, session_id: str) -> Optional[SessionContext]:
        """获取会话上下文"""
        return self.sessions.get(session_id)
    
    def get_task_context(self, task_id: str) -> Optional[TaskContext]:
        """获取任务上下文"""
        return self.tasks.get(task_id)
    
    def get_session_tasks(self, session_id: str) -> List[TaskContext]:
        """获取会话的所有任务"""
        task_ids = self.session_tasks.get(session_id, [])
        return [self.tasks[task_id] for task_id in task_ids if task_id in self.tasks]


class MappedAgentExecutor(AgentExecutor):
    """
    使用上下文映射的AgentExecutor
    AgentExecutor that uses context mapping
    """
    
    def __init__(self, adapter, context_mapper: A2AContextMapper = None):
        self.adapter = adapter
        self.context_mapper = context_mapper or A2AContextMapper()
    
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """执行请求，使用上下文映射"""
        try:
            # 映射上下文
            session_context, task_context = await self.context_mapper.map_context_to_session_and_task(
                context, event_queue
            )
            
            # 更新任务状态为运行中
            await self.context_mapper.update_task_progress(
                task_context.task_id, 0.1, "running", event_queue
            )
            
            # 执行实际任务
            message_content = task_context.input_data['message']
            
            # 添加会话上下文到prompt（如果需要）
            if len(session_context.message_history) > 1:
                # 包含之前的对话历史
                context_prompt = self._build_context_prompt(session_context, message_content)
            else:
                context_prompt = message_content
            
            # 更新进度
            await self.context_mapper.update_task_progress(
                task_context.task_id, 0.5, "processing", event_queue
            )
            
            # 调用adapter执行
            if hasattr(self.adapter, 'run'):
                result = self.adapter.run(prompt=context_prompt)
            else:
                result = "Adapter not available"
            
            # 完成任务
            await self.context_mapper.complete_task(task_context.task_id, result, event_queue)
            
        except Exception as e:
            log.error(f"Error in mapped execution: {e}")
            # 任务失败
            if 'task_context' in locals():
                await self.context_mapper.fail_task(task_context.task_id, str(e), event_queue)
            else:
                if A2A_AVAILABLE:
                    await event_queue.enqueue_event(new_agent_text_message(f"Error: {str(e)}"))
    
    def _build_context_prompt(self, session_context: SessionContext, current_message: str) -> str:
        """构建包含会话上下文的prompt"""
        context_parts = ["Previous conversation:"]
        
        # 添加最近的几条消息作为上下文
        recent_messages = session_context.message_history[-5:]  # 最近5条消息
        for msg in recent_messages[:-1]:  # 排除当前消息
            role = msg['role']
            content = msg['content']
            context_parts.append(f"{role}: {content}")
        
        context_parts.append(f"Current message: {current_message}")
        
        return "\n".join(context_parts)
    
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """取消执行"""
        if A2A_AVAILABLE:
            await event_queue.enqueue_event(new_agent_text_message("Request cancelled"))


# 使用示例
def create_mapped_a2a_application(adapter):
    """创建使用上下文映射的A2A应用"""
    if not A2A_AVAILABLE:
        raise RuntimeError("A2A SDK not available")
    
    from a2a.server.apps import A2AStarletteApplication
    from a2a.server.request_handlers import DefaultRequestHandler
    from a2a.server.tasks import InMemoryTaskStore
    from a2a.types import AgentCard, AgentCapabilities
    
    # 创建映射的executor
    context_mapper = A2AContextMapper()
    executor = MappedAgentExecutor(adapter, context_mapper)
    
    # 创建agent card
    agent_card = AgentCard(
        name="Mapped ISEK Agent",
        description="ISEK Agent with A2A context mapping",
        url="http://localhost:8888",
        version="1.0.0",
        defaultInputModes=["text"],
        defaultOutputModes=["text", "streaming"],
        capabilities=AgentCapabilities(
            streaming=True,
            tasks=True,
            sessions=True
        ),
        skills=[]
    )
    
    # 创建request handler
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore()
    )
    
    # 创建应用
    return A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler
    )