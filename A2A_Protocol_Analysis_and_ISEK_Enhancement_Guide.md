# A2A协议深度分析与ISEK增强指南

## 概述

本文档深入分析了Google A2A (Agent-to-Agent) 协议的核心功能，并提供了ISEK系统中A2A协议类的具体改进建议，重点关注任务管理、会话管理和上下文管理三个核心领域。

## 目录

1. [A2A协议核心架构](#1-a2a协议核心架构)
2. [任务管理机制](#2-任务管理机制)
3. [会话与上下文管理](#3-会话与上下文管理)
4. [EventQueue详细用法](#4-eventqueue详细用法)
5. [RequestContext详细用法](#5-requestcontext详细用法)
6. [ISEK当前实现分析](#6-isek当前实现分析)
7. [具体改进建议](#7-具体改进建议)
8. [实施方案](#8-实施方案)

---

## 1. A2A协议核心架构

### 1.1 核心组件

```python
# A2A协议的核心组件架构
class AgentExecutor:
    """代理执行器接口"""
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """执行任务的主要方法"""
        pass
    
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """取消正在执行的任务"""
        pass

class RequestContext:
    """请求上下文，包含任务和会话信息"""
    def get_task_id(self) -> str: pass
    def get_context_id(self) -> str: pass
    def get_user_input(self) -> str: pass

class EventQueue:
    """事件队列，用于发送响应和状态更新"""
    async def enqueue_event(self, event) -> None: pass

class TaskStore:
    """任务存储，负责任务状态持久化"""
    pass
```

### 1.2 通信流程

1. **客户端** → 发送消息到A2A服务器
2. **RequestHandler** → 解析请求，创建RequestContext
3. **AgentExecutor** → 使用context执行任务，通过event_queue发送响应
4. **EventQueue** → 将事件转换为A2A协议响应
5. **客户端** → 接收响应和状态更新

---

## 2. 任务管理机制

### 2.1 任务生命周期

A2A协议定义了完整的任务状态管理：

```
submitted → working → input-required/completed/failed/cancelled
```

**状态说明:**
- `submitted`: 任务已提交，等待处理
- `working`: 任务正在执行中
- `input-required`: 任务需要额外输入或用户确认
- `completed`: 任务成功完成
- `failed`: 任务执行失败
- `cancelled`: 任务被取消

### 2.2 任务管理实现

```python
class EnhancedTaskStore(InMemoryTaskStore):
    """增强的任务存储，支持完整生命周期管理"""
    
    def __init__(self):
        super().__init__()
        self.task_states = {}
        self.task_history = {}
        self.task_artifacts = {}
        
    async def create_task(self, task_id: str, context_id: str, metadata: dict = None):
        """创建新任务"""
        self.task_states[task_id] = {
            "status": "submitted",
            "context_id": context_id,
            "created_at": datetime.now(),
            "metadata": metadata or {}
        }
        
    async def update_task_status(self, task_id: str, status: str, metadata: dict = None):
        """更新任务状态"""
        if task_id in self.task_states:
            self.task_states[task_id]["status"] = status
            self.task_states[task_id]["updated_at"] = datetime.now()
            if metadata:
                self.task_states[task_id]["metadata"].update(metadata)
                
    async def add_task_artifact(self, task_id: str, artifact: Any):
        """添加任务产物"""
        if task_id not in self.task_artifacts:
            self.task_artifacts[task_id] = []
        self.task_artifacts[task_id].append(artifact)
        
    def get_task_status(self, task_id: str) -> Optional[str]:
        """获取任务状态"""
        return self.task_states.get(task_id, {}).get("status")
```

### 2.3 长时间运行任务支持

```python
class LongRunningTaskExecutor(AgentExecutor):
    """支持长时间运行任务的执行器"""
    
    def __init__(self, url: str, adapter: Adapter, task_store: EnhancedTaskStore):
        self.url = url
        self.adapter = adapter
        self.task_store = task_store
        self.running_tasks = {}
        
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        task_id = context.get_task_id()
        
        # 创建任务记录
        await self.task_store.create_task(task_id, context.get_context_id())
        self.running_tasks[task_id] = {
            "context": context,
            "cancelled": False,
            "start_time": datetime.now()
        }
        
        try:
            # 发送任务开始状态
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="working"
            ))
            
            # 执行任务，支持取消检查
            result = await self._execute_with_cancellation_check(
                task_id, context, event_queue
            )
            
            # 任务完成
            await self.task_store.update_task_status(task_id, "completed")
            await event_queue.enqueue_event(new_agent_text_message(result))
            
        except TaskCancelledException:
            await self.task_store.update_task_status(task_id, "cancelled")
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="cancelled"
            ))
        except Exception as e:
            await self.task_store.update_task_status(task_id, "failed")
            await event_queue.enqueue_event(A2AError(
                code=-32603,
                message=f"Task execution failed: {str(e)}"
            ))
        finally:
            # 清理任务记录
            self.running_tasks.pop(task_id, None)
            
    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        task_id = context.get_task_id()
        
        if task_id in self.running_tasks:
            # 标记任务为取消状态
            self.running_tasks[task_id]["cancelled"] = True
            
            # 更新任务状态
            await self.task_store.update_task_status(task_id, "cancelled")
            
            # 发送取消确认
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="cancelled"
            ))
            
    async def _execute_with_cancellation_check(self, task_id: str, context: RequestContext, event_queue: EventQueue):
        """执行任务，支持取消检查"""
        user_input = context.get_user_input()
        
        # 模拟长时间运行的任务
        for i in range(10):  # 假设分10个步骤
            # 检查是否被取消
            if self.running_tasks.get(task_id, {}).get("cancelled", False):
                raise TaskCancelledException(f"Task {task_id} was cancelled")
                
            # 执行部分工作
            partial_result = self.adapter.run_partial(prompt=user_input, step=i)
            
            # 发送进度更新
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="working",
                metadata={"progress": f"{i+1}/10", "partial_result": partial_result}
            ))
            
            # 模拟工作延迟
            await asyncio.sleep(1)
            
        return self.adapter.run(prompt=user_input)
```

---

## 3. 会话与上下文管理

### 3.1 多层次上下文架构

A2A协议支持多层次的上下文管理：

1. **Request Context**: 单次请求的上下文信息
2. **Session Context**: 会话级别的持久化上下文
3. **User Context**: 用户级别的长期记忆

### 3.2 会话持久化机制

```python
class SessionManager:
    """会话管理器，整合A2A上下文与ISEK Memory系统"""
    
    def __init__(self, memory_manager: Memory):
        self.memory_manager = memory_manager
        self.active_sessions = {}
        
    def create_session_context(self, context_id: str, user_id: str = "default"):
        """创建会话上下文"""
        session_context = {
            "context_id": context_id,
            "user_id": user_id,
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "message_count": 0
        }
        self.active_sessions[context_id] = session_context
        return session_context
        
    def get_session_context(self, context_id: str):
        """获取会话上下文"""
        return self.active_sessions.get(context_id)
        
    def update_session_activity(self, context_id: str):
        """更新会话活动时间"""
        if context_id in self.active_sessions:
            self.active_sessions[context_id]["last_activity"] = datetime.now()
            self.active_sessions[context_id]["message_count"] += 1
            
    def get_conversation_history(self, context_id: str, limit: int = 10):
        """获取对话历史"""
        session_summary = self.memory_manager.get_session_summary(context_id)
        user_memories = self.memory_manager.get_user_memories()
        
        # 合并会话摘要和用户记忆
        history = []
        if session_summary:
            history.append(session_summary.summary)
            
        # 添加相关的用户记忆
        recent_memories = user_memories[-limit:] if user_memories else []
        for memory in recent_memories:
            history.append(memory.memory)
            
        return history
        
    def save_conversation_turn(self, context_id: str, user_input: str, agent_response: str):
        """保存对话轮次"""
        # 更新会话摘要
        conversation_turn = f"User: {user_input}\nAgent: {agent_response}"
        
        existing_summary = self.memory_manager.get_session_summary(context_id)
        if existing_summary:
            # 更新现有摘要
            new_summary_text = f"{existing_summary.summary}\n{conversation_turn}"
        else:
            # 创建新摘要
            new_summary_text = conversation_turn
            
        new_summary = SessionSummary(
            summary=new_summary_text,
            topics=self._extract_topics(user_input, agent_response),
            last_updated=datetime.now()
        )
        
        self.memory_manager.add_session_summary(context_id, new_summary)
        
    def _extract_topics(self, user_input: str, agent_response: str) -> List[str]:
        """提取对话主题（简化实现）"""
        # 这里可以使用更复杂的NLP技术
        text = f"{user_input} {agent_response}".lower()
        keywords = ["task", "question", "help", "information", "analysis"]
        return [keyword for keyword in keywords if keyword in text]
```

### 3.3 上下文感知的执行器

```python
class ContextAwareAgentExecutor(AgentExecutor):
    """上下文感知的代理执行器"""
    
    def __init__(self, url: str, adapter: Adapter, session_manager: SessionManager):
        self.url = url
        self.adapter = adapter
        self.session_manager = session_manager
        
    def get_a2a_agent_card(self) -> AgentCard:
        """获取代理卡片信息"""
        adapter_card = self.adapter.get_adapter_card()
        return AgentCard(
            name=adapter_card.name,
            description=f"Context-aware agent: {adapter_card.bio}",
            url=self.url,
            version="2.0.0",
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            capabilities=AgentCapabilities(
                streaming=True,
                multiturn=True,
                context_management=True
            ),
            skills=adapter_card.skills if hasattr(adapter_card, 'skills') else [],
        )
        
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        """执行任务，集成上下文管理"""
        # 1. 获取基本信息
        context_id = context.get_context_id()
        user_input = context.get_user_input()
        task_id = context.get_task_id()
        
        # 2. 管理会话上下文
        session_context = self.session_manager.get_session_context(context_id)
        if not session_context:
            session_context = self.session_manager.create_session_context(context_id)
            
        self.session_manager.update_session_activity(context_id)
        
        # 3. 获取对话历史
        conversation_history = self.session_manager.get_conversation_history(context_id)
        
        # 4. 构建上下文感知的提示词
        enhanced_prompt = self._build_context_prompt(user_input, conversation_history)
        
        # 5. 执行任务
        try:
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="working"
            ))
            
            result = self.adapter.run(prompt=enhanced_prompt)
            
            # 6. 保存对话记录
            self.session_manager.save_conversation_turn(context_id, user_input, result)
            
            # 7. 发送响应
            await event_queue.enqueue_event(new_agent_text_message(result))
            
        except Exception as e:
            await event_queue.enqueue_event(A2AError(
                code=-32603,
                message=f"Context-aware execution failed: {str(e)}"
            ))
            
    def _build_context_prompt(self, user_input: str, history: List[str]) -> str:
        """构建包含上下文的提示词"""
        if not history:
            return user_input
            
        context_part = "\n".join(history[-3:])  # 最近3条历史
        return f"""Previous conversation context:
{context_part}

Current user input: {user_input}

Please respond considering the conversation history."""

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        """取消任务执行"""
        task_id = context.get_task_id()
        await event_queue.enqueue_event(TaskStatusUpdateEvent(
            task_id=task_id,
            status="cancelled"
        ))
```

---

## 4. EventQueue详细用法

### 4.1 基本事件类型

```python
# 1. 文本消息响应
from a2a.utils import new_agent_text_message
await event_queue.enqueue_event(new_agent_text_message("Hello, World!"))

# 2. 任务状态更新
from a2a.types.events import TaskStatusUpdateEvent
await event_queue.enqueue_event(TaskStatusUpdateEvent(
    task_id=task_id,
    status="working",
    metadata={"progress": "50%"}
))

# 3. 错误事件
from a2a.types.errors import A2AError
await event_queue.enqueue_event(A2AError(
    code=-32603,
    message="Internal error occurred",
    data={"task_id": task_id}
))

# 4. 任务创建
from a2a.utils import new_task
task = new_task(context.message)
await event_queue.enqueue_event(task)
```

### 4.2 流式响应实现

```python
async def execute_streaming(self, context: RequestContext, event_queue: EventQueue):
    """流式响应实现"""
    user_input = context.get_user_input()
    task_id = context.get_task_id()
    
    # 开始流式处理
    await event_queue.enqueue_event(TaskStatusUpdateEvent(
        task_id=task_id,
        status="working"
    ))
    
    # 模拟流式输出
    response_chunks = self.adapter.stream(prompt=user_input)
    
    accumulated_response = ""
    async for chunk in response_chunks:
        accumulated_response += chunk
        
        # 发送部分响应
        await event_queue.enqueue_event(new_agent_text_message(chunk))
        
        # 可选：发送进度更新
        progress = len(accumulated_response) / 1000  # 假设目标长度1000字符
        await event_queue.enqueue_event(TaskStatusUpdateEvent(
            task_id=task_id,
            status="working",
            metadata={"streaming_progress": min(progress, 1.0)}
        ))
    
    # 流式处理完成
    await event_queue.enqueue_event(TaskStatusUpdateEvent(
        task_id=task_id,
        status="completed"
    ))
```

### 4.3 多模态响应

```python
async def execute_multimodal(self, context: RequestContext, event_queue: EventQueue):
    """多模态响应示例"""
    user_input = context.get_user_input()
    
    # 文本响应
    text_result = self.adapter.generate_text(user_input)
    await event_queue.enqueue_event(new_agent_text_message(text_result))
    
    # 图像响应
    if self.adapter.supports_image_generation():
        image_data = self.adapter.generate_image(user_input)
        image_artifact = {
            "type": "image",
            "data": image_data,
            "metadata": {"format": "png", "description": "Generated image"}
        }
        await event_queue.enqueue_event(TaskArtifactUpdateEvent(
            task_id=context.get_task_id(),
            artifact=image_artifact
        ))
    
    # 结构化数据响应
    structured_data = {
        "analysis_result": {"score": 0.95, "confidence": "high"},
        "recommendations": ["Action 1", "Action 2"]
    }
    await event_queue.enqueue_event(TaskArtifactUpdateEvent(
        task_id=context.get_task_id(),
        artifact=structured_data
    ))
```

---

## 5. RequestContext详细用法

### 5.1 基本信息获取

```python
async def execute(self, context: RequestContext, event_queue: EventQueue):
    # 基本信息
    task_id = context.get_task_id()           # 任务唯一标识
    context_id = context.get_context_id()     # 会话上下文ID
    user_input = context.get_user_input()     # 用户输入文本
    
    # 原始消息对象
    message = context.message
    message_id = message.messageId if hasattr(message, 'messageId') else None
    
    # 当前任务对象
    current_task = context.current_task
    if current_task:
        task_status = current_task.status
        task_artifacts = current_task.artifacts
```

### 5.2 元数据处理

```python
def extract_metadata(self, context: RequestContext) -> dict:
    """提取请求元数据"""
    metadata = {}
    
    # 消息级元数据
    if hasattr(context.message, 'metadata'):
        msg_metadata = context.message.metadata
        metadata.update({
            'sender_node_id': msg_metadata.get('sender_node_id'),
            'priority': msg_metadata.get('priority', 'normal'),
            'timeout': msg_metadata.get('timeout', 30)
        })
    
    # 任务级元数据
    if context.current_task and hasattr(context.current_task, 'metadata'):
        task_metadata = context.current_task.metadata
        metadata.update({
            'task_type': task_metadata.get('type'),
            'expected_duration': task_metadata.get('expected_duration'),
            'dependencies': task_metadata.get('dependencies', [])
        })
    
    return metadata
```

### 5.3 多轮对话支持

```python
def handle_multiturn_context(self, context: RequestContext) -> str:
    """处理多轮对话上下文"""
    # 检查是否是多轮对话的后续消息
    current_task = context.current_task
    
    if current_task and current_task.status in ["working", "input-required"]:
        # 这是现有任务的续集
        previous_context = current_task.metadata.get('conversation_context', '')
        current_input = context.get_user_input()
        
        # 构建累积的对话上下文
        accumulated_context = f"{previous_context}\nUser: {current_input}"
        return accumulated_context
    else:
        # 新的对话开始
        return context.get_user_input()
```

### 5.4 条件执行逻辑

```python
async def execute_with_context_analysis(self, context: RequestContext, event_queue: EventQueue):
    """基于上下文分析的条件执行"""
    user_input = context.get_user_input()
    metadata = self.extract_metadata(context)
    
    # 根据发送者类型调整处理策略
    sender_node_id = metadata.get('sender_node_id')
    if sender_node_id:
        # P2P消息，可能需要特殊处理
        await self._handle_p2p_message(context, event_queue, sender_node_id)
    else:
        # 直接客户端消息
        await self._handle_direct_message(context, event_queue)
    
    # 根据任务优先级调整响应速度
    priority = metadata.get('priority', 'normal')
    if priority == 'urgent':
        # 紧急任务，使用快速模式
        result = self.adapter.run_fast(prompt=user_input)
    else:
        # 普通任务，使用标准模式
        result = self.adapter.run(prompt=user_input)
    
    await event_queue.enqueue_event(new_agent_text_message(result))

async def _handle_p2p_message(self, context: RequestContext, event_queue: EventQueue, sender_id: str):
    """处理P2P消息的特殊逻辑"""
    # 可以添加发送者验证、权限检查等
    await event_queue.enqueue_event(TaskStatusUpdateEvent(
        task_id=context.get_task_id(),
        status="working",
        metadata={"processing_mode": "p2p", "sender": sender_id}
    ))

async def _handle_direct_message(self, context: RequestContext, event_queue: EventQueue):
    """处理直接消息的逻辑"""
    await event_queue.enqueue_event(TaskStatusUpdateEvent(
        task_id=context.get_task_id(),
        status="working",
        metadata={"processing_mode": "direct"}
    ))
```

---

## 6. ISEK当前实现分析

### 6.1 现有架构优势

ISEK在`/Users/sparkss/ISEKOS/isek/protocol/a2a_protocol.py`中已经实现了A2A协议的基础架构：

**优势：**
1. ✅ 正确使用了A2A SDK的核心组件
2. ✅ 实现了基本的AgentExecutor
3. ✅ 集成了P2P通信能力
4. ✅ 有独立的Memory系统支持
5. ✅ 支持多种Adapter架构

### 6.2 当前实现的局限性

**任务管理方面：**
- ❌ 只使用简单的`InMemoryTaskStore`
- ❌ 缺少任务状态跟踪机制
- ❌ `cancel`方法只抛出异常，没有实际取消逻辑
- ❌ 不支持长时间运行任务

**上下文管理方面：**
- ❌ Memory系统与A2A RequestContext未集成
- ❌ 会话持久化依赖独立系统，未使用A2A标准机制
- ❌ 缺少多轮对话的上下文传递

**错误处理方面：**
- ❌ 缺少完整的错误处理和重试机制
- ❌ 没有实现流式响应
- ❌ 状态更新机制不完整

### 6.3 当前实现代码分析

```python
# ISEK当前的简单实现 (a2a_protocol.py:35-65)
class DefaultAgentExecutor(AgentExecutor):
    def __init__(self, url: str, adapter: Adapter):
        self.url = url
        self.adapter = adapter

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        prompt = context.get_user_input()
        result = self.adapter.run(prompt=prompt)
        await event_queue.enqueue_event(new_agent_text_message(result))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception("cancel not supported")  # ❌ 需要改进
```

---

## 7. 具体改进建议

### 7.1 任务管理增强

```python
# 替换当前的DefaultAgentExecutor
class EnhancedDefaultAgentExecutor(AgentExecutor):
    def __init__(self, url: str, adapter: Adapter, memory_manager: Memory = None):
        self.url = url
        self.adapter = adapter
        self.memory_manager = memory_manager or Memory()
        self.running_tasks = {}
        self.task_store = EnhancedTaskStore()
        
    def get_a2a_agent_card(self) -> AgentCard:
        adapter_card = self.adapter.get_adapter_card()
        return AgentCard(
            name=adapter_card.name,
            description=f"Enhanced A2A Agent: {adapter_card.bio}",
            url=self.url,
            version="2.0.0",  # 升级版本号
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            capabilities=AgentCapabilities(
                streaming=True,
                multiturn=True,
                long_running_tasks=True
            ),
            skills=getattr(adapter_card, 'skills', []),
        )

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id = context.get_task_id()
        context_id = context.get_context_id()
        user_input = context.get_user_input()
        
        # 1. 初始化任务
        await self.task_store.create_task(task_id, context_id)
        self.running_tasks[task_id] = {
            "context": context,
            "cancelled": False,
            "start_time": datetime.now()
        }
        
        try:
            # 2. 发送工作状态
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="working"
            ))
            
            # 3. 获取历史上下文
            session_context = self._get_session_context(context_id)
            enhanced_prompt = self._build_enhanced_prompt(user_input, session_context)
            
            # 4. 执行任务（支持取消检查）
            result = await self._execute_with_cancellation(task_id, enhanced_prompt)
            
            # 5. 保存会话记录
            self._save_session_context(context_id, user_input, result)
            
            # 6. 发送结果
            await event_queue.enqueue_event(new_agent_text_message(result))
            await self.task_store.update_task_status(task_id, "completed")
            
        except TaskCancelledException:
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="cancelled"
            ))
        except Exception as e:
            await event_queue.enqueue_event(A2AError(
                code=-32603,
                message=f"Task execution failed: {str(e)}",
                data={"task_id": task_id}
            ))
            await self.task_store.update_task_status(task_id, "failed")
        finally:
            # 7. 清理任务记录
            self.running_tasks.pop(task_id, None)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id = context.get_task_id()
        
        if task_id in self.running_tasks:
            # 标记为取消状态
            self.running_tasks[task_id]["cancelled"] = True
            
            # 更新任务状态
            await self.task_store.update_task_status(task_id, "cancelled")
            
            # 发送取消确认
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="cancelled",
                metadata={"cancelled_at": datetime.now().isoformat()}
            ))
        else:
            # 任务不存在或已完成
            await event_queue.enqueue_event(A2AError(
                code=-32602,
                message=f"Task {task_id} not found or already completed"
            ))

    def _get_session_context(self, context_id: str) -> Optional[SessionSummary]:
        """获取会话上下文"""
        return self.memory_manager.get_session_summary(context_id)
    
    def _build_enhanced_prompt(self, user_input: str, session_context: Optional[SessionSummary]) -> str:
        """构建增强的提示词"""
        if not session_context:
            return user_input
            
        return f"""Previous conversation:
{session_context.summary}

Current user input: {user_input}

Please respond considering the conversation history."""

    def _save_session_context(self, context_id: str, user_input: str, result: str):
        """保存会话上下文"""
        conversation_turn = f"User: {user_input}\nAgent: {result}"
        
        existing_summary = self.memory_manager.get_session_summary(context_id)
        if existing_summary:
            new_summary_text = f"{existing_summary.summary}\n{conversation_turn}"
        else:
            new_summary_text = conversation_turn
            
        new_summary = SessionSummary(
            summary=new_summary_text,
            topics=self._extract_topics(user_input, result),
            last_updated=datetime.now()
        )
        
        self.memory_manager.add_session_summary(context_id, new_summary)

    async def _execute_with_cancellation(self, task_id: str, prompt: str) -> str:
        """支持取消的任务执行"""
        # 检查取消状态
        if self.running_tasks.get(task_id, {}).get("cancelled", False):
            raise TaskCancelledException(f"Task {task_id} was cancelled")
            
        # 执行实际任务
        return self.adapter.run(prompt=prompt)
    
    def _extract_topics(self, user_input: str, result: str) -> List[str]:
        """提取对话主题"""
        # 简化的主题提取逻辑
        text = f"{user_input} {result}".lower()
        keywords = ["question", "task", "help", "analysis", "information"]
        return [kw for kw in keywords if kw in text]
```

### 7.2 A2A应用构建增强

```python
# 增强build_a2a_application方法
def build_a2a_application(self) -> JSONRPCApplication:
    if not self.adapter or not isinstance(self.adapter, Adapter):
        raise ValueError("A Adapter must be provided to the A2AProtocol.")
    
    # 使用增强的执行器
    agent_executor = EnhancedDefaultAgentExecutor(
        self.url, 
        self.adapter,
        Memory()  # 集成Memory系统
    )
    
    # 使用增强的任务存储
    enhanced_task_store = EnhancedTaskStore()
    
    # 使用增强的请求处理器
    request_handler = EnhancedRequestHandler(
        agent_executor=agent_executor,
        task_store=enhanced_task_store,
    )

    return A2AStarletteApplication(
        agent_card=agent_executor.get_a2a_agent_card(),
        http_handler=request_handler,
    )
```

### 7.3 P2P通信增强

```python
# 增强P2P消息发送，添加错误处理和重试
def send_p2p_message(self, sender_node_id, p2p_address, message, retry_count=3):
    for attempt in range(retry_count):
        try:
            request = build_send_message_request(sender_node_id, message)
            request_body = request.model_dump(mode="json", exclude_none=True)
            
            response = httpx.post(
                url=f"http://localhost:{self.p2p_server_port}/call_peer?p2p_address={urllib.parse.quote(p2p_address)}",
                json=request_body,
                headers={"Content-Type": "application/json"},
                timeout=60,
            )
            
            if response.status_code == 200:
                response_body = json.loads(response.content)
                return response_body["result"]["parts"][0]["text"]
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            if attempt == retry_count - 1:
                raise Exception(f"P2P message failed after {retry_count} attempts: {str(e)}")
            else:
                log.warning(f"P2P attempt {attempt + 1} failed: {str(e)}, retrying...")
                time.sleep(2 ** attempt)  # 指数退避

def send_message(self, sender_node_id, target_address, message, retry_count=3):
    for attempt in range(retry_count):
        try:
            httpx_client = httpx.AsyncClient(timeout=60)
            client = A2AClient(httpx_client=httpx_client, url=target_address)
            request = build_send_message_request(sender_node_id, message)
            response = asyncio.run(client.send_message(request))
            return response.model_dump(mode="json", exclude_none=True)["result"]["parts"][0]["text"]
            
        except Exception as e:
            if attempt == retry_count - 1:
                raise Exception(f"A2A message failed after {retry_count} attempts: {str(e)}")
            else:
                log.warning(f"A2A attempt {attempt + 1} failed: {str(e)}, retrying...")
                await asyncio.sleep(2 ** attempt)
```

---

## 8. 实施方案

### 8.1 阶段一：核心增强 (Week 1-2)

1. **替换DefaultAgentExecutor**
   - 实现EnhancedDefaultAgentExecutor
   - 添加任务状态跟踪
   - 实现cancel方法

2. **集成Memory系统**
   - 将现有Memory类与RequestContext集成
   - 实现会话上下文传递
   - 添加对话历史构建

3. **增强错误处理**
   - 添加完整的异常处理
   - 实现重试机制
   - 改进日志记录

### 8.2 阶段二：高级功能 (Week 3-4)

1. **长时间任务支持**
   - 实现任务取消机制
   - 添加进度报告
   - 支持任务暂停/恢复

2. **流式响应**
   - 实现流式输出
   - 添加实时进度更新
   - 支持多模态响应

3. **性能优化**
   - 优化内存使用
   - 改进P2P通信性能
   - 添加连接池管理

### 8.3 阶段三：企业级功能 (Week 5-6)

1. **安全增强**
   - 添加输入验证
   - 实现访问控制
   - 增强审计日志

2. **可观测性**
   - 添加指标收集
   - 实现健康检查
   - 集成监控系统

3. **测试和文档**
   - 编写单元测试
   - 集成测试
   - API文档更新

### 8.4 迁移策略

```python
# 渐进式迁移示例
class A2AProtocol(Protocol):
    def __init__(self, enhanced_mode: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.enhanced_mode = enhanced_mode
        # ... 现有初始化代码
    
    def build_a2a_application(self) -> JSONRPCApplication:
        if self.enhanced_mode:
            # 使用增强版本
            return self._build_enhanced_a2a_application()
        else:
            # 使用现有版本（向后兼容）
            return self._build_legacy_a2a_application()
    
    def _build_enhanced_a2a_application(self) -> JSONRPCApplication:
        # 新的增强实现
        agent_executor = EnhancedDefaultAgentExecutor(
            self.url, self.adapter, Memory()
        )
        # ... 其他增强功能
    
    def _build_legacy_a2a_application(self) -> JSONRPCApplication:
        # 现有的实现保持不变
        agent_executor = DefaultAgentExecutor(self.url, self.adapter)
        # ... 现有代码
```

### 8.5 配置管理

```python
# 配置文件示例 (config/a2a_config.yaml)
a2a:
  enhanced_mode: true
  task_management:
    enable_cancellation: true
    max_task_duration: 3600  # 1小时
    progress_reporting: true
  context_management:
    session_timeout: 1800    # 30分钟
    max_history_length: 100
    memory_persistence: true
  error_handling:
    max_retries: 3
    retry_backoff: exponential
  performance:
    connection_pool_size: 10
    request_timeout: 60
```

---

## 9. 总结

通过本文档的分析和建议，ISEK可以在保持现有架构优势的基础上，全面升级A2A协议支持，实现：

1. **完整的任务生命周期管理** - 从submitted到completed/failed/cancelled的全流程跟踪
2. **智能的上下文管理** - 集成Memory系统，支持多轮对话和长期记忆
3. **强大的事件处理** - 通过EventQueue实现实时状态更新和流式响应
4. **可靠的错误处理** - 完整的异常处理、重试机制和优雅降级
5. **企业级可扩展性** - 支持长时间任务、P2P通信优化和性能监控

这些改进将使ISEK成为一个功能完整、性能卓越的A2A协议实现，完全符合Google A2A标准，同时保持与现有系统的兼容性。

---

## 附录

### A. 相关文件路径
- A2A协议实现: `/Users/sparkss/ISEKOS/isek/protocol/a2a_protocol.py`
- Memory系统: `/Users/sparkss/ISEKOS/isek/memory/memory.py`
- 节点实现: `/Users/sparkss/ISEKOS/isek/node/node_v2.py`

### B. 参考资源
- [A2A Python SDK](https://github.com/a2aproject/a2a-python)
- [A2A Samples](https://github.com/a2aproject/a2a-samples)
- [A2A Protocol Specification](https://github.com/a2aproject/A2A)

### C. 依赖包
```python
# requirements.txt 新增依赖
a2a-sdk>=1.0.0
httpx>=0.24.0
uvicorn>=0.22.0
pydantic>=2.0.0
```