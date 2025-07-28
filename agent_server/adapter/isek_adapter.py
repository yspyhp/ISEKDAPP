"""
Simplified ISEK Team Adapter for A2A Protocol
基于a2a native服务的简化ISEK适配器，保留核心功能，提高可维护性
"""

import asyncio
from typing import Any, AsyncGenerator, Optional, Dict, List
from datetime import datetime

# A2A native imports
from a2a.utils import new_agent_text_message, new_task
from a2a.types import TaskStatusUpdateEvent, A2AError, TaskState, TaskStatus, Task

# ISEK imports
from isek.adapter.base import Adapter, AdapterCard
from isek.team.isek_team import IsekTeam
from utils.session import SessionManager
from utils.task import EnhancedTaskStore, TaskCancelledException


class UnifiedIsekAdapter(Adapter):
    """
    简化的ISEK适配器 - 基于a2a native服务
    
    核心功能：
    - 任务管理：基于a2a native TaskStore
    - 会话管理：基于a2a native SessionService
    - 多轮对话：信息收集和确认流程
    - 流式响应：实时输出支持
    """
    
    def __init__(self, isek_team: IsekTeam, enable_streaming: bool = False):
        """初始化简化的ISEK适配器 - 移除复杂的对话状态管理"""
        self.isek_team = isek_team
        self.enable_streaming = enable_streaming
        self.session_manager = SessionManager()
        self.task_store = EnhancedTaskStore()
        self.running_tasks = {}  # 活跃任务跟踪
        # 移除 self.conversation_states - 让AI自然处理多轮对话
    
    async def execute_async(self, context: dict) -> AsyncGenerator[Any, None]:
        """异步执行任务并生成A2A事件流 - 简化版，让AI处理多轮对话"""
        task_id = context["task_id"]
        session_id = context["session_id"]
        user_input = context["user_input"]
        
        try:
            # 1. 创建和跟踪任务
            await self.task_store.create_task(task_id, session_id)
            self.running_tasks[task_id] = {
                "cancelled": False,
                "start_time": datetime.now(),
                "session_id": session_id
            }
            
            # 2. 发送任务开始事件
            yield TaskStatusUpdateEvent(
                contextId=session_id,
                taskId=task_id,
                status=TaskStatus(state=TaskState.working),
                final=False,
                metadata={"started_at": datetime.now().isoformat()}
            )
            
            # 3. 会话管理和上下文构建
            session_context = await self._manage_session_context(session_id, user_input)
            enhanced_prompt = self._build_contextual_prompt(user_input, session_context)
            
            # 4. 执行任务 - 简化执行逻辑
            async for event in self._execute_task(task_id, session_id, enhanced_prompt):
                if self._is_task_cancelled(task_id):
                    break
                yield event
            
            # 5. 完成任务
            if not self._is_task_cancelled(task_id):
                await self.task_store.update_task_status(task_id, TaskState.completed)
                yield TaskStatusUpdateEvent(
                    contextId=session_id,
                    taskId=task_id,
                    status=TaskStatus(state=TaskState.completed),
                    final=True
                )
                
        except TaskCancelledException:
            # Handle task cancellation gracefully
            yield TaskStatusUpdateEvent(
                contextId=session_id,
                taskId=task_id,
                status=TaskStatus(state=TaskState.cancelled),
                final=True
            )
        except Exception as e:
            # Handle execution errors
            await self.task_store.update_task_status(task_id, TaskState.failed)
            yield A2AError(
                code=-32603,
                message=f"ISEK team execution failed: {str(e)}",
                data={"task_id": task_id}
            )
        finally:
            # Clean up running task tracking
            self.running_tasks.pop(task_id, None)
    
    async def cancel_async(self, context: dict) -> AsyncGenerator[Any, None]:
        """
        Cancel a running task - Follows A2A best practices
        
        Args:
            context: Dictionary containing task_id to cancel
            
        Yields:
            Cancellation confirmation or error event
        """
        task_id = context["task_id"]
        if task_id in self.running_tasks:
            # Mark task as cancelled
            self.running_tasks[task_id]["cancelled"] = True
            await self.task_store.update_task_status(task_id, TaskState.cancelled)
            
            # Send cancellation confirmation
            yield TaskStatusUpdateEvent(
                contextId=self.running_tasks[task_id]["session_id"],
                taskId=task_id,
                status=TaskStatus(state=TaskState.cancelled),
                final=True,
                metadata={"cancelled_at": datetime.now().isoformat()}
            )
        else:
            # Task not found or already completed
            yield A2AError(
                code=-32602,
                message=f"Task {task_id} not found or already completed"
            )
    
    async def _manage_session_context(self, session_id: str, user_input: str) -> dict:
        """简化会话上下文管理 - 参考A2A samples模式"""
        if not self.session_manager.get_session_context(session_id):
            self.session_manager.create_session_context(session_id)
        self.session_manager.update_session_activity(session_id)
        
        # 简化返回，减少复杂度
        return {"session_id": session_id}
    
    # 移除复杂的多轮对话分析 - 让AI自然处理
    
    # 移除复杂的对话状态管理 - 让AI自然处理多轮对话
    
    # 移除复杂的信息收集状态管理 - 让AI自然处理
    
    # 移除复杂的确认状态管理 - 让AI自然处理
    
    # 移除复杂的新对话处理 - 让AI自然处理
    
    # 移除复杂的多轮流程管理 - 让AI自然处理
    
    def _build_contextual_prompt(self, user_input: str, session_context: dict) -> str:
        """构建上下文提示 - A2A samples风格"""
        session_id = session_context.get("session_id")
        if not session_id:
            return user_input
        
        # 获取简化的上下文，让AI处理复杂逻辑
        recent_context = self.session_manager.get_conversation_context(session_id, limit=2)
        if recent_context:
            return f"Previous context:\n{recent_context}\n\nCurrent: {user_input}"
        return user_input
    
    # 移除过于简单的长任务判断 - 让AI自然处理所有任务
    
    # 移除复杂的长任务模拟 - 统一任务执行
    
    async def _execute_task(self, task_id: str, session_id: str, prompt: str) -> AsyncGenerator[Any, None]:
        """统一任务执行 - A2A samples风格"""
        try:
            if self.enable_streaming and hasattr(self.isek_team, 'stream'):
                # 流式执行 - 直接输出
                async for chunk in self.isek_team.stream(
                    message=prompt, user_id="default", session_id=session_id
                ):
                    if self._is_task_cancelled(task_id):
                        break
                    yield new_agent_text_message(chunk)
            else:
                # 非流式执行 - 简化版
                result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.isek_team.run(
                        message=prompt, user_id="default", session_id=session_id
                    )
                )
                # 保存对话记录
                self.session_manager.save_conversation_turn(session_id, prompt, result)
                yield new_agent_text_message(result)
        except Exception as e:
            # 简化错误处理
            yield new_agent_text_message(f"Error: {str(e)}")
    
    # 移除复杂的流式模拟 - 统一到_execute_task
    
    # 移除重复的会话保存包装 - 直接使用session_manager
    
    def _is_task_cancelled(self, task_id: str) -> bool:
        """
        Check if a task has been cancelled
        
        Args:
            task_id: Task identifier to check
            
        Returns:
            True if task is cancelled, False otherwise
        """
        return self.running_tasks.get(task_id, {}).get("cancelled", False)
    
    # 移除复杂的信息汇总生成 - 让AI自然处理
    
    # 移除复杂的上下文构建 - 让AI自然处理
    
    def run(self, prompt: str, **kwargs) -> str:
        """同步执行方法 - A2A samples风格简化"""
        return self.isek_team.run(
            message=prompt,
            user_id=kwargs.get("user_id", "default"),
            session_id=kwargs.get("session_id", "default")
        )
    
    def get_adapter_card(self) -> AdapterCard:
        """获取适配器卡片信息 - 简化版"""
        team_name = getattr(self.isek_team, 'name', 'ISEK Team')
        team_description = getattr(self.isek_team, 'description', 'AI agent team')
        
        return AdapterCard(
            name=team_name,
            bio=f"A2A-enabled {team_description}",
            lore=f"Intelligent agent team with A2A protocol support",
            knowledge="AI team coordination and task execution",
            routine="Execute tasks efficiently with context awareness"
        )
    
    # A2A 能力查询方法 - 简化版
    def supports_streaming(self) -> bool: return self.enable_streaming
    def supports_cancellation(self) -> bool: return True  
    def supports_multiturn(self) -> bool: return True


