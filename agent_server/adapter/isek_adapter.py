"""
Unified ISEK Team Adapter for A2A Protocol
A comprehensive adapter that integrates ISEK Team with Google's A2A (Agent-to-Agent) protocol.
Features include: task management, session management, multi-turn conversations, 
long-running task support, and streaming responses.
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
    Unified ISEK Adapter - Comprehensive business logic implementation
    
    This adapter provides a complete integration layer between ISEK Team and the A2A protocol,
    offering the following capabilities:
    
    - Task Management: Lifecycle tracking, progress reporting, cancellation support
    - Session Management: Conversation history, context awareness
    - Multi-turn Conversations: Information gathering, confirmation workflows
    - Long-running Tasks: Cancellable extended operations with progress updates
    - Streaming Responses: Real-time output support
    
    Follows Google A2A best practices for agent-to-agent communication.
    """
    
    def __init__(self, isek_team: IsekTeam, enable_streaming: bool = False):
        """
        Initialize the Unified ISEK Adapter
        
        Args:
            isek_team: The ISEK Team instance to be wrapped
            enable_streaming: Whether to enable streaming response mode
        """
        self.isek_team = isek_team
        self.enable_streaming = enable_streaming
        self.session_manager = SessionManager()
        self.task_store = EnhancedTaskStore()
        self.running_tasks = {}  # Track active tasks and their states
        self.conversation_states = {}  # Multi-turn conversation state management
    
    async def execute_async(self, context: dict) -> AsyncGenerator[Any, None]:
        """
        Asynchronously execute tasks and generate event streams
        
        This method implements the core execution logic following A2A best practices:
        1. Task lifecycle management
        2. Session context handling
        3. Multi-turn conversation processing
        4. Long vs short task routing
        5. Progress reporting and cancellation support
        
        Args:
            context: Dictionary containing task_id, session_id, user_input, and optional current_task
            
        Yields:
            A2A protocol events (TaskStatusUpdateEvent, agent messages, errors)
        """
        task_id = context["task_id"]
        session_id = context["session_id"]
        user_input = context["user_input"]
        current_task = context.get("current_task")
        
        try:
            # Step 1: Task Management - Create and track the task
            await self.task_store.create_task(task_id, session_id)
            self.running_tasks[task_id] = {
                "cancelled": False,
                "start_time": datetime.now(),
                "session_id": session_id
            }
            
            # Step 2: Send task start status event
            yield TaskStatusUpdateEvent(
                contextId=session_id,
                taskId=task_id,
                status=TaskStatus(state=TaskState.working),
                final=False,
                metadata={"started_at": datetime.now().isoformat()}
            )
            
            # Step 3: Session Management - Get and manage session context
            session_context = await self._manage_session_context(session_id, user_input)
            
            # Step 4: Multi-turn conversation handling
            if current_task and current_task.status in ["working", "input-required"]:
                # Handle continuation of existing multi-turn conversation
                async for event in self._handle_conversation_continuation(
                    task_id, session_id, user_input, session_context
                ):
                    if self._is_task_cancelled(task_id):
                        break
                    yield event
                return
            
            # Step 5: Analyze if multi-turn conversation is needed
            multiturn_result = await self._analyze_multiturn_requirement(user_input)
            
            if multiturn_result["needs_more_info"]:
                # Enter multi-turn conversation mode to gather more information
                async for event in self._handle_multiturn_flow(
                    task_id, session_id, multiturn_result, session_context
                ):
                    if self._is_task_cancelled(task_id):
                        break
                    yield event
                return
            
            # Step 6: Build enhanced contextual prompt
            enhanced_prompt = self._build_contextual_prompt(user_input, session_context)
            
            # Step 7: Long task support - Determine if this is a long-running task
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
            
            # Step 8: Save conversation record and complete task
            if not self._is_task_cancelled(task_id):
                await self._save_conversation_turn(session_id, user_input, "Task completed")
                
                # Update task status to completed
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
        """
        Manage session context and conversation history
        
        Args:
            session_id: Unique session identifier
            user_input: Current user input
            
        Returns:
            Dictionary containing session context and conversation history
        """
        session_context = self.session_manager.get_session_context(session_id)
        if not session_context:
            session_context = self.session_manager.create_session_context(session_id)
        self.session_manager.update_session_activity(session_id)
        
        # Retrieve conversation history for context
        conversation_history = self.session_manager.get_conversation_history(session_id)
        session_context["conversation_history"] = conversation_history
        
        return session_context
    
    async def _analyze_multiturn_requirement(self, user_input: str) -> dict:
        """
        Analyze whether the user input requires multi-turn conversation
        
        This method implements a simple heuristic to determine if more information
        is needed before processing the request.
        
        Args:
            user_input: The user's input text
            
        Returns:
            Dictionary indicating if multi-turn conversation is needed and what information to collect
        """
        # Simple multi-turn conversation detection logic
        word_count = len(user_input.split())
        
        if word_count < 5:  # Input too brief, need more information
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
        """
        Handle continuation of existing multi-turn conversations
        
        Routes the conversation to appropriate handlers based on current stage.
        
        Args:
            task_id: Current task identifier
            session_id: Session identifier
            user_input: User's response
            session_context: Current session context
            
        Yields:
            Events for conversation continuation
        """
        conv_state = self.conversation_states.get(session_id, {})
        
        if conv_state.get("stage") == "collecting_info":
            # Continue information gathering phase
            async for event in self._handle_info_collection_continuation(
                task_id, session_id, user_input, conv_state
            ):
                yield event
        elif conv_state.get("stage") == "confirmation":
            # Continue confirmation phase
            async for event in self._handle_confirmation_continuation(
                task_id, session_id, user_input, conv_state
            ):
                yield event
        else:
            # Unknown state, restart conversation
            async for event in self._handle_new_conversation(task_id, session_id, user_input):
                yield event
    
    async def _handle_info_collection_continuation(
        self, task_id: str, session_id: str, user_input: str, conv_state: dict
    ) -> AsyncGenerator[Any, None]:
        """
        Handle continuation of information gathering phase
        
        Records collected information and determines if more is needed.
        
        Args:
            task_id: Current task identifier
            session_id: Session identifier
            user_input: User's response to current question
            conv_state: Current conversation state
            
        Yields:
            Events for information collection continuation
        """
        # Record the collected information
        current_question = conv_state.get("current_question")
        if current_question:
            conv_state["collected_info"][current_question] = user_input
        
        # Check if more information is still needed
        remaining_info = [
            info for info in conv_state.get("required_info", [])
            if info not in conv_state.get("collected_info", {})
        ]
        
        if remaining_info:
            # More information needed, ask next question
            next_question = remaining_info[0]
            conv_state["current_question"] = next_question
            
            yield new_agent_text_message(
                f"Thank you! Now, could you please provide information about: {next_question}?"
            )
            
            # Maintain working state while waiting for input
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
            # Information collection complete, move to confirmation phase
            conv_state["stage"] = "confirmation"
            
            # Generate confirmation summary
            summary = self._generate_info_summary(conv_state)
            yield new_agent_text_message(
                f"Perfect! I've collected all the information:\n{summary}\n\nShall I proceed with processing your request? (yes/no)"
            )
            
            # Wait for confirmation
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
        """
        Handle continuation of confirmation phase
        
        Processes user's confirmation response and either proceeds with execution
        or cancels the request.
        
        Args:
            task_id: Current task identifier
            session_id: Session identifier
            user_input: User's confirmation response
            conv_state: Current conversation state
            
        Yields:
            Events for confirmation processing
        """
        user_response = user_input.lower().strip()
        
        if user_response in ["yes", "y", "proceed", "ok", "确认"]:
            # User confirmed, proceed with processing
            yield TaskStatusUpdateEvent(
                contextId=session_id,
                taskId=task_id,
                status=TaskStatus(state=TaskState.working),
                final=False
            )
            yield new_agent_text_message("Great! Processing your request now...")
            
            # Build full context and process
            full_context = self._build_full_context(conv_state)
            async for event in self._execute_short_task(task_id, session_id, full_context):
                yield event
            
            # Clean up conversation state
            self.conversation_states.pop(session_id, None)
            
        elif user_response in ["no", "n", "cancel", "stop", "取消"]:
            # User cancelled
            yield new_agent_text_message(
                "Understood. The request has been cancelled. Feel free to start over if needed."
            )
            yield TaskStatusUpdateEvent(
                contextId=session_id,
                taskId=task_id,
                status=TaskStatus(state=TaskState.cancelled),
                final=True
            )
            
            # Clean up conversation state
            self.conversation_states.pop(session_id, None)
        else:
            # Invalid response, ask for clarification
            yield new_agent_text_message(
                "I didn't understand that. Please respond with 'yes' to proceed or 'no' to cancel."
            )
            
            # Maintain confirmation state
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
        """
        Handle new conversation start
        
        Analyzes the initial user input and either starts information gathering
        or proceeds directly with execution.
        
        Args:
            task_id: Current task identifier
            session_id: Session identifier
            user_input: Initial user input
            
        Yields:
            Events for new conversation handling
        """
        multiturn_result = await self._analyze_multiturn_requirement(user_input)
        
        if multiturn_result["needs_more_info"]:
            # Need more information, start collection process
            yield new_agent_text_message(multiturn_result["clarification_question"])
            
            # Create task status update for waiting input
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
            
            # Save conversation state
            self.conversation_states[session_id] = {
                "stage": "collecting_info",
                "original_request": user_input,
                "required_info": multiturn_result["required_info"],
                "collected_info": {},
                "current_question": multiturn_result["required_info"][0]
            }
        else:
            # Sufficient information, process directly
            async for event in self._execute_short_task(task_id, session_id, user_input):
                yield event
    
    async def _handle_multiturn_flow(
        self, task_id: str, session_id: str, multiturn_result: dict, session_context: dict
    ) -> AsyncGenerator[Any, None]:
        """
        Handle multi-turn conversation flow
        
        Initiates the information gathering process when more details are needed.
        
        Args:
            task_id: Current task identifier
            session_id: Session identifier
            multiturn_result: Result from multi-turn analysis
            session_context: Current session context
            
        Yields:
            Events for multi-turn flow handling
        """
        # Send clarification question
        yield new_agent_text_message(multiturn_result["clarification_question"])
        
        # Create task status update for waiting input
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
        
        # Save conversation state
        self.conversation_states[session_id] = {
            "stage": "collecting_info",
            "original_request": session_context.get("user_input", ""),
            "required_info": multiturn_result["required_info"],
            "collected_info": {},
            "current_question": multiturn_result["required_info"][0]
        }
    
    def _build_contextual_prompt(self, user_input: str, session_context: dict) -> str:
        """
        Build contextual prompt with conversation history
        
        Enhances the user input with relevant conversation context to provide
        better continuity and understanding.
        
        Args:
            user_input: Current user input
            session_context: Session context containing conversation history
            
        Returns:
            Enhanced prompt with conversation context
        """
        session_id = session_context.get("session_id")
        if not session_id:
            return user_input
        
        # Use SessionStore context format
        context_text = self.session_manager.get_conversation_context(session_id, limit=3)
        
        if context_text:
            return f"""Previous conversation context:
{context_text}

Current user input: {user_input}

Please respond considering the conversation history."""
        else:
            return user_input
    
    def _is_long_running_task(self, prompt: str) -> bool:
        """
        Determine if the task is likely to be long-running
        
        Uses keyword analysis to identify tasks that might take significant time.
        
        Args:
            prompt: The task prompt to analyze
            
        Returns:
            True if task is likely to be long-running, False otherwise
        """
        long_task_keywords = ["analyze", "process", "generate", "create", "build", "train", "complex"]
        return any(keyword in prompt.lower() for keyword in long_task_keywords)
    
    async def _execute_long_task(self, task_id: str, session_id: str, prompt: str) -> AsyncGenerator[Any, None]:
        """
        Execute long-running tasks with progress reporting
        
        Provides step-by-step progress updates and handles cancellation gracefully.
        
        Args:
            task_id: Task identifier
            session_id: Session identifier
            prompt: Task prompt
            
        Yields:
            Progress events and final result
        """
        steps = [
            ("Understanding your request", 0.2, "Processing your input..."),
            ("Analyzing requirements", 0.4, "Breaking down the task..."),
            ("Generating response", 0.7, "Creating optimized content..."),
            ("Final review", 0.9, "Reviewing and polishing...")
        ]
        
        for i, (step_name, progress, message) in enumerate(steps):
            # Check cancellation status
            if self._is_task_cancelled(task_id):
                raise TaskCancelledException(f"Task {task_id} was cancelled")
            
            # Send progress update
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
            
            # Send step message
            yield new_agent_text_message(f"🔄 {message}")
            
            # Simulate work time
            await asyncio.sleep(0.5)
        
        # Execute actual ISEK team processing
        if not self._is_task_cancelled(task_id):
            result = self.isek_team.run(
                message=prompt,
                user_id="default",
                session_id=session_id
            )
            
            # Save conversation record
            self.session_manager.save_conversation_turn(session_id, prompt, result)
            
            yield new_agent_text_message(f"✅ Task completed:\n\n{result}")
    
    async def _execute_short_task(self, task_id: str, session_id: str, prompt: str) -> AsyncGenerator[Any, None]:
        """
        Execute short tasks with streaming and non-streaming support
        
        Handles both streaming and non-streaming execution modes based on configuration.
        
        Args:
            task_id: Task identifier
            session_id: Session identifier
            prompt: Task prompt
            
        Yields:
            Task execution events
        """
        if self.enable_streaming:
            # Streaming execution
            async for event in self._execute_streaming_task(task_id, session_id, prompt):
                yield event
        else:
            # Non-streaming execution - use asyncio to avoid blocking
            import asyncio
            
            # Run synchronous isek_team.run in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.isek_team.run(
                    message=prompt,
                    user_id="default", 
                    session_id=session_id
                )
            )
            
            # Save conversation record
            self.session_manager.save_conversation_turn(session_id, prompt, result)
            
            yield new_agent_text_message(result)
    
    async def _execute_streaming_task(self, task_id: str, session_id: str, prompt: str) -> AsyncGenerator[Any, None]:
        """
        Execute task with streaming response
        
        Provides real-time streaming output either using native streaming
        or simulated streaming by chunking the response.
        
        Args:
            task_id: Task identifier
            session_id: Session identifier
            prompt: Task prompt
            
        Yields:
            Streaming response chunks
        """
        # Check if ISEK team supports streaming output
        if hasattr(self.isek_team, 'stream'):
            # Use team's native streaming method
            async for chunk in self.isek_team.stream(
                message=prompt,
                user_id="default",
                session_id=session_id
            ):
                yield new_agent_text_message(chunk)
                await asyncio.sleep(0.05)  # Control streaming speed
        else:
            # Simulate streaming output
            result = self.isek_team.run(
                message=prompt,
                user_id="default",
                session_id=session_id
            )
            
            # Stream output by words
            words = result.split()
            chunk_size = 5
            
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i:i + chunk_size])
                if i + chunk_size < len(words):
                    chunk += " "
                    
                yield new_agent_text_message(chunk)
                await asyncio.sleep(0.1)
        
        # Save conversation record
        self.session_manager.save_conversation_turn(session_id, prompt, "streaming response")
    
    async def _save_conversation_turn(self, session_id: str, user_input: str, agent_response: str):
        """
        Save conversation turn to session history
        
        Args:
            session_id: Session identifier
            user_input: User's input
            agent_response: Agent's response
        """
        self.session_manager.save_conversation_turn(session_id, user_input, agent_response)
    
    def _is_task_cancelled(self, task_id: str) -> bool:
        """
        Check if a task has been cancelled
        
        Args:
            task_id: Task identifier to check
            
        Returns:
            True if task is cancelled, False otherwise
        """
        return self.running_tasks.get(task_id, {}).get("cancelled", False)
    
    def _generate_info_summary(self, conv_state: dict) -> str:
        """
        Generate summary of collected information
        
        Creates a formatted summary of all information collected during
        multi-turn conversation.
        
        Args:
            conv_state: Conversation state containing collected information
            
        Returns:
            Formatted summary string
        """
        summary_parts = []
        for info_type, value in conv_state.get("collected_info", {}).items():
            summary_parts.append(f"- {info_type}: {value}")
        return "\n".join(summary_parts)
    
    def _build_full_context(self, conv_state: dict) -> str:
        """
        Build complete context from conversation state
        
        Combines original request with collected information to create
        a comprehensive context for task execution.
        
        Args:
            conv_state: Conversation state with original request and collected info
            
        Returns:
            Complete context string
        """
        original = conv_state.get("original_request", "")
        collected = conv_state.get("collected_info", {})
        
        context_parts = [f"Original request: {original}"]
        context_parts.append("Additional information:")
        
        for info_type, value in collected.items():
            context_parts.append(f"- {info_type}: {value}")
            
        return "\n".join(context_parts)
    
    def run(self, prompt: str, **kwargs) -> str:
        """
        Synchronous execution method (backward compatibility)
        
        Provides a simple synchronous interface for basic task execution.
        
        Args:
            prompt: Task prompt
            **kwargs: Additional arguments including session_id and user_id
            
        Returns:
            Task execution result as string
        """
        session_id = kwargs.get("session_id", "default")
        user_id = kwargs.get("user_id", "default")
        
        return self.isek_team.run(
            message=prompt,
            user_id=user_id,
            session_id=session_id
        )
    
    def get_adapter_card(self) -> AdapterCard:
        """
        Get adapter card information
        
        Returns metadata about this adapter for discovery and integration.
        
        Returns:
            AdapterCard with adapter metadata
        """
        # Get team configuration information
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
        """
        Check if streaming responses are supported
        
        Returns:
            True if streaming is enabled, False otherwise
        """
        return self.enable_streaming
    
    def supports_cancellation(self) -> bool:
        """
        Check if task cancellation is supported
        
        Returns:
            True (this adapter supports cancellation)
        """
        return True
    
    def supports_multiturn(self) -> bool:
        """
        Check if multi-turn conversations are supported
        
        Returns:
            True (this adapter supports multi-turn conversations)
        """
        return True
    
    def enable_streaming_mode(self, enabled: bool = True):
        """
        Enable or disable streaming mode
        
        Args:
            enabled: Whether to enable streaming mode
        """
        self.enable_streaming = enabled
    
    def get_streaming_status(self) -> bool:
        """
        Get current streaming mode status
        
        Returns:
            Current streaming mode status
        """
        return self.enable_streaming


