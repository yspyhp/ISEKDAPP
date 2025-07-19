from __future__ import annotations

from isek.adapter.base import Adapter, AdapterCard
from typing import Dict, Any, Optional
import json
import dotenv
from isek.utils.log import LoggerManager, log

# Import modular components
from modules import (
    BaseSessionManager, BaseTaskManager, BaseMessageHandler,
    DefaultSessionManager, DefaultTaskManager, DefaultMessageHandler
)

# Import shared message formats
from shared import create_agent_config, create_agent_response

LoggerManager.plain_mode()
dotenv.load_dotenv()


class SessionAdapter(Adapter):
    """
    Modular session adapter with pluggable components for session management,
    task management, and message handling
    """

    def __init__(self, 
                 session_manager: Optional[BaseSessionManager] = None,
                 task_manager: Optional[BaseTaskManager] = None,
                 message_handler: Optional[BaseMessageHandler] = None):
        """
        Initialize SessionAdapter with pluggable modules
        
        Args:
            session_manager: Session management module (defaults to DefaultSessionManager)
            task_manager: Task management module (defaults to DefaultTaskManager)  
            message_handler: Message handling module (defaults to DefaultMessageHandler)
        """
        self.session_manager = session_manager or DefaultSessionManager()
        self.task_manager = task_manager or DefaultTaskManager()
        self.message_handler = message_handler or DefaultMessageHandler()
        
        log.info("SessionAdapter initialized with modular components")

    def run(self, prompt: str, **kwargs) -> str:
        """
        Execute the adapter's main functionality with the given prompt.
        This is the main entry point for ISEK node communication.
        
        Args:
            prompt: The input message from client
            **kwargs: Additional keyword arguments
            
        Returns:
            str: The adapter's response
        """
        try:
            # Handle the message using the message handler
            return self._handle_message_sync(prompt)
        except Exception as e:
            log.error(f"Error in run method: {e}")
            return json.dumps({"success": False, "error": str(e)})

    def _handle_message_sync(self, message: str) -> str:
        """Synchronous wrapper for async message handling"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If event loop is already running, we need to create a new task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self._handle_message_async(message))
                    return future.result()
            else:
                return asyncio.run(self._handle_message_async(message))
        except Exception as e:
            log.error(f"Error in sync wrapper: {e}")
            return json.dumps({"success": False, "error": str(e)})

    async def _handle_message_async(self, message: str) -> str:
        """
        Handle incoming message from ISEK client
        Parse the message and route to appropriate handler
        """
        try:
            # Parse the incoming message
            parsed_data = self.message_handler.parse_message(message)
            
            if not parsed_data.get("success"):
                return self.message_handler.format_response({
                    "success": False, 
                    "error": "Failed to parse message"
                })
            
            message_type = self.message_handler.get_message_type(parsed_data)
            
            # Route to appropriate handler
            if message_type == "chat":
                response_data = await self.message_handler.handle_chat_message(parsed_data)
            elif message_type == "session_lifecycle":
                response_data = await self.message_handler.handle_session_lifecycle(parsed_data)
            elif message_type == "task":
                response_data = await self._handle_task_message(parsed_data)
            else:
                response_data = {
                    "success": False, 
                    "error": f"Unknown message type: {message_type}"
                }
            
            return self.message_handler.format_response(response_data)
                
        except Exception as e:
            log.error(f"Error handling message: {e}")
            return self.message_handler.format_response({
                "success": False, 
                "error": str(e)
            })

    async def _handle_task_message(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle task execution requests"""
        try:
            data = parsed_data["data"]
            task_type = data.get("task_type")
            task_data = data.get("task_data", {})
            
            if not task_type:
                return {"success": False, "error": "task_type is required"}
            
            if not self.task_manager.validate_task_data(task_type, task_data):
                return {"success": False, "error": "Invalid task data"}
            
            result = await self.task_manager.execute_task(task_type, task_data)
            return result
            
        except Exception as e:
            log.error(f"Error handling task message: {e}")
            return {"success": False, "error": str(e)}

    def get_adapter_card(self) -> AdapterCard:
        """
        Get metadata about the adapter for discovery and identification purposes.
        
        Returns:
            AdapterCard: A card containing adapter metadata compatible with client AgentConfig
        """
        return AdapterCard(
            name="Session Management Agent",
            bio="AI agent specialized in session and task management with modular architecture",
            lore="Born from the need to manage complex conversational sessions and coordinate various AI tasks",
            knowledge="Session management, task orchestration, message parsing, and multi-agent coordination",
            routine="Parse incoming messages, manage user sessions, coordinate task execution, and maintain conversation context"
        )
    
    def get_agent_config(self, node_id: str) -> Dict[str, Any]:
        """
        Get agent configuration in the format expected by client
        
        Args:
            node_id: The node ID (which serves as the address)
            
        Returns:
            Dict containing agent configuration matching client's AgentConfig format
        """
        adapter_card = self.get_adapter_card()
        
        return create_agent_config(
            node_id=node_id,
            name=adapter_card.name,
            description=adapter_card.bio,
            system_prompt=f"{adapter_card.knowledge}\n\nRoutine: {adapter_card.routine}",
            model="session-management-v1",
            capabilities=[
                "session_management",
                "task_execution", 
                "message_parsing",
                "team_formation",
                "data_analysis",
                "text_generation"
            ]
        )

    # Expose session management methods through the session manager
    def get_user_sessions(self, creator_id: str):
        """Get all sessions for a user"""
        return self.session_manager.get_user_sessions(creator_id)

    def get_session_by_id(self, session_id: str, creator_id: str):
        """Get a specific session by ID"""
        return self.session_manager.get_session_by_id(session_id, creator_id)

    def create_session(self, session):
        """Create a new session"""
        return self.session_manager.create_session(session)

    def delete_session(self, session_id: str, creator_id: str):
        """Delete a session"""
        return self.session_manager.delete_session(session_id, creator_id)

    def get_session_messages(self, session_id: str, creator_id: str):
        """Get all messages in a session"""
        return self.session_manager.get_session_messages(session_id, creator_id)

    def create_message(self, message, creator_id: str):
        """Create a new message in a session"""
        return self.session_manager.create_message(message, creator_id)

    # Expose task management methods
    def get_available_tasks(self):
        """Get list of available task types"""
        return self.task_manager.get_available_tasks()

    async def execute_task(self, task_type: str, task_data: Dict[str, Any]):
        """Execute a task"""
        return await self.task_manager.execute_task(task_type, task_data)
