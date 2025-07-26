"""
Unified ISEK Team Adapter for A2A Protocol
统一的ISEK Team适配器 - 包含所有功能：任务管理、会话管理、多轮对话、长任务支持、流式响应
"""

import asyncio
from typing import Any, AsyncGenerator, Optional, Dict, List
from datetime import datetime

from a2a.utils import new_agent_text_message, new_task
from a2a.types import TaskStatusUpdateEvent, A2AError, TaskState, TaskStatus, Task

from isek.adapter.base import Adapter, AdapterCard
from isek.team.isek_team import IsekTeam
from utils.session import SessionManager
from utils.task import EnhancedTaskStore, TaskCancelledException


class UnifiedIsekAdapter(Adapter):
    """
    统一的ISEK适配器 - 包含所有复杂业务逻辑
    - 任务管理：生命周期跟踪、进度报告、取消支持
    - 会话管理：对话历史、上下文感知
    - 多轮对话：信息收集、确认流程
    - 长任务支持：可取消的长时间任务
    - 流式响应：实时输出支持
    遵循Google A2A最佳实践
    """
    
    def __init__(self, isek_team: IsekTeam, enable_streaming: bool = False):
        self.isek_team = isek_team
        self.enable_streaming = enable_streaming
        self.session_manager = SessionManager()
        self.task_store = EnhancedTaskStore()
        self.running_tasks = {}
        self.conversation_states = {}  # 多轮对话状态
    
    async def execute_async(self, context: dict) -> AsyncGenerator[Any, None]:
        """异步执行任务，产生事件流 - 遵循A2A最佳实践"""
        task_id = context["task_id"]
        session_id = context["session_id"]
        user_input = context["user_input"]
        current_task = context.get("current_task")
        
        try:
            # 1. 任务管理 - 创建任务
            await self.task_store.create_task(task_id, session_id)
            self.running_tasks[task_id] = {
                "cancelled": False,
                "start_time": datetime.now(),
                "session_id": session_id
            }
            
            # 2. 发送任务开始状态
            yield TaskStatusUpdateEvent(
                contextId=session_id,
                taskId=task_id,
                status=TaskStatus(state=TaskState.working),
                final=False,
                metadata={"started_at": datetime.now().isoformat()}
            )
            
            # 3. 会话管理 - 获取和管理会话上下文
            session_context = await self._manage_session_context(session_id, user_input)
            
            # 4. 多轮对话处理
            if current_task and current_task.status in ["working", "input-required"]:
                # 处理多轮对话的延续
                async for event in self._handle_conversation_continuation(
                    task_id, session_id, user_input, session_context
                ):
                    if self._is_task_cancelled(task_id):
                        break
                    yield event
                return
            
            # 5. 检查是否需要多轮对话收集信息
            multiturn_result = await self._analyze_multiturn_requirement(user_input)
            
            if multiturn_result["needs_more_info"]:
                # 需要更多信息，进入多轮对话模式
                async for event in self._handle_multiturn_flow(
                    task_id, session_id, multiturn_result, session_context
                ):
                    if self._is_task_cancelled(task_id):
                        break
                    yield event
                return
            
            # 6. 构建增强的上下文提示
            enhanced_prompt = self._build_contextual_prompt(user_input, session_context)
            
            # 7. 长任务支持 - 根据输入判断是否为长任务
            if self._is_long_running_task(enhanced_prompt):
                async for event in self._execute_long_task(task_id, session_id, enhanced_prompt):
                    if self._is_task_cancelled(task_id):
                        break
                    yield event
            else:
                async for event in self._execute_short_task(task_id, session_id, enhanced_prompt):
                    if self._is_task_cancelled(task_id):
                        break
                    yield event
            
            # 8. 保存会话记录
            if not self._is_task_cancelled(task_id):
                await self._save_conversation_turn(session_id, user_input, "Task completed")
                
                # 更新任务状态
                await self.task_store.update_task_status(task_id, TaskState.completed)
                yield TaskStatusUpdateEvent(
                    contextId=session_id,
                    taskId=task_id,
                    status=TaskStatus(state=TaskState.completed),
                    final=True
                )
                
        except TaskCancelledException:
            yield TaskStatusUpdateEvent(
                contextId=session_id,
                taskId=task_id,
                status=TaskStatus(state=TaskState.cancelled),
                final=True
            )
        except Exception as e:
            await self.task_store.update_task_status(task_id, TaskState.failed)
            yield A2AError(
                code=-32603,
                message=f"ISEK team execution failed: {str(e)}",
                data={"task_id": task_id}
            )
        finally:
            self.running_tasks.pop(task_id, None)
    
    async def cancel_async(self, context: dict) -> AsyncGenerator[Any, None]:
        """取消任务 - 遵循A2A最佳实践"""
        task_id = context["task_id"]
        if task_id in self.running_tasks:
            self.running_tasks[task_id]["cancelled"] = True
            await self.task_store.update_task_status(task_id, TaskState.cancelled)
            
            # 发送取消确认
            yield TaskStatusUpdateEvent(
                contextId=self.running_tasks[task_id]["session_id"],
                taskId=task_id,
                status=TaskStatus(state=TaskState.cancelled),
                final=True,
                metadata={"cancelled_at": datetime.now().isoformat()}
            )
        else:
            yield A2AError(
                code=-32602,
                message=f"Task {task_id} not found or already completed"
            )
    
    async def _manage_session_context(self, session_id: str, user_input: str) -> dict:
        """管理会话上下文"""
        session_context = self.session_manager.get_session_context(session_id)
        if not session_context:
            session_context = self.session_manager.create_session_context(session_id)
        self.session_manager.update_session_activity(session_id)
        
        # 获取对话历史
        conversation_history = self.session_manager.get_conversation_history(session_id)
        session_context["conversation_history"] = conversation_history
        
        return session_context
    
    async def _analyze_multiturn_requirement(self, user_input: str) -> dict:
        """分析是否需要多轮对话"""
        # 简化的多轮对话判断逻辑
        word_count = len(user_input.split())
        
        if word_count < 5:  # 输入太简短，需要更多信息
            return {
                "needs_more_info": True,
                "clarification_question": "I'd like to help you better. Could you provide more details about what you need?",
                "required_info": ["specific_goal", "context", "preferences"],
                "conversation_stage": "information_gathering"
            }
        elif "help" in user_input.lower() and word_count < 10:
            return {
                "needs_more_info": True,
                "clarification_question": "I'm here to help! What specific area do you need assistance with?",
                "required_info": ["topic", "specific_question"],
                "conversation_stage": "information_gathering"
            }
        else:
            return {"needs_more_info": False}
    
    async def _handle_conversation_continuation(
        self, task_id: str, session_id: str, user_input: str, session_context: dict
    ) -> AsyncGenerator[Any, None]:
        """处理多轮对话的延续"""
        conv_state = self.conversation_states.get(session_id, {})
        
        if conv_state.get("stage") == "collecting_info":
            async for event in self._handle_info_collection_continuation(
                task_id, session_id, user_input, conv_state
            ):
                yield event
        elif conv_state.get("stage") == "confirmation":
            async for event in self._handle_confirmation_continuation(
                task_id, session_id, user_input, conv_state
            ):
                yield event
        else:
            # 未知状态，重新开始
            async for event in self._handle_new_conversation(task_id, session_id, user_input):
                yield event
    
    async def _handle_info_collection_continuation(
        self, task_id: str, session_id: str, user_input: str, conv_state: dict
    ) -> AsyncGenerator[Any, None]:
        """处理信息收集阶段的延续"""
        # 记录收集到的信息
        current_question = conv_state.get("current_question")
        if current_question:
            conv_state["collected_info"][current_question] = user_input
        
        # 检查是否还需要更多信息
        remaining_info = [
            info for info in conv_state.get("required_info", [])
            if info not in conv_state.get("collected_info", {})
        ]
        
        if remaining_info:
            # 还需要更多信息
            next_question = remaining_info[0]
            conv_state["current_question"] = next_question
            
            yield new_agent_text_message(
                f"Thank you! Now, could you please provide information about: {next_question}?"
            )
            
            # 保持input-required状态
            yield TaskStatusUpdateEvent(
                contextId=session_id,
                taskId=task_id,
                status=TaskStatus(state=TaskState.working),  # Use working state as input-required is not a standard state
                final=False,
                metadata={
                    "conversation_stage": "information_gathering",
                    "progress": f"{len(conv_state.get('collected_info', {}))}/{len(conv_state.get('required_info', []))}"
                }
            )
        else:
            # 信息收集完成，进入确认阶段
            conv_state["stage"] = "confirmation"
            
            # 生成确认摘要
            summary = self._generate_info_summary(conv_state)
            yield new_agent_text_message(
                f"Perfect! I've collected all the information:\n{summary}\n\nShall I proceed with processing your request? (yes/no)"
            )
            
            # 等待确认
            yield TaskStatusUpdateEvent(
                contextId=session_id,
                taskId=task_id,
                status=TaskStatus(state=TaskState.working),
                final=False,
                metadata={"conversation_stage": "confirmation"}
            )
    
    async def _handle_confirmation_continuation(
        self, task_id: str, session_id: str, user_input: str, conv_state: dict
    ) -> AsyncGenerator[Any, None]:
        """处理确认阶段的延续"""
        user_response = user_input.lower().strip()
        
        if user_response in ["yes", "y", "proceed", "ok", "确认"]:
            # 用户确认，开始处理
            yield TaskStatusUpdateEvent(
                contextId=session_id,
                taskId=task_id,
                status=TaskStatus(state=TaskState.working),
                final=False
            )
            yield new_agent_text_message("Great! Processing your request now...")
            
            # 构建完整上下文并处理
            full_context = self._build_full_context(conv_state)
            async for event in self._execute_short_task(task_id, session_id, full_context):
                yield event
            
            # 清理会话状态
            self.conversation_states.pop(session_id, None)
            
        elif user_response in ["no", "n", "cancel", "stop", "取消"]:
            # 用户取消
            yield new_agent_text_message(
                "Understood. The request has been cancelled. Feel free to start over if needed."
            )
            yield TaskStatusUpdateEvent(
                contextId=session_id,
                taskId=task_id,
                status=TaskStatus(state=TaskState.cancelled),
                final=True
            )
            
            # 清理会话状态
            self.conversation_states.pop(session_id, None)
        else:
            # 无效响应，请求再次确认
            yield new_agent_text_message(
                "I didn't understand that. Please respond with 'yes' to proceed or 'no' to cancel."
            )
            
            # 保持确认状态
            yield TaskStatusUpdateEvent(
                contextId=session_id,
                taskId=task_id,
                status=TaskStatus(state=TaskState.working),
                final=False,
                metadata={"conversation_stage": "confirmation"}
            )
    
    async def _handle_new_conversation(
        self, task_id: str, session_id: str, user_input: str
    ) -> AsyncGenerator[Any, None]:
        """处理新对话开始"""
        multiturn_result = await self._analyze_multiturn_requirement(user_input)
        
        if multiturn_result["needs_more_info"]:
            # 需要更多信息，启动收集流程
            yield new_agent_text_message(multiturn_result["clarification_question"])
            
            # 创建等待输入的任务状态更新
            yield TaskStatusUpdateEvent(
                contextId=session_id,
                taskId=task_id,
                status=TaskStatus(state=TaskState.working),
                final=False,
                metadata={
                    "conversation_stage": "information_gathering",
                    "required_info": multiturn_result["required_info"],
                    "original_request": user_input
                }
            )
            
            # 保存会话状态
            self.conversation_states[session_id] = {
                "stage": "collecting_info",
                "original_request": user_input,
                "required_info": multiturn_result["required_info"],
                "collected_info": {},
                "current_question": multiturn_result["required_info"][0]
            }
        else:
            # 信息充足，直接处理
            async for event in self._execute_short_task(task_id, session_id, user_input):
                yield event
    
    async def _handle_multiturn_flow(
        self, task_id: str, session_id: str, multiturn_result: dict, session_context: dict
    ) -> AsyncGenerator[Any, None]:
        """处理多轮对话流程"""
        # 发送澄清问题
        yield new_agent_text_message(multiturn_result["clarification_question"])
        
        # 创建等待输入的任务状态更新
        yield TaskStatusUpdateEvent(
            contextId=session_id,
            taskId=task_id,
            status=TaskStatus(state=TaskState.working),
            final=False,
            metadata={
                "conversation_stage": "information_gathering",
                "required_info": multiturn_result["required_info"]
            }
        )
        
        # 保存会话状态
        self.conversation_states[session_id] = {
            "stage": "collecting_info",
            "original_request": session_context.get("user_input", ""),
            "required_info": multiturn_result["required_info"],
            "collected_info": {},
            "current_question": multiturn_result["required_info"][0]
        }
    
    def _build_contextual_prompt(self, user_input: str, session_context: dict) -> str:
        """构建带上下文的提示词"""
        session_id = session_context.get("session_id")
        if not session_id:
            return user_input
        
        # 使用SessionStore的上下文格式
        context_text = self.session_manager.get_conversation_context(session_id, limit=3)
        
        if context_text:
            return f"""Previous conversation context:
{context_text}

Current user input: {user_input}

Please respond considering the conversation history."""
        else:
            return user_input
    
    def _is_long_running_task(self, prompt: str) -> bool:
        """判断是否为长时间运行任务"""
        long_task_keywords = ["analyze", "process", "generate", "create", "build", "train", "complex"]
        return any(keyword in prompt.lower() for keyword in long_task_keywords)
    
    async def _execute_long_task(self, task_id: str, session_id: str, prompt: str) -> AsyncGenerator[Any, None]:
        """执行长时间任务，支持进度报告"""
        steps = [
            ("Understanding your request", 0.2, "Processing your input..."),
            ("Analyzing requirements", 0.4, "Breaking down the task..."),
            ("Generating response", 0.7, "Creating optimized content..."),
            ("Final review", 0.9, "Reviewing and polishing...")
        ]
        
        for i, (step_name, progress, message) in enumerate(steps):
            # 检查取消状态
            if self._is_task_cancelled(task_id):
                raise TaskCancelledException(f"Task {task_id} was cancelled")
            
            # 发送进度更新
            yield TaskStatusUpdateEvent(
                contextId=session_id,
                taskId=task_id,
                status=TaskStatus(state=TaskState.working),
                final=False,
                metadata={
                    "progress": progress,
                    "current_step": step_name,
                    "step_number": f"{i+1}/{len(steps)}"
                }
            )
            
            # 发送步骤消息
            yield new_agent_text_message(f"🔄 {message}")
            
            # 模拟工作时间
            await asyncio.sleep(0.5)
        
        # 执行实际的ISEK team处理
        if not self._is_task_cancelled(task_id):
            result = self.isek_team.run(
                message=prompt,
                user_id="default",
                session_id=session_id
            )
            
            # 保存对话记录
            self.session_manager.save_conversation_turn(session_id, prompt, result)
            
            yield new_agent_text_message(f"✅ Task completed:\n\n{result}")
    
    async def _execute_short_task(self, task_id: str, session_id: str, prompt: str) -> AsyncGenerator[Any, None]:
        """执行短任务 - 支持流式和非流式输出"""
        if self.enable_streaming:
            # 流式执行
            async for event in self._execute_streaming_task(task_id, session_id, prompt):
                yield event
        else:
            # 非流式执行
            result = self.isek_team.run(
                message=prompt,
                user_id="default", 
                session_id=session_id
            )
            
            # 保存对话记录
            self.session_manager.save_conversation_turn(session_id, prompt, result)
            
            yield new_agent_text_message(result)
    
    async def _execute_streaming_task(self, task_id: str, session_id: str, prompt: str) -> AsyncGenerator[Any, None]:
        """流式执行任务"""
        # 检查ISEK team是否支持流式输出
        if hasattr(self.isek_team, 'stream'):
            # 使用team的流式方法
            async for chunk in self.isek_team.stream(
                message=prompt,
                user_id="default",
                session_id=session_id
            ):
                yield new_agent_text_message(chunk)
                await asyncio.sleep(0.05)  # 控制流式速度
        else:
            # 模拟流式输出
            result = self.isek_team.run(
                message=prompt,
                user_id="default",
                session_id=session_id
            )
            
            # 按单词流式输出
            words = result.split()
            chunk_size = 5
            
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i:i + chunk_size])
                if i + chunk_size < len(words):
                    chunk += " "
                    
                yield new_agent_text_message(chunk)
                await asyncio.sleep(0.1)
        
        # 保存对话记录
        self.session_manager.save_conversation_turn(session_id, prompt, "streaming response")
    
    async def _save_conversation_turn(self, session_id: str, user_input: str, agent_response: str):
        """保存对话轮次"""
        self.session_manager.save_conversation_turn(session_id, user_input, agent_response)
    
    def _is_task_cancelled(self, task_id: str) -> bool:
        """检查任务是否被取消"""
        return self.running_tasks.get(task_id, {}).get("cancelled", False)
    
    def _generate_info_summary(self, conv_state: dict) -> str:
        """生成信息收集摘要"""
        summary_parts = []
        for info_type, value in conv_state.get("collected_info", {}).items():
            summary_parts.append(f"- {info_type}: {value}")
        return "\n".join(summary_parts)
    
    def _build_full_context(self, conv_state: dict) -> str:
        """构建完整的上下文"""
        original = conv_state.get("original_request", "")
        collected = conv_state.get("collected_info", {})
        
        context_parts = [f"Original request: {original}"]
        context_parts.append("Additional information:")
        
        for info_type, value in collected.items():
            context_parts.append(f"- {info_type}: {value}")
            
        return "\n".join(context_parts)
    
    def run(self, prompt: str, **kwargs) -> str:
        """同步执行方法（向后兼容）"""
        session_id = kwargs.get("session_id", "default")
        user_id = kwargs.get("user_id", "default")
        
        return self.isek_team.run(
            message=prompt,
            user_id=user_id,
            session_id=session_id
        )
    
    def get_adapter_card(self) -> AdapterCard:
        """获取adapter卡片信息"""
        # 获取team配置信息
        team_name = getattr(self.isek_team, 'name', 'ISEK Team')
        team_description = getattr(self.isek_team, 'description', 'AI agent team')
        
        return AdapterCard(
            name=team_name,
            bio=f"A2A-enhanced ISEK Team: {team_description}",
            lore=f"Enhanced with task management, session context, and multi-turn conversations",
            knowledge="Distributed AI agent knowledge with memory and context awareness",
            routine="Coordinate team members effectively with A2A protocol support"
        )
    
    def supports_streaming(self) -> bool:
        """是否支持流式响应"""
        return self.enable_streaming
    
    def supports_cancellation(self) -> bool:
        """是否支持任务取消"""
        return True
    
    def supports_multiturn(self) -> bool:
        """是否支持多轮对话"""
        return True
    
    def enable_streaming_mode(self, enabled: bool = True):
        """启用或禁用流式模式"""
        self.enable_streaming = enabled
    
    def get_streaming_status(self) -> bool:
        """获取当前流式模式状态"""
        return self.enable_streaming


