# A2A EventQueue和任务管理机制详解

## 概述

本文档详细解释了Google A2A协议中EventQueue的工作机制、任务处理流程，以及如何实现多轮对话和长任务处理。重点分析了EventQueue如何作为AgentExecutor与A2A协议层之间的桥梁，实现异步通信和状态管理。

## 目录

1. [EventQueue工作机制](#1-eventqueue工作机制)
2. [任务处理架构](#2-任务处理架构)
3. [事件类型和用法](#3-事件类型和用法)
4. [多轮对话实现](#4-多轮对话实现)
5. [长任务处理](#5-长任务处理)
6. [流式响应](#6-流式响应)
7. [ISEK集成方案](#7-isek集成方案)
8. [最佳实践](#8-最佳实践)

---

## 1. EventQueue工作机制

### 1.1 EventQueue的核心作用

EventQueue是A2A协议中连接AgentExecutor和协议层的关键组件：

```python
# EventQueue的基本工作流程
async def execute(self, context: RequestContext, event_queue: EventQueue):
    # 1. 获取任务信息
    task_id = context.get_task_id()
    user_input = context.get_user_input()
    
    # 2. 通过EventQueue发送事件
    await event_queue.enqueue_event(TaskStatusUpdateEvent(
        task_id=task_id,
        status="working"
    ))
    
    # 3. 执行业务逻辑
    result = self.adapter.run(prompt=user_input)
    
    # 4. 发送结果事件
    await event_queue.enqueue_event(new_agent_text_message(result))
```

### 1.2 EventQueue处理流程

```
AgentExecutor.execute()
    ↓
await event_queue.enqueue_event(event)
    ↓
EventQueue内部处理 (A2A框架负责)
    ↓
转换为A2A协议响应格式
    ↓
通过HTTP/WebSocket发送给客户端
    ↓
客户端接收响应和状态更新
```

### 1.3 EventQueue的特性

- **异步通信**: 支持非阻塞的事件发送
- **实时更新**: 客户端可以实时接收状态变更
- **多事件类型**: 支持文本、状态、错误等多种事件
- **自动序列化**: A2A框架自动处理事件格式转换

---

## 2. 任务处理架构

### 2.1 A2A任务处理的完整架构

```python
# A2A任务处理的核心组件关系
class A2ATaskProcessingArchitecture:
    """
    客户端请求 
        ↓
    A2AStarletteApplication (HTTP服务器)
        ↓  
    DefaultRequestHandler (A2A协议处理)
        ↓
    1. 从TaskStore获取或创建Task对象
    2. 创建RequestContext
    3. 调用 AgentExecutor.execute(context, event_queue)
        ↓
    DefaultAgentExecutor.execute() (业务逻辑)
        ↓
    通过event_queue发送事件
        ↓
    DefaultRequestHandler处理事件并更新TaskStore
        ↓
    返回给客户端
    """
    pass
```

### 2.2 组件职责分工

| 组件 | 职责 | 生命周期 |
|------|------|----------|
| **AgentExecutor** | 业务逻辑执行 | 应用启动时创建一次，处理所有请求 |
| **TaskStore** | 任务状态持久化 | 应用级别单例，存储所有任务状态 |
| **DefaultRequestHandler** | A2A协议处理 | 应用启动时创建，协调各组件 |
| **EventQueue** | 事件通信桥梁 | 每个请求创建，用于该请求的事件发送 |
| **RequestContext** | 请求上下文 | 每个请求创建，包含任务和会话信息 |

### 2.3 任务状态管理

```python
# 任务状态在TaskStore中的存储
class TaskState:
    """
    任务状态说明:
    - submitted: 任务已提交，等待处理
    - working: 任务正在执行中
    - input-required: 任务需要额外输入（多轮对话）
    - completed: 任务成功完成
    - failed: 任务执行失败
    - cancelled: 任务被取消
    """
    
    # TaskStore自动管理这些状态
    # AgentExecutor通过EventQueue更新状态
    # DefaultRequestHandler负责状态同步
```

---

## 3. 事件类型和用法

### 3.1 基本事件类型

```python
# 1. 文本消息响应
from a2a.utils import new_agent_text_message
await event_queue.enqueue_event(new_agent_text_message("Hello, World!"))

# 2. 任务状态更新
from a2a.types.events import TaskStatusUpdateEvent
await event_queue.enqueue_event(TaskStatusUpdateEvent(
    task_id=task_id,
    status="working",  # submitted, working, input-required, completed, failed, cancelled
    metadata={"progress": "50%", "current_step": "Processing data"}
))

# 3. 任务创建 (用于多轮对话)
from a2a.utils import new_task
task = new_task(
    context.message, 
    status="input-required",
    metadata={"conversation_state": "waiting_for_details"}
)
await event_queue.enqueue_event(task)

# 4. 错误事件
from a2a.types.errors import A2AError
await event_queue.enqueue_event(A2AError(
    code=-32603,
    message="Processing failed",
    data={"task_id": task_id, "error_details": "..."}
))

# 5. 任务工件更新 (用于复杂结果)
from a2a.types.events import TaskArtifactUpdateEvent
await event_queue.enqueue_event(TaskArtifactUpdateEvent(
    task_id=task_id,
    artifact={
        "type": "data", 
        "content": {"results": [...], "metadata": {...}}
    },
    append=False  # 是否追加到现有工件
))
```

### 3.2 事件发送模式

```python
class EventSendingPatterns:
    """事件发送的常见模式"""
    
    async def simple_response_pattern(self, context, event_queue):
        """简单响应模式"""
        # 1. 开始工作
        await event_queue.enqueue_event(TaskStatusUpdateEvent(
            task_id=context.get_task_id(),
            status="working"
        ))
        
        # 2. 执行任务
        result = self.process_task(context.get_user_input())
        
        # 3. 发送结果
        await event_queue.enqueue_event(new_agent_text_message(result))
        
        # 4. 标记完成
        await event_queue.enqueue_event(TaskStatusUpdateEvent(
            task_id=context.get_task_id(),
            status="completed"
        ))
    
    async def progress_reporting_pattern(self, context, event_queue):
        """进度报告模式"""
        task_id = context.get_task_id()
        steps = ["Analysis", "Processing", "Generation", "Validation"]
        
        for i, step in enumerate(steps):
            # 报告当前步骤
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="working",
                metadata={
                    "progress": i / len(steps),
                    "current_step": step,
                    "step_number": f"{i+1}/{len(steps)}"
                }
            ))
            
            # 执行步骤
            step_result = await self.execute_step(step)
            
            # 发送步骤结果
            await event_queue.enqueue_event(new_agent_text_message(
                f"✓ {step} completed: {step_result}"
            ))
    
    async def error_handling_pattern(self, context, event_queue):
        """错误处理模式"""
        task_id = context.get_task_id()
        
        try:
            # 执行任务
            result = await self.risky_operation()
            await event_queue.enqueue_event(new_agent_text_message(result))
            
        except ValidationError as e:
            # 业务逻辑错误
            await event_queue.enqueue_event(A2AError(
                code=-32602,  # Invalid params
                message=f"Input validation failed: {str(e)}",
                data={"validation_errors": e.errors}
            ))
            
        except Exception as e:
            # 系统错误
            await event_queue.enqueue_event(A2AError(
                code=-32603,  # Internal error
                message="An unexpected error occurred",
                data={"error_type": type(e).__name__}
            ))
            
            # 更新任务状态
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="failed"
            ))
```

---

## 4. 多轮对话实现

### 4.1 多轮对话的核心机制

多轮对话通过以下机制实现：
- **TaskStore**: 持久化存储任务状态和上下文
- **contextId**: 标识会话，关联多个消息
- **taskId**: 标识具体任务，可以跨多轮消息
- **status="input-required"**: 保持任务活跃，等待后续输入

### 4.2 完整的多轮对话实现

```python
class MultiTurnConversationExecutor(AgentExecutor):
    """支持多轮对话的AgentExecutor实现"""
    
    def __init__(self, url: str, adapter: Adapter):
        self.url = url
        self.adapter = adapter
        self.conversation_states = {}  # 会话状态存储
        
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        task_id = context.get_task_id()
        context_id = context.get_context_id()
        user_input = context.get_user_input()
        current_task = context.current_task
        
        # 检查是否是现有任务的延续
        if current_task and current_task.status in ["working", "input-required"]:
            await self._handle_continuation(context, event_queue, current_task)
        else:
            await self._handle_new_conversation(context, event_queue)
    
    async def _handle_new_conversation(self, context: RequestContext, event_queue: EventQueue):
        """处理新对话开始"""
        task_id = context.get_task_id()
        context_id = context.get_context_id()
        user_input = context.get_user_input()
        
        # 分析用户输入，判断是否需要更多信息
        analysis_result = self._analyze_user_request(user_input)
        
        if analysis_result["needs_more_info"]:
            # 需要更多信息，启动收集流程
            await event_queue.enqueue_event(new_agent_text_message(
                analysis_result["clarification_question"]
            ))
            
            # 创建等待输入的任务
            task = new_task(
                context.message,
                status="input-required",
                metadata={
                    "conversation_stage": "information_gathering",
                    "required_info": analysis_result["required_info"],
                    "original_request": user_input
                }
            )
            await event_queue.enqueue_event(task)
            
            # 保存会话状态
            self.conversation_states[context_id] = {
                "stage": "collecting_info",
                "original_request": user_input,
                "required_info": analysis_result["required_info"],
                "collected_info": {},
                "current_question": analysis_result["required_info"][0]
            }
            
        else:
            # 信息充足，直接处理
            await self._process_complete_request(user_input, task_id, event_queue)
    
    async def _handle_continuation(self, context: RequestContext, event_queue: EventQueue, current_task):
        """处理多轮对话的延续"""
        task_id = context.get_task_id()
        context_id = context.get_context_id()
        user_input = context.get_user_input()
        
        # 获取会话状态
        conv_state = self.conversation_states.get(context_id, {})
        
        if conv_state.get("stage") == "collecting_info":
            await self._handle_info_collection(context, event_queue, conv_state)
        elif conv_state.get("stage") == "confirmation":
            await self._handle_confirmation(context, event_queue, conv_state)
        else:
            # 未知状态，重新开始
            await self._handle_new_conversation(context, event_queue)
    
    async def _handle_info_collection(self, context: RequestContext, event_queue: EventQueue, conv_state: dict):
        """处理信息收集阶段"""
        task_id = context.get_task_id()
        context_id = context.get_context_id()
        user_input = context.get_user_input()
        
        # 记录收集到的信息
        current_question = conv_state["current_question"]
        conv_state["collected_info"][current_question] = user_input
        
        # 检查是否还需要更多信息
        remaining_info = [
            info for info in conv_state["required_info"] 
            if info not in conv_state["collected_info"]
        ]
        
        if remaining_info:
            # 还需要更多信息
            next_question = remaining_info[0]
            conv_state["current_question"] = next_question
            
            await event_queue.enqueue_event(new_agent_text_message(
                f"Thank you! Now, could you please provide information about: {next_question}?"
            ))
            
            # 保持input-required状态
            task = new_task(
                context.message,
                status="input-required",
                metadata={
                    "conversation_stage": "information_gathering",
                    "progress": f"{len(conv_state['collected_info'])}/{len(conv_state['required_info'])}"
                }
            )
            await event_queue.enqueue_event(task)
            
        else:
            # 信息收集完成，进入确认阶段
            conv_state["stage"] = "confirmation"
            
            # 生成确认摘要
            summary = self._generate_info_summary(conv_state)
            await event_queue.enqueue_event(new_agent_text_message(
                f"Perfect! I've collected all the information:\n{summary}\n\nShall I proceed with processing your request? (yes/no)"
            ))
            
            # 等待确认
            task = new_task(
                context.message,
                status="input-required",
                metadata={"conversation_stage": "confirmation"}
            )
            await event_queue.enqueue_event(task)
    
    async def _handle_confirmation(self, context: RequestContext, event_queue: EventQueue, conv_state: dict):
        """处理确认阶段"""
        task_id = context.get_task_id()
        context_id = context.get_context_id()
        user_input = context.get_user_input().lower().strip()
        
        if user_input in ["yes", "y", "proceed", "ok", "确认"]:
            # 用户确认，开始处理
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="working"
            ))
            
            await event_queue.enqueue_event(new_agent_text_message(
                "Great! Processing your request now..."
            ))
            
            # 构建完整上下文并处理
            full_context = self._build_full_context(conv_state)
            await self._process_complete_request(full_context, task_id, event_queue)
            
            # 清理会话状态
            del self.conversation_states[context_id]
            
        elif user_input in ["no", "n", "cancel", "stop", "取消"]:
            # 用户取消
            await event_queue.enqueue_event(new_agent_text_message(
                "Understood. The request has been cancelled. Feel free to start over if needed."
            ))
            
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="cancelled"
            ))
            
            # 清理会话状态
            del self.conversation_states[context_id]
            
        else:
            # 无效响应，请求再次确认
            await event_queue.enqueue_event(new_agent_text_message(
                "I didn't understand that. Please respond with 'yes' to proceed or 'no' to cancel."
            ))
            
            # 保持确认状态
            task = new_task(
                context.message,
                status="input-required",
                metadata={"conversation_stage": "confirmation"}
            )
            await event_queue.enqueue_event(task)
    
    async def _process_complete_request(self, full_request: str, task_id: str, event_queue: EventQueue):
        """处理完整的请求"""
        try:
            # 执行实际业务逻辑
            result = self.adapter.run(prompt=full_request)
            
            # 发送结果
            await event_queue.enqueue_event(new_agent_text_message(result))
            
            # 标记完成
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="completed"
            ))
            
        except Exception as e:
            await event_queue.enqueue_event(A2AError(
                code=-32603,
                message=f"Processing failed: {str(e)}"
            ))
    
    def _analyze_user_request(self, user_input: str) -> dict:
        """分析用户请求，判断是否需要更多信息"""
        # 简化的分析逻辑
        word_count = len(user_input.split())
        
        if word_count < 5:
            return {
                "needs_more_info": True,
                "clarification_question": "I'd like to help you better. Could you provide more details about what you need?",
                "required_info": ["specific_goal", "context", "preferences"]
            }
        elif "help" in user_input.lower() and word_count < 10:
            return {
                "needs_more_info": True,
                "clarification_question": "I'm here to help! What specific area do you need assistance with?",
                "required_info": ["topic", "specific_question"]
            }
        else:
            return {"needs_more_info": False}
    
    def _generate_info_summary(self, conv_state: dict) -> str:
        """生成信息收集摘要"""
        summary_parts = []
        for info_type, value in conv_state["collected_info"].items():
            summary_parts.append(f"- {info_type}: {value}")
        return "\n".join(summary_parts)
    
    def _build_full_context(self, conv_state: dict) -> str:
        """构建完整的上下文"""
        original = conv_state["original_request"]
        collected = conv_state["collected_info"]
        
        context_parts = [f"Original request: {original}"]
        context_parts.append("Additional information:")
        
        for info_type, value in collected.items():
            context_parts.append(f"- {info_type}: {value}")
            
        return "\n".join(context_parts)
```

### 4.3 多轮对话流程示例

```
第一轮 - 用户发起请求:
客户端: "Help me"
    ↓
AgentExecutor分析: 信息不足
    ↓
发送: "I'd like to help you better. Could you provide more details?"
发送: new_task(status="input-required")
    ↓
客户端收到: 文本响应 + Task(status="input-required", taskId="123")

第二轮 - 用户提供更多信息:
客户端: "I need help with Python programming" (带taskId="123")
    ↓
AgentExecutor检测到current_task存在
    ↓
收集信息，判断还需要更多细节
    ↓
发送: "What specific Python topic do you need help with?"
发送: new_task(status="input-required")
    ↓
客户端收到: 继续多轮对话

第三轮 - 用户提供具体信息:
客户端: "How to use decorators" (带taskId="123")
    ↓
AgentExecutor: 信息充足，进入确认阶段
    ↓
发送: "I understand you need help with Python decorators. Shall I proceed?"
发送: new_task(status="input-required")

第四轮 - 用户确认:
客户端: "yes" (带taskId="123")
    ↓
AgentExecutor: 开始实际处理
    ↓
发送: TaskStatusUpdateEvent(status="working")
发送: 详细的Python装饰器教程
发送: TaskStatusUpdateEvent(status="completed")
```

---

## 5. 长任务处理

### 5.1 长任务处理的设计原则

- **可取消性**: 支持任务中断和清理
- **进度报告**: 实时更新任务进展
- **错误恢复**: 优雅处理异常情况
- **资源管理**: 合理管理任务资源

### 5.2 长任务处理实现

```python
import asyncio
from datetime import datetime
from typing import Dict, List, Tuple

class LongRunningTaskExecutor(AgentExecutor):
    """支持长时间运行任务的执行器"""
    
    def __init__(self, url: str, adapter: Adapter):
        self.url = url
        self.adapter = adapter
        self.running_tasks: Dict[str, dict] = {}  # 跟踪运行中的任务
        
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        task_id = context.get_task_id()
        context_id = context.get_context_id()
        user_input = context.get_user_input()
        
        # 记录任务开始
        self.running_tasks[task_id] = {
            "start_time": datetime.now(),
            "cancelled": False,
            "context": context,
            "current_step": None
        }
        
        try:
            # 发送任务开始状态
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="working",
                metadata={
                    "started_at": datetime.now().isoformat(),
                    "estimated_duration": "5-10 minutes"
                }
            ))
            
            # 执行长时间任务
            await self._execute_long_task(task_id, user_input, event_queue)
            
        except TaskCancelledException:
            await event_queue.enqueue_event(new_agent_text_message(
                "Task was cancelled successfully."
            ))
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="cancelled"
            ))
            
        except Exception as e:
            await event_queue.enqueue_event(new_agent_text_message(
                f"Task failed due to an error: {str(e)}"
            ))
            await event_queue.enqueue_event(A2AError(
                code=-32603,
                message=f"Long task execution failed: {str(e)}",
                data={"task_id": task_id, "error_type": type(e).__name__}
            ))
            
        finally:
            # 清理任务记录
            self.running_tasks.pop(task_id, None)
    
    async def _execute_long_task(self, task_id: str, user_input: str, event_queue: EventQueue):
        """执行长时间任务，分多个步骤"""
        
        # 定义任务步骤
        steps = [
            ("Analyzing requirements", 15, self._analyze_requirements),
            ("Gathering resources", 20, self._gather_resources),
            ("Processing data", 35, self._process_data),
            ("Generating results", 20, self._generate_results),
            ("Final validation", 10, self._validate_results)
        ]
        
        task_context = {"user_input": user_input, "results": {}}
        total_weight = sum(step[1] for step in steps)
        completed_weight = 0
        
        for i, (step_name, weight, step_func) in enumerate(steps):
            # 检查是否被取消
            if self._is_task_cancelled(task_id):
                raise TaskCancelledException(f"Task {task_id} was cancelled")
            
            # 更新当前步骤
            self.running_tasks[task_id]["current_step"] = step_name
            
            # 发送步骤开始通知
            await event_queue.enqueue_event(new_agent_text_message(
                f"🔄 Step {i+1}/{len(steps)}: {step_name}..."
            ))
            
            # 发送进度更新
            progress = completed_weight / total_weight
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="working",
                metadata={
                    "progress": progress,
                    "current_step": step_name,
                    "step_number": f"{i+1}/{len(steps)}",
                    "estimated_remaining": f"{total_weight - completed_weight}%"
                }
            ))
            
            # 执行步骤
            try:
                step_result = await step_func(task_context, task_id)
                task_context["results"][step_name] = step_result
                
                # 发送步骤完成通知
                await event_queue.enqueue_event(new_agent_text_message(
                    f"✅ {step_name} completed successfully"
                ))
                
                completed_weight += weight
                
            except Exception as e:
                # 步骤失败处理
                await event_queue.enqueue_event(new_agent_text_message(
                    f"❌ {step_name} failed: {str(e)}"
                ))
                
                # 尝试恢复或跳过
                if self._can_recover_from_step_failure(step_name):
                    await event_queue.enqueue_event(new_agent_text_message(
                        f"🔄 Attempting to recover from {step_name} failure..."
                    ))
                    # 重试逻辑
                    step_result = await self._handle_step_recovery(step_name, task_context, e)
                    task_context["results"][step_name] = step_result
                else:
                    raise e
        
        # 生成最终结果
        final_result = await self._compile_final_result(task_context)
        
        # 发送最终结果
        await event_queue.enqueue_event(new_agent_text_message(
            f"🎉 Task completed successfully!\n\n{final_result}"
        ))
        
        # 发送完成状态
        await event_queue.enqueue_event(TaskStatusUpdateEvent(
            task_id=task_id,
            status="completed",
            metadata={
                "completed_at": datetime.now().isoformat(),
                "total_duration": str(datetime.now() - self.running_tasks[task_id]["start_time"]),
                "steps_completed": len(steps)
            }
        ))
    
    async def _analyze_requirements(self, context: dict, task_id: str) -> str:
        """分析需求步骤"""
        # 模拟耗时分析
        for i in range(15):
            if self._is_task_cancelled(task_id):
                raise TaskCancelledException("Cancelled during requirements analysis")
            await asyncio.sleep(0.2)  # 模拟工作
            
        return f"Requirements analyzed for: {context['user_input']}"
    
    async def _gather_resources(self, context: dict, task_id: str) -> str:
        """收集资源步骤"""
        for i in range(20):
            if self._is_task_cancelled(task_id):
                raise TaskCancelledException("Cancelled during resource gathering")
            await asyncio.sleep(0.1)
            
        return "Resources gathered successfully"
    
    async def _process_data(self, context: dict, task_id: str) -> str:
        """处理数据步骤"""
        for i in range(35):
            if self._is_task_cancelled(task_id):
                raise TaskCancelledException("Cancelled during data processing")
            await asyncio.sleep(0.1)
            
        # 实际调用adapter进行处理
        processing_result = self.adapter.run(
            prompt=f"Process this request: {context['user_input']}"
        )
        return processing_result
    
    async def _generate_results(self, context: dict, task_id: str) -> str:
        """生成结果步骤"""
        for i in range(20):
            if self._is_task_cancelled(task_id):
                raise TaskCancelledException("Cancelled during result generation")
            await asyncio.sleep(0.1)
            
        return "Results generated based on processed data"
    
    async def _validate_results(self, context: dict, task_id: str) -> str:
        """验证结果步骤"""
        for i in range(10):
            if self._is_task_cancelled(task_id):
                raise TaskCancelledException("Cancelled during validation")
            await asyncio.sleep(0.1)
            
        return "Results validated successfully"
    
    async def _compile_final_result(self, context: dict) -> str:
        """编译最终结果"""
        results = context["results"]
        final_parts = [
            f"Original Request: {context['user_input']}",
            "",
            "Processing Summary:",
        ]
        
        for step_name, result in results.items():
            final_parts.append(f"- {step_name}: {result}")
            
        final_parts.append("")
        final_parts.append("Task completed successfully with all steps executed.")
        
        return "\n".join(final_parts)
    
    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        """取消长时间任务"""
        task_id = context.get_task_id()
        
        if task_id in self.running_tasks:
            # 标记为取消状态
            self.running_tasks[task_id]["cancelled"] = True
            current_step = self.running_tasks[task_id].get("current_step")
            
            # 发送取消通知
            await event_queue.enqueue_event(new_agent_text_message(
                f"🛑 Task cancellation requested. Stopping current operation: {current_step or 'Unknown'}..."
            ))
            
            # 给任务一些时间来优雅停止
            await asyncio.sleep(1)
            
            # 发送取消确认
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="cancelled",
                metadata={
                    "cancelled_at": datetime.now().isoformat(),
                    "cancelled_during": current_step
                }
            ))
            
        else:
            await event_queue.enqueue_event(A2AError(
                code=-32602,
                message=f"Task {task_id} not found or already completed"
            ))
    
    def _is_task_cancelled(self, task_id: str) -> bool:
        """检查任务是否被取消"""
        return self.running_tasks.get(task_id, {}).get("cancelled", False)
    
    def _can_recover_from_step_failure(self, step_name: str) -> bool:
        """判断是否可以从步骤失败中恢复"""
        recoverable_steps = ["Gathering resources", "Processing data"]
        return step_name in recoverable_steps
    
    async def _handle_step_recovery(self, step_name: str, context: dict, error: Exception) -> str:
        """处理步骤恢复"""
        # 简化的恢复逻辑
        await asyncio.sleep(1)  # 等待一段时间再重试
        return f"Recovered from {step_name} failure: {str(error)}"

class TaskCancelledException(Exception):
    """任务取消异常"""
    pass
```

### 5.3 长任务的客户端体验流程

```
客户端发送: "Process this large dataset: [data]"
    ↓
立即收到: TaskStatusUpdateEvent(status="working", started_at="...", estimated_duration="5-10 minutes")
    ↓
收到: "🔄 Step 1/5: Analyzing requirements..."
    ↓
收到: TaskStatusUpdateEvent(progress=0.0, current_step="Analyzing requirements", step_number="1/5")
    ↓
收到: "✅ Analyzing requirements completed successfully"
    ↓
收到: "🔄 Step 2/5: Gathering resources..."
    ↓
收到: TaskStatusUpdateEvent(progress=0.15, current_step="Gathering resources", step_number="2/5")
    ↓
... (持续接收进度更新和步骤完成通知)
    ↓
收到: "🎉 Task completed successfully!\n\n[详细结果]"
    ↓
收到: TaskStatusUpdateEvent(status="completed", completed_at="...", total_duration="...")

如果用户取消:
客户端调用: cancel_task(task_id)
    ↓
收到: "🛑 Task cancellation requested. Stopping current operation: Processing data..."
    ↓
收到: TaskStatusUpdateEvent(status="cancelled", cancelled_at="...", cancelled_during="Processing data")
```

---

## 6. 流式响应

### 6.1 流式响应的应用场景

- **实时文本生成**: 类似ChatGPT的打字效果
- **逐步结果展示**: 分析过程的实时展示
- **长内容输出**: 避免用户等待过长时间

### 6.2 流式响应实现

```python
class StreamingResponseExecutor(AgentExecutor):
    """支持流式响应的执行器"""
    
    def __init__(self, url: str, adapter: Adapter):
        self.url = url
        self.adapter = adapter
        
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        task_id = context.get_task_id()
        user_input = context.get_user_input()
        
        # 开始任务
        await event_queue.enqueue_event(TaskStatusUpdateEvent(
            task_id=task_id,
            status="working"
        ))
        
        # 判断是否使用流式响应
        if self._should_use_streaming(user_input):
            await self._execute_streaming_response(task_id, user_input, event_queue)
        else:
            await self._execute_regular_response(task_id, user_input, event_queue)
    
    def _should_use_streaming(self, user_input: str) -> bool:
        """判断是否应该使用流式响应"""
        # 检查用户请求类型
        streaming_keywords = ["explain", "describe", "write", "generate", "create", "analyze"]
        return any(keyword in user_input.lower() for keyword in streaming_keywords)
    
    async def _execute_streaming_response(self, task_id: str, user_input: str, event_queue: EventQueue):
        """执行流式响应"""
        
        # 检查adapter是否支持流式输出
        if hasattr(self.adapter, 'stream'):
            # 使用adapter的流式方法
            async for chunk in self.adapter.stream(prompt=user_input):
                await event_queue.enqueue_event(new_agent_text_message(chunk))
                await asyncio.sleep(0.05)  # 控制流式速度
        else:
            # 模拟流式输出
            full_response = self.adapter.run(prompt=user_input)
            await self._simulate_streaming(full_response, event_queue)
        
        # 完成
        await event_queue.enqueue_event(TaskStatusUpdateEvent(
            task_id=task_id,
            status="completed"
        ))
    
    async def _simulate_streaming(self, full_response: str, event_queue: EventQueue):
        """模拟流式输出"""
        words = full_response.split()
        chunk_size = 3  # 每次发送3个词
        
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            if i + chunk_size < len(words):
                chunk += " "
            
            await event_queue.enqueue_event(new_agent_text_message(chunk))
            await asyncio.sleep(0.1)  # 控制流式速度
    
    async def _execute_regular_response(self, task_id: str, user_input: str, event_queue: EventQueue):
        """执行常规响应"""
        result = self.adapter.run(prompt=user_input)
        await event_queue.enqueue_event(new_agent_text_message(result))
        
        await event_queue.enqueue_event(TaskStatusUpdateEvent(
            task_id=task_id,
            status="completed"
        ))


class AdvancedStreamingExecutor(AgentExecutor):
    """高级流式响应执行器，支持多种流式模式"""
    
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        task_id = context.get_task_id()
        user_input = context.get_user_input()
        
        # 分析请求类型
        request_type = self._analyze_request_type(user_input)
        
        await event_queue.enqueue_event(TaskStatusUpdateEvent(
            task_id=task_id,
            status="working"
        ))
        
        if request_type == "analysis":
            await self._stream_analysis_response(task_id, user_input, event_queue)
        elif request_type == "creative_writing":
            await self._stream_creative_response(task_id, user_input, event_queue)
        elif request_type == "code_generation":
            await self._stream_code_response(task_id, user_input, event_queue)
        else:
            await self._stream_general_response(task_id, user_input, event_queue)
    
    async def _stream_analysis_response(self, task_id: str, user_input: str, event_queue: EventQueue):
        """流式分析响应"""
        
        # 分析步骤
        analysis_steps = [
            ("🔍 Initial Assessment", "Let me start by examining the key aspects..."),
            ("📊 Data Analysis", "Now analyzing the data patterns and trends..."),
            ("🎯 Key Insights", "Based on the analysis, here are the main findings:"),
            ("💡 Recommendations", "Given these insights, I recommend the following actions:"),
            ("📋 Summary", "To summarize the complete analysis:")
        ]
        
        for step_title, intro_text in analysis_steps:
            # 发送步骤标题
            await event_queue.enqueue_event(new_agent_text_message(f"\n## {step_title}\n\n"))
            await asyncio.sleep(0.3)
            
            # 发送介绍文本
            await event_queue.enqueue_event(new_agent_text_message(intro_text))
            await asyncio.sleep(0.5)
            
            # 生成并流式发送该步骤的内容
            step_content = self.adapter.run(prompt=f"{user_input} - Focus on: {step_title}")
            await self._stream_text_gradually(step_content, event_queue)
            
            await asyncio.sleep(0.5)  # 步骤间停顿
        
        await event_queue.enqueue_event(TaskStatusUpdateEvent(
            task_id=task_id,
            status="completed"
        ))
    
    async def _stream_creative_response(self, task_id: str, user_input: str, event_queue: EventQueue):
        """流式创意写作响应"""
        
        # 发送开始提示
        await event_queue.enqueue_event(new_agent_text_message("✨ Starting creative writing...\n\n"))
        await asyncio.sleep(1)
        
        # 生成内容
        creative_content = self.adapter.run(prompt=user_input)
        
        # 按句子流式输出
        sentences = creative_content.split('. ')
        for i, sentence in enumerate(sentences):
            if i > 0:
                sentence = '. ' + sentence
            
            # 按字符逐步输出每个句子
            for char in sentence:
                await event_queue.enqueue_event(new_agent_text_message(char))
                await asyncio.sleep(0.02)  # 打字机效果
            
            await asyncio.sleep(0.3)  # 句子间停顿
        
        await event_queue.enqueue_event(TaskStatusUpdateEvent(
            task_id=task_id,
            status="completed"
        ))
    
    async def _stream_code_response(self, task_id: str, user_input: str, event_queue: EventQueue):
        """流式代码生成响应"""
        
        # 发送代码生成开始提示
        await event_queue.enqueue_event(new_agent_text_message("```python\n# Generating code...\n\n"))
        await asyncio.sleep(1)
        
        # 生成代码
        code_content = self.adapter.run(prompt=user_input)
        
        # 按行流式输出代码
        lines = code_content.split('\n')
        for line in lines:
            await event_queue.enqueue_event(new_agent_text_message(line + '\n'))
            await asyncio.sleep(0.1)  # 控制代码输出速度
        
        await event_queue.enqueue_event(new_agent_text_message("```\n"))
        
        await event_queue.enqueue_event(TaskStatusUpdateEvent(
            task_id=task_id,
            status="completed"
        ))
    
    async def _stream_text_gradually(self, text: str, event_queue: EventQueue):
        """逐步流式输出文本"""
        words = text.split()
        chunk_size = 4  # 每次输出4个词
        
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            if i + chunk_size < len(words):
                chunk += " "
            
            await event_queue.enqueue_event(new_agent_text_message(chunk))
            await asyncio.sleep(0.15)
    
    def _analyze_request_type(self, user_input: str) -> str:
        """分析请求类型"""
        input_lower = user_input.lower()
        
        if any(word in input_lower for word in ["analyze", "analysis", "examine", "evaluate"]):
            return "analysis"
        elif any(word in input_lower for word in ["write", "story", "poem", "creative"]):
            return "creative_writing"
        elif any(word in input_lower for word in ["code", "function", "class", "script", "program"]):
            return "code_generation"
        else:
            return "general"
```

---

## 7. ISEK集成方案

### 7.1 集成架构设计

ISEK的优势在于其分层架构，可以在Adapter层进行增强而无需修改底层的Agent实现：

```python
# ISEK集成架构
A2A Protocol Layer (增强的DefaultAgentExecutor)
    ↓
Enhanced Adapter Layer (传递A2A上下文)
    ↓
IsekTeam Layer (现有实现，支持session_id和memory)
    ↓
IsekAgent Layer (底层agents，无需修改)
```

### 7.2 增强的IsekAdapter实现

```python
from isek.adapter.base import Adapter, AdapterCard
from isek.team.isek_team import IsekTeam
from isek.memory.memory import Memory, SessionSummary
from datetime import datetime
from typing import Optional, AsyncGenerator

class EnhancedIsekAdapter(Adapter):
    """支持A2A完整功能的ISEK适配器"""
    
    def __init__(self, isek_team: IsekTeam, enable_streaming: bool = False):
        self._isek_team = isek_team
        self.enable_streaming = enable_streaming
        self._ensure_memory_system()
        
    def _ensure_memory_system(self):
        """确保IsekTeam有Memory系统"""
        if not self._isek_team.memory:
            self._isek_team.memory = Memory()
    
    def run(self, prompt: str, **kwargs) -> str:
        """执行任务，支持A2A上下文传递"""
        # 从kwargs中获取A2A上下文信息
        session_id = kwargs.get('session_id')
        user_id = kwargs.get('user_id', 'default')
        task_id = kwargs.get('task_id')
        
        # 构建增强的上下文
        enhanced_prompt = self._build_context_aware_prompt(prompt, session_id, user_id)
        
        # 调用IsekTeam执行
        result = self._isek_team.run(
            message=enhanced_prompt,
            user_id=user_id,
            session_id=session_id
        )
        
        # 记录执行结果到A2A上下文
        self._record_execution_result(session_id, user_id, prompt, result, task_id)
        
        return result
    
    async def stream(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """流式响应支持"""
        if not self.enable_streaming:
            # 如果不支持流式，模拟流式输出
            result = self.run(prompt, **kwargs)
            words = result.split()
            chunk_size = 5
            
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i:i + chunk_size])
                if i + chunk_size < len(words):
                    chunk += " "
                yield chunk
        else:
            # 如果IsekTeam支持流式输出
            if hasattr(self._isek_team, 'stream'):
                async for chunk in self._isek_team.stream(prompt, **kwargs):
                    yield chunk
            else:
                # 回退到模拟流式
                result = self.run(prompt, **kwargs)
                for word in result.split():
                    yield word + " "
    
    def _build_context_aware_prompt(self, prompt: str, session_id: Optional[str], user_id: str) -> str:
        """构建上下文感知的提示词"""
        if not session_id or not self._isek_team.memory:
            return prompt
            
        # 获取会话历史
        session_summary = self._isek_team.memory.get_session_summary(session_id, user_id)
        user_memories = self._isek_team.memory.get_user_memories(user_id)
        
        context_parts = []
        
        # 添加会话历史
        if session_summary:
            context_parts.append(f"Previous conversation context:\n{session_summary.summary}")
        
        # 添加相关的用户记忆
        if user_memories:
            recent_memories = user_memories[-3:]  # 最近3条记忆
            memory_text = "\n".join([f"- {memory.memory}" for memory in recent_memories])
            context_parts.append(f"Relevant memories:\n{memory_text}")
        
        # 添加当前输入
        context_parts.append(f"Current request: {prompt}")
        
        return "\n\n".join(context_parts)
    
    def _record_execution_result(self, session_id: Optional[str], user_id: str, 
                               prompt: str, result: str, task_id: Optional[str]):
        """记录执行结果到记忆系统"""
        if not session_id or not self._isek_team.memory:
            return
            
        # 构建对话记录
        conversation_record = f"User: {prompt}\nAgent: {result}"
        
        # 获取现有会话摘要
        existing_summary = self._isek_team.memory.get_session_summary(session_id, user_id)
        
        if existing_summary:
            # 更新现有摘要
            new_summary_text = f"{existing_summary.summary}\n\n{conversation_record}"
        else:
            # 创建新摘要
            new_summary_text = conversation_record
        
        # 保存会话摘要
        new_summary = SessionSummary(
            summary=new_summary_text,
            topics=self._extract_topics(prompt, result),
            last_updated=datetime.now()
        )
        
        self._isek_team.memory.add_session_summary(session_id, new_summary, user_id)
        
        # 如果有task_id，记录到runs中
        if task_id:
            run_data = {
                "task_id": task_id,
                "user_input": prompt,
                "agent_response": result,
                "timestamp": datetime.now().isoformat()
            }
            self._isek_team.memory.add_run(session_id, run_data)
    
    def _extract_topics(self, user_input: str, agent_response: str) -> list:
        """提取对话主题"""
        # 简化的主题提取
        text = f"{user_input} {agent_response}".lower()
        potential_topics = ["question", "help", "analysis", "task", "information", "problem"]
        return [topic for topic in potential_topics if topic in text]
    
    def get_adapter_card(self) -> AdapterCard:
        """获取增强的adapter卡片"""
        team_config = self._isek_team.get_agent_config()
        
        return AdapterCard(
            name=team_config.get("name", "ISEK Team"),
            bio=f"Enhanced A2A Agent: {team_config.get('description', 'A team of ISEK agents')}",
            lore=f"A2A-enabled ISEK team with memory and context management. {team_config.get('lore', '')}",
            knowledge=team_config.get('knowledge', 'Distributed agent knowledge'),
            routine=f"A2A Protocol Support: {team_config.get('instructions', 'Coordinate team members effectively')}"
        )
    
    def supports_cancellation(self) -> bool:
        """是否支持任务取消"""
        return hasattr(self._isek_team, 'cancel_task')
    
    def supports_streaming(self) -> bool:
        """是否支持流式响应"""
        return self.enable_streaming or hasattr(self._isek_team, 'stream')
```

### 7.3 增强的DefaultAgentExecutor for ISEK

```python
from isek.protocol.a2a_protocol import DefaultAgentExecutor
from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.types.events import TaskStatusUpdateEvent
from a2a.types.errors import A2AError
from a2a.utils import new_agent_text_message
from datetime import datetime
import asyncio

class ISEKEnhancedAgentExecutor(DefaultAgentExecutor):
    """为ISEK优化的A2A AgentExecutor"""
    
    def __init__(self, url: str, adapter: EnhancedIsekAdapter):
        super().__init__(url, adapter)
        self.running_tasks = {}
        
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id = context.get_task_id()
        context_id = context.get_context_id()
        user_input = context.get_user_input()
        
        # 记录任务开始
        self.running_tasks[task_id] = {
            "start_time": datetime.now(),
            "cancelled": False,
            "context_id": context_id
        }
        
        try:
            # 发送任务开始状态
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="working",
                metadata={"started_at": datetime.now().isoformat()}
            ))
            
            # 检查是否支持流式输出
            if self.adapter.supports_streaming() and self._should_use_streaming(user_input):
                await self._execute_streaming(task_id, context_id, user_input, event_queue)
            else:
                await self._execute_regular(task_id, context_id, user_input, event_queue)
                
        except Exception as e:
            await event_queue.enqueue_event(A2AError(
                code=-32603,
                message=f"ISEK execution failed: {str(e)}",
                data={"task_id": task_id, "context_id": context_id}
            ))
        finally:
            # 清理任务记录
            self.running_tasks.pop(task_id, None)
    
    async def _execute_regular(self, task_id: str, context_id: str, user_input: str, event_queue: EventQueue):
        """常规执行模式"""
        result = self.adapter.run(
            prompt=user_input,
            session_id=context_id,
            user_id="default",
            task_id=task_id
        )
        
        await event_queue.enqueue_event(new_agent_text_message(result))
        
        await event_queue.enqueue_event(TaskStatusUpdateEvent(
            task_id=task_id,
            status="completed"
        ))
    
    async def _execute_streaming(self, task_id: str, context_id: str, user_input: str, event_queue: EventQueue):
        """流式执行模式"""
        async for chunk in self.adapter.stream(
            prompt=user_input,
            session_id=context_id,
            user_id="default",
            task_id=task_id
        ):
            # 检查是否被取消
            if self._is_task_cancelled(task_id):
                await event_queue.enqueue_event(TaskStatusUpdateEvent(
                    task_id=task_id,
                    status="cancelled"
                ))
                return
                
            await event_queue.enqueue_event(new_agent_text_message(chunk))
            await asyncio.sleep(0.05)  # 控制流式速度
        
        await event_queue.enqueue_event(TaskStatusUpdateEvent(
            task_id=task_id,
            status="completed"
        ))
    
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """取消任务执行"""
        task_id = context.get_task_id()
        
        if task_id in self.running_tasks:
            # 标记为取消状态
            self.running_tasks[task_id]["cancelled"] = True
            
            # 如果adapter支持取消
            if self.adapter.supports_cancellation():
                # 调用adapter的取消方法
                if hasattr(self.adapter._isek_team, 'cancel_task'):
                    self.adapter._isek_team.cancel_task(task_id)
            
            await event_queue.enqueue_event(new_agent_text_message(
                "Task cancellation requested. Stopping ISEK team operations..."
            ))
            
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="cancelled",
                metadata={"cancelled_at": datetime.now().isoformat()}
            ))
        else:
            await event_queue.enqueue_event(A2AError(
                code=-32602,
                message=f"Task {task_id} not found in ISEK executor"
            ))
    
    def _should_use_streaming(self, user_input: str) -> bool:
        """判断是否应该使用流式响应"""
        streaming_indicators = ["explain", "describe", "write", "generate", "analyze", "create"]
        return any(indicator in user_input.lower() for indicator in streaming_indicators)
    
    def _is_task_cancelled(self, task_id: str) -> bool:
        """检查任务是否被取消"""
        return self.running_tasks.get(task_id, {}).get("cancelled", False)
```

### 7.4 集成配置更新

```python
# 在 a2a_protocol.py 中的build_a2a_application方法更新
def build_a2a_application(self) -> JSONRPCApplication:
    if not self.adapter or not isinstance(self.adapter, Adapter):
        raise ValueError("A Adapter must be provided to the A2AProtocol.")
    
    # 如果是IsekAdapter，升级为EnhancedIsekAdapter
    if isinstance(self.adapter, IsekAdapter):
        enhanced_adapter = EnhancedIsekAdapter(
            self.adapter._isek_team,
            enable_streaming=True  # 启用流式支持
        )
    else:
        enhanced_adapter = self.adapter
    
    # 使用增强的AgentExecutor
    agent_executor = ISEKEnhancedAgentExecutor(self.url, enhanced_adapter)
    
    # 使用增强的TaskStore（可选）
    task_store = InMemoryTaskStore()  # 或者自定义的持久化TaskStore
    
    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=task_store,
    )

    return A2AStarletteApplication(
        agent_card=agent_executor.get_a2a_agent_card(),
        http_handler=request_handler,
    )
```

---

## 8. 最佳实践

### 8.1 EventQueue使用最佳实践

```python
class EventQueueBestPractices:
    """EventQueue使用的最佳实践"""
    
    async def proper_event_handling(self, context: RequestContext, event_queue: EventQueue):
        """正确的事件处理模式"""
        task_id = context.get_task_id()
        
        try:
            # 1. 总是在开始时发送工作状态
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="working"
            ))
            
            # 2. 为长时间操作提供进度更新
            total_steps = 5
            for i in range(total_steps):
                # 执行步骤
                step_result = await self.execute_step(i)
                
                # 发送进度更新
                await event_queue.enqueue_event(TaskStatusUpdateEvent(
                    task_id=task_id,
                    status="working",
                    metadata={
                        "progress": (i + 1) / total_steps,
                        "current_step": f"Step {i + 1}",
                        "step_result": step_result
                    }
                ))
            
            # 3. 发送最终结果
            final_result = "Task completed successfully"
            await event_queue.enqueue_event(new_agent_text_message(final_result))
            
            # 4. 总是标记任务完成
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="completed"
            ))
            
        except Exception as e:
            # 5. 适当的错误处理
            await event_queue.enqueue_event(A2AError(
                code=-32603,
                message=f"Task failed: {str(e)}",
                data={"task_id": task_id}
            ))
            
            # 6. 错误时也要更新任务状态
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="failed"
            ))
    
    async def streaming_best_practices(self, context: RequestContext, event_queue: EventQueue):
        """流式响应最佳实践"""
        task_id = context.get_task_id()
        
        # 1. 控制流式速度，避免过快输出
        chunk_delay = 0.05  # 50ms延迟
        
        # 2. 合理的chunk大小
        chunk_size = 5  # 每次5个词
        
        # 3. 提供流式进度指示
        response_parts = ["Part 1", "Part 2", "Part 3"]
        total_parts = len(response_parts)
        
        for i, part in enumerate(response_parts):
            # 发送内容
            await event_queue.enqueue_event(new_agent_text_message(part))
            
            # 更新流式进度
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="working",
                metadata={
                    "streaming_progress": (i + 1) / total_parts,
                    "current_part": i + 1,
                    "total_parts": total_parts
                }
            ))
            
            await asyncio.sleep(chunk_delay)
        
        # 4. 流式完成后标记任务完成
        await event_queue.enqueue_event(TaskStatusUpdateEvent(
            task_id=task_id,
            status="completed"
        ))
```

### 8.2 任务管理最佳实践

```python
class TaskManagementBestPractices:
    """任务管理最佳实践"""
    
    def __init__(self):
        self.task_timeouts = {}  # 任务超时管理
        self.task_resources = {}  # 任务资源管理
    
    async def robust_task_execution(self, context: RequestContext, event_queue: EventQueue):
        """健壮的任务执行"""
        task_id = context.get_task_id()
        
        # 1. 设置任务超时
        timeout_duration = 300  # 5分钟超时
        timeout_task = asyncio.create_task(self._task_timeout_handler(task_id, timeout_duration))
        
        try:
            # 2. 执行任务with超时控制
            main_task = asyncio.create_task(self._execute_main_task(context, event_queue))
            
            # 3. 等待任务完成或超时
            done, pending = await asyncio.wait(
                [main_task, timeout_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # 4. 处理结果
            if main_task in done:
                # 任务正常完成
                timeout_task.cancel()
                return await main_task
            else:
                # 任务超时
                main_task.cancel()
                await event_queue.enqueue_event(A2AError(
                    code=-32603,
                    message="Task execution timeout",
                    data={"task_id": task_id, "timeout": timeout_duration}
                ))
                
        except asyncio.CancelledError:
            # 5. 任务被取消
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="cancelled"
            ))
        finally:
            # 6. 清理资源
            await self._cleanup_task_resources(task_id)
    
    async def _task_timeout_handler(self, task_id: str, timeout_duration: int):
        """任务超时处理"""
        await asyncio.sleep(timeout_duration)
        # 超时逻辑在上层处理
    
    async def _cleanup_task_resources(self, task_id: str):
        """清理任务资源"""
        # 清理内存资源
        self.task_timeouts.pop(task_id, None)
        self.task_resources.pop(task_id, None)
        
        # 清理临时文件等
        # ...
```

### 8.3 错误处理最佳实践

```python
class ErrorHandlingBestPractices:
    """错误处理最佳实践"""
    
    async def comprehensive_error_handling(self, context: RequestContext, event_queue: EventQueue):
        """全面的错误处理"""
        task_id = context.get_task_id()
        
        try:
            # 主要业务逻辑
            result = await self.execute_business_logic(context)
            await event_queue.enqueue_event(new_agent_text_message(result))
            
        except ValidationError as e:
            # 1. 用户输入错误
            await event_queue.enqueue_event(A2AError(
                code=-32602,  # Invalid params
                message="Input validation failed",
                data={
                    "validation_errors": str(e),
                    "suggestions": "Please check your input format"
                }
            ))
            
        except TimeoutError as e:
            # 2. 超时错误
            await event_queue.enqueue_event(A2AError(
                code=-32603,  # Internal error
                message="Operation timeout",
                data={
                    "timeout_duration": str(e),
                    "suggestion": "Try breaking down your request into smaller parts"
                }
            ))
            
        except ResourceExhaustedException as e:
            # 3. 资源不足
            await event_queue.enqueue_event(A2AError(
                code=-32603,
                message="Insufficient resources",
                data={
                    "resource_type": e.resource_type,
                    "suggestion": "Please try again later when resources are available"
                }
            ))
            
        except Exception as e:
            # 4. 未知错误
            await event_queue.enqueue_event(A2AError(
                code=-32603,
                message="An unexpected error occurred",
                data={
                    "error_type": type(e).__name__,
                    "suggestion": "Please contact support if this persists"
                }
            ))
            
        finally:
            # 5. 确保任务状态更新
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                task_id=task_id,
                status="failed"  # 或根据具体情况设置
            ))
```

### 8.4 性能优化最佳实践

```python
class PerformanceOptimizationBestPractices:
    """性能优化最佳实践"""
    
    def __init__(self):
        self.event_batch = []
        self.batch_size = 10
        self.batch_timeout = 0.1  # 100ms
    
    async def batched_event_sending(self, events: list, event_queue: EventQueue):
        """批量事件发送优化"""
        # 对于大量事件，可以考虑批量发送
        for i in range(0, len(events), self.batch_size):
            batch = events[i:i + self.batch_size]
            
            # 发送批次中的事件
            for event in batch:
                await event_queue.enqueue_event(event)
            
            # 批次间短暂停顿，避免overwhelm客户端
            await asyncio.sleep(self.batch_timeout)
    
    async def memory_efficient_streaming(self, large_content: str, event_queue: EventQueue):
        """内存高效的流式处理"""
        # 对于大内容，使用生成器避免内存占用
        def content_generator():
            words = large_content.split()
            chunk_size = 20
            
            for i in range(0, len(words), chunk_size):
                yield " ".join(words[i:i + chunk_size]) + " "
        
        for chunk in content_generator():
            await event_queue.enqueue_event(new_agent_text_message(chunk))
            await asyncio.sleep(0.05)
    
    async def resource_pooling(self, context: RequestContext, event_queue: EventQueue):
        """资源池化管理"""
        # 使用连接池、线程池等资源管理
        # 这里是概念性示例
        
        async with self.get_resource_from_pool() as resource:
            result = await resource.process(context.get_user_input())
            await event_queue.enqueue_event(new_agent_text_message(result))
```

---

## 总结

EventQueue是A2A协议中实现异步通信和状态管理的核心机制。通过正确使用EventQueue，ISEK可以：

1. **支持实时状态更新** - 客户端可以实时了解任务进展
2. **实现多轮对话** - 通过任务状态管理维护会话连续性
3. **处理长时间任务** - 支持可取消的长任务和进度报告
4. **提供流式响应** - 改善用户体验的实时反馈
5. **保持架构优雅** - 在不修改底层Agent的情况下增强功能

关键是理解EventQueue作为桥梁的作用，正确处理事件的发送时机和类型，以及合理管理任务状态和资源。ISEK的分层架构使得这种集成变得相对简单和安全。

---

## 附录

### 相关文件
- A2A协议实现: `/Users/sparkss/ISEKOS/isek/protocol/a2a_protocol.py`
- Memory系统: `/Users/sparkss/ISEKOS/isek/memory/memory.py`
- ISEK团队实现: `/Users/sparkss/ISEKOS/isek/team/isek_team.py`

### 依赖包
```python
# requirements.txt 建议添加
a2a-sdk>=1.0.0
httpx>=0.24.0
uvicorn>=0.22.0
pydantic>=2.0.0
asyncio  # Python标准库
```

### 错误代码参考
- `-32602`: Invalid params (用户输入错误)
- `-32603`: Internal error (系统内部错误)  
- `-32000`: Server error (服务器错误)