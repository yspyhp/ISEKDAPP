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
    Session-aware adapter with plugin support.
    Drop-in replacement for IsekAdapter with session management capabilities.
    """

    def __init__(self, 
                 agent=None,
                 session_manager: Optional[BaseSessionManager] = None,
                 task_manager: Optional[BaseTaskManager] = None,
                 message_handler: Optional[BaseMessageHandler] = None):
        self.agent = agent
        self.session_manager = session_manager
        self.task_manager = task_manager 
        self.message_handler = message_handler or DefaultMessageHandler()
        
        log.info(f"SessionAdapter initialized: agent={type(agent).__name__ if agent else None}, "
                f"plugins=[{', '.join([p for p in ['session', 'task'] if getattr(self, f'{p}_manager')])}]")

    def run(self, prompt: str, **kwargs) -> str:
        try:
            parsed_data = self.message_handler.parse_message(prompt)
            if not parsed_data.get("success"):
                return self._error_response("Failed to parse message")
            
            message_type = self.message_handler.get_message_type(parsed_data)
            
            if self.session_manager or self.task_manager:
                return self._process_with_plugins(prompt, message_type, parsed_data)
            else:
                return self._process_simple(prompt, message_type, parsed_data)
                
        except Exception as e:
            log.error(f"Adapter error: {e}")
            return self._error_response(str(e))

    def _process_simple(self, prompt: str, message_type: str, parsed_data: Dict[str, Any]) -> str:
        if message_type == "chat":
            return self._team_run(prompt)
        elif message_type == "agent_config_request":
            return self._agent_config(parsed_data)
        else:
            return self._error_response(f"Type '{message_type}' requires plugins")

    def _process_with_plugins(self, prompt: str, message_type: str, parsed_data: Dict[str, Any]) -> str:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, 
                        self._plugin_chain(prompt, message_type, parsed_data)
                    )
                    return future.result()
            else:
                return asyncio.run(self._plugin_chain(prompt, message_type, parsed_data))
        except Exception as e:
            log.error(f"Plugin processing error: {e}")
            return self._error_response(str(e))

    async def _plugin_chain(self, prompt: str, message_type: str, parsed_data: Dict[str, Any]) -> str:
        try:
            if self.session_manager:
                if message_type in ["chat", "session_lifecycle"]:
                    if message_type == "chat":
                        if hasattr(self.message_handler, 'set_agent_runner'):
                            self.message_handler.set_agent_runner(self._team_run)
                        if hasattr(self.message_handler, 'set_session_manager'):
                            self.message_handler.set_session_manager(self.session_manager)
                        response_data = await self.message_handler.handle_chat_message(parsed_data)
                    else:
                        response_data = await self._handle_session_lifecycle(parsed_data)
                    return self.message_handler.format_response(response_data)
            
            if message_type == "task" and self.task_manager:
                response_data = await self._handle_task_message(parsed_data)
                return self.message_handler.format_response(response_data)
            
            if message_type == "chat":
                return self._team_run(prompt)
            elif message_type == "agent_config_request":
                response_data = await self._handle_agent_config_request(parsed_data)
                return self.message_handler.format_response(response_data)
            
            return self._error_response(f"Unsupported message type: {message_type}")
            
        except Exception as e:
            log.error(f"Plugin chain error: {e}")
            return self._error_response(str(e))

    def _team_run(self, prompt: str) -> str:
        if self.agent and hasattr(self.agent, 'run'):
            return self.agent.run(prompt)
        else:
            return self.message_handler.format_response(
                create_agent_response(success=True, content=f"Echo: {prompt}")
            )

    def _agent_config(self, parsed_data: Dict[str, Any]) -> str:
        data = parsed_data["data"]
        node_id = data.get("node_id")
        if not node_id:
            return self._error_response("node_id required")
        
        config = self.get_agent_config(node_id)
        response = create_agent_response(success=True, content=json.dumps(config), **config)
        return self.message_handler.format_response(response)

    def _error_response(self, error: str) -> str:
        response = create_agent_response(success=False, error=error)
        return self.message_handler.format_response(response)


    async def _handle_session_lifecycle(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            data = parsed_data["data"]
            action = data.get("action", "")
            session_id = data.get("session_id", "")
            user_id = data.get("user_id", "")
            request_id = data.get("request_id", "")
            
            log.info(f"Session lifecycle event: {action} for session {session_id} from user {user_id}")
            
            return create_agent_response(
                success=True,
                content=f"Session {action} processed",
                request_id=request_id
            )
            
        except Exception as e:
            log.error(f"Error handling session lifecycle: {e}")
            return create_agent_response(success=False, error=str(e))

    async def _handle_task_message(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
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

    async def _handle_agent_config_request(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            data = parsed_data["data"]
            node_id = data.get("node_id")
            
            if not node_id:
                return {"success": False, "error": "node_id is required"}
            
            agent_config = self.get_agent_config(node_id)
            
            return {
                "success": True,
                "content": json.dumps(agent_config),
                **agent_config
            }
            
        except Exception as e:
            log.error(f"Error handling agent config request: {e}")
            return {"success": False, "error": str(e)}

    def get_adapter_card(self) -> AdapterCard:
        if self.agent and hasattr(self.agent, 'get_adapter_card'):
            agent_card = self.agent.get_adapter_card()
            return AdapterCard(
                name=f"{agent_card.name} (Session-Enabled)" if agent_card.name else "Session-Enabled Agent",
                bio=agent_card.bio or "Agent with session management capabilities",
                lore=agent_card.lore or "Enhanced with session and task management",
                knowledge=agent_card.knowledge or "Session management, task orchestration",
                routine=agent_card.routine or "Process messages with session context"
            )
        elif self.agent and hasattr(self.agent, 'name'):
            return AdapterCard(
                name=f"{self.agent.name} (Session-Enabled)",
                bio="Agent with session management capabilities",
                lore="Enhanced with session and task management",
                knowledge="Session management, task orchestration",
                routine="Process messages with session context"
            )
        else:
            return AdapterCard(
                name="Session Management Agent",
                bio="AI agent specialized in session and task management",
                lore="Provides session context and task orchestration for agent teams",
                knowledge="Session management, task orchestration, message parsing",
                routine="Parse messages, manage sessions, coordinate tasks, and process through agent teams"
            )
    
    def get_agent_config(self, node_id: str) -> Dict[str, Any]:
        adapter_card = self.get_adapter_card()
        return {
            "name": adapter_card.name,
            "node_id": node_id,
            "bio": adapter_card.bio,
            "lore": adapter_card.lore,
            "knowledge": adapter_card.knowledge,
            "routine": adapter_card.routine
        }

    def __getattr__(self, name: str):
        if self.session_manager and hasattr(self.session_manager, name):
            return getattr(self.session_manager, name)
        if self.task_manager and hasattr(self.task_manager, name):
            return getattr(self.task_manager, name)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
