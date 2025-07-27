"""
A2A Protocol Implementation
A2A protocol implementation - Following Google A2A best practices, AgentExecutor only handles run/cancel, complex logic is handled in the adapter layer
"""

import asyncio
from typing import Any, Optional, Dict
from uuid import uuid4
from datetime import datetime
import threading
import time
import os
import subprocess
import json
import atexit
import urllib

import httpx
import uvicorn
from a2a.client import A2AClient
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.apps.jsonrpc import JSONRPCApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard, AgentCapabilities
from a2a.types import MessageSendParams, SendMessageRequest
from a2a.types import A2AError
from a2a.utils import new_agent_text_message

from isek.protocol.protocol import Protocol
from isek.adapter.base import Adapter
from isek.adapter.simple_adapter import SimpleAdapter
from adapter.isek_adapter import UnifiedIsekAdapter
from isek.utils.log import log


class A2ACompliantAgentExecutor(AgentExecutor):
    """
    A2A Compliant Agent Executor - Only handles run/cancel, contains no business logic
    All complex logic (task management, session management, multi-turn conversations, etc.) is handled in the adapter layer
    Following Google A2A best practices
    """
    
    def __init__(self, url: str, adapter: Adapter):
        self.url = url
        self.adapter = adapter

    def get_a2a_agent_card(self) -> AgentCard:
        """Get A2A agent card information"""
        adapter_card = self.adapter.get_adapter_card()
        return AgentCard(
            name=adapter_card.name,
            description=f"A2A-enabled: {adapter_card.bio}",
            url=self.url,
            version="5.0.0",  # Upgrade version number
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            capabilities=AgentCapabilities(
                streaming=getattr(self.adapter, 'supports_streaming', lambda: False)(),
                multiturn=getattr(self.adapter, 'supports_multiturn', lambda: False)(),
                longRunningTasks=getattr(self.adapter, 'supports_cancellation', lambda: False)()
            ),
            skills=getattr(adapter_card, 'skills', []),
        )

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """
        Execute task - Only responsible for calling adapter.run(), contains no business logic
        Following A2A best practices: AgentExecutor doesn't handle logic, handled through adapter
        """
        try:
            # Build adapter context
            adapter_context = self._build_adapter_context(context)
            
            # Check if using enhanced adapter
            # Use unified adapter for all processing
            async for event in self.adapter.execute_async(adapter_context):
                await event_queue.enqueue_event(event)
                
        except Exception as e:
            # Minimal exception handling
            await event_queue.enqueue_event(A2AError(
                code=-32603,
                message=f"Executor failed: {str(e)}",
                data={"task_id": context.task_id}
            ))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """
        Cancel task - Only responsible for calling adapter.cancel(), contains no business logic
        Following A2A best practices: AgentExecutor doesn't handle logic, handled through adapter
        """
        try:
            # Build adapter context
            adapter_context = self._build_adapter_context(context)
            
            # Check if adapter supports async cancellation
            # Unified adapter supports cancellation
            async for event in self.adapter.cancel_async(adapter_context):
                await event_queue.enqueue_event(event)
                
        except Exception as e:
            # Minimal exception handling
            await event_queue.enqueue_event(A2AError(
                code=-32603,
                message=f"Cancel failed: {str(e)}"
            ))
    
    def _build_adapter_context(self, context: RequestContext) -> dict:
        """Build context passed to adapter - only data conversion"""
        return {
            "task_id": context.task_id,
            "session_id": context.context_id,
            "user_input": context.get_user_input(),
            "message": context.message,
            "current_task": context.current_task
        }


def build_send_message_request(sender_node_id, message):
    """Build P2P message request"""
    send_message_payload: dict[str, Any] = {
        "message": {
            "role": "user",
            "parts": [{"kind": "text", "text": message}],
            "messageId": uuid4().hex,
            "metadata": {"sender_node_id": sender_node_id},
        },
        "metadata": {"sender_node_id": sender_node_id},
    }
    return SendMessageRequest(
        id=str(uuid4()), params=MessageSendParams(**send_message_payload)
    )


def build_task_request(sender_node_id, task_id: str, action: str, **kwargs):
    """Build P2P task request (get_task, cancel_task, etc.)"""
    task_payload: dict[str, Any] = {
        "action": action,
        "task_id": task_id,
        "sender_node_id": sender_node_id,
        "metadata": kwargs.get("metadata", {}),
        "timestamp": datetime.now().isoformat()
    }
    
    if kwargs:
        task_payload.update(kwargs)
    
    return {
        "id": str(uuid4()),
        "method": f"a2a.task.{action}",
        "params": task_payload
    }


class A2AProtocol(Protocol):
    """
    A2A Protocol Implementation - Following Google A2A best practices
    - AgentExecutor only handles run/cancel
    - Complex logic handled in adapter layer
    - Supports task management, session management, multi-turn conversations
    """
    
    def __init__(
        self,
        a2a_application: Optional[JSONRPCApplication] = None,
        host: str = "localhost",
        port: int = 8080,
        p2p: bool = True,
        p2p_server_port: int = 9000,
        adapter: Optional[Adapter] = None,
        enable_long_tasks: bool = False,
        enable_enhanced_features: bool = True,
        **kwargs: Any,
    ):
        super().__init__(
            host=host,
            port=port,
            adapter=adapter,
            p2p=p2p,
            p2p_server_port=p2p_server_port,
            **kwargs,
        )
        self.adapter = adapter or SimpleAdapter()
        self.enable_long_tasks = enable_long_tasks
        self.enable_enhanced_features = enable_enhanced_features
        self.peer_id = None
        self.p2p_address = None
        
        if a2a_application:
            self.url = a2a_application.agent_card.url
            self.a2a_application = a2a_application
        else:
            self.url = f"http://{host}:{port}/"
            self.a2a_application = self.build_a2a_application()

    def bootstrap_server(self):
        """Start A2A server"""
        uvicorn.run(self.a2a_application.build(), host="0.0.0.0", port=self.port)

    def bootstrap_p2p_extension(self):
        """Start P2P extension"""
        if self.p2p and self.p2p_server_port:
            self.__bootstrap_p2p_server()

    def __bootstrap_p2p_server(self):
        """Start P2P server"""
        def stream_output(stream):
            for line in iter(stream.readline, ""):
                log.debug(line)

        dirc = os.path.dirname(__file__)
        p2p_file_path = os.path.join(dirc, "p2p", "p2p_server.js")
        process = subprocess.Popen(
            [
                "node",
                p2p_file_path,
                f"--port={self.p2p_server_port}",
                f"--agent_port={self.port}",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        def cleanup():
            if process and process.poll() is None:
                process.terminate()
            log.debug(f"p2p_server[port:{self.p2p_server_port}] process terminated")

        atexit.register(cleanup)
        thread = threading.Thread(
            target=stream_output, args=(process.stdout,), daemon=True
        )
        thread.start()
        while True:
            if process.poll() is not None:
                raise RuntimeError(
                    f"p2p_server process exited unexpectedly with code {process.returncode}"
                )

            p2p_context = self.__load_p2p_context()
            if p2p_context and self.peer_id and self.p2p_address:
                log.debug(f"The p2p service has been completed: {p2p_context}")
                break
            time.sleep(1)

    def __load_p2p_context(self):
        """Load P2P context"""
        try:
            response = httpx.get(f"http://localhost:{self.p2p_server_port}/p2p_context")
            response_body = json.loads(response.content)
            self.peer_id = response_body["peer_id"]
            self.p2p_address = response_body["p2p_address"]
            log.debug(f"__load_p2p_context response[{response_body}]")
            return response_body
        except Exception:
            log.exception("Load p2p server context error.")
            return None

    def stop_server(self) -> None:
        """Stop server"""
        pass

    # ============ 统一P2P转发核心方法 ============
    
    def _forward_to_p2p(self, p2p_address: str, json_rpc_request: dict) -> dict:
        """统一的P2P转发方法 - 可以转发任何JSON-RPC请求"""
        try:
            response = httpx.post(
                url=f"http://localhost:{self.p2p_server_port}/call_peer?p2p_address={urllib.parse.quote(p2p_address)}",
                json=json_rpc_request,
                headers={"Content-Type": "application/json"},
                timeout=60,
            )
            return response.json()
        except Exception as e:
            log.error(f"P2P forward failed: {e}")
            return {"error": str(e)}
    
    async def _forward_to_p2p_async(self, p2p_address: str, json_rpc_request: dict) -> dict:
        """异步P2P转发方法"""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    url=f"http://localhost:{self.p2p_server_port}/call_peer?p2p_address={urllib.parse.quote(p2p_address)}",
                    json=json_rpc_request,
                    headers={"Content-Type": "application/json"}
                )
                return response.json()
        except Exception as e:
            log.error(f"Async P2P forward failed: {e}")
            return {"error": str(e)}

    # ============ 消息发送方法 (简化版) ============
    
    def send_p2p_message(self, sender_node_id: str, p2p_address: str, message: str) -> str:
        """发送P2P消息 - 使用统一转发"""
        request = build_send_message_request(sender_node_id, message)
        request_body = request.model_dump(mode="json", exclude_none=True)
        response = self._forward_to_p2p(p2p_address, request_body)
        
        if "error" in response:
            raise Exception(f"P2P message send failed: {response['error']}")
        return response["result"]["parts"][0]["text"]

    async def send_p2p_message_async(self, sender_node_id: str, p2p_address: str, message: str) -> str:
        """异步发送P2P消息 - 使用统一转发"""
        request = build_send_message_request(sender_node_id, message)
        request_body = request.model_dump(mode="json", exclude_none=True)
        response = await self._forward_to_p2p_async(p2p_address, request_body)
        
        if "error" in response:
            raise Exception(f"Async P2P message send failed: {response['error']}")
        return response["result"]["parts"][0]["text"]

    def send_message(self, sender_node_id: str, target_address: str, message: str) -> str:
        """发送A2A消息 - HTTP版本"""
        request = build_send_message_request(sender_node_id, message)
        request_body = request.model_dump(mode="json", exclude_none=True)
        
        response = httpx.post(
            url=target_address,
            json=request_body,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
        response_data = response.json()
        return response_data["result"]["parts"][0]["text"]

    async def send_message_async(self, sender_node_id: str, target_address: str, message: str) -> str:
        """异步发送A2A消息 - HTTP版本"""
        request = build_send_message_request(sender_node_id, message)
        request_body = request.model_dump(mode="json", exclude_none=True)
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                url=target_address,
                json=request_body,
                headers={"Content-Type": "application/json"}
            )
            response_data = response.json()
            return response_data["result"]["parts"][0]["text"]

    # ============ 任务操作方法 (简化版) ============
    
    def get_task_p2p(self, sender_node_id: str, p2p_address: str, task_id: str, **kwargs) -> Dict[str, Any]:
        """P2P获取任务状态 - 使用统一转发"""
        task_request = build_task_request(sender_node_id, task_id, "get_task", **kwargs)
        response = self._forward_to_p2p(p2p_address, task_request)
        
        if "error" in response:
            return {"error": response["error"], "task_id": task_id, "status": "error"}
        return response.get("result", response)

    async def get_task_p2p_async(self, sender_node_id: str, p2p_address: str, task_id: str, **kwargs) -> Dict[str, Any]:
        """异步P2P获取任务状态 - 使用统一转发"""
        task_request = build_task_request(sender_node_id, task_id, "get_task", **kwargs)
        response = await self._forward_to_p2p_async(p2p_address, task_request)
        
        if "error" in response:
            return {"error": response["error"], "task_id": task_id, "status": "error"}
        return response.get("result", response)

    def cancel_task_p2p(self, sender_node_id: str, p2p_address: str, task_id: str, **kwargs) -> Dict[str, Any]:
        """P2P取消任务 - 使用统一转发"""
        task_request = build_task_request(sender_node_id, task_id, "cancel_task", **kwargs)
        response = self._forward_to_p2p(p2p_address, task_request)
        
        if "error" in response:
            return {"error": response["error"], "task_id": task_id, "status": "cancel_failed"}
        return response.get("result", response)

    async def cancel_task_p2p_async(self, sender_node_id: str, p2p_address: str, task_id: str, **kwargs) -> Dict[str, Any]:
        """异步P2P取消任务 - 使用统一转发"""
        task_request = build_task_request(sender_node_id, task_id, "cancel_task", **kwargs)
        response = await self._forward_to_p2p_async(p2p_address, task_request)
        
        if "error" in response:
            return {"error": response["error"], "task_id": task_id, "status": "cancel_failed"}
        return response.get("result", response)

    def get_task(self, sender_node_id: str, target_address: str, task_id: str, **kwargs) -> Dict[str, Any]:
        """Direct A2A get task status"""
        try:
            task_request = build_task_request(sender_node_id, task_id, "get_task", **kwargs)
            
            response = httpx.post(
                url=f"{target_address}/a2a/task/get",
                json=task_request,
                headers={"Content-Type": "application/json"},
                timeout=60,
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "task_id": task_id,
                    "status": "error"
                }
                
        except Exception as e:
            log.error(f"A2A get_task failed for task {task_id}: {str(e)}")
            return {
                "error": str(e),
                "task_id": task_id,
                "status": "error"
            }

    def cancel_task(self, sender_node_id: str, target_address: str, task_id: str, **kwargs) -> Dict[str, Any]:
        """Direct A2A cancel task"""
        try:
            task_request = build_task_request(sender_node_id, task_id, "cancel_task", **kwargs)
            
            response = httpx.post(
                url=f"{target_address}/a2a/task/cancel",
                json=task_request,
                headers={"Content-Type": "application/json"},
                timeout=60,
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "task_id": task_id,
                    "status": "cancel_failed"
                }
                
        except Exception as e:
            log.error(f"A2A cancel_task failed for task {task_id}: {str(e)}")
            return {
                "error": str(e),
                "task_id": task_id,
                "status": "cancel_failed"
            }

    def build_a2a_application(self) -> JSONRPCApplication:
        """Build A2A application - Following Google A2A best practices"""
        if not self.adapter or not isinstance(self.adapter, Adapter):
            raise ValueError("A Adapter must be provided to the A2AProtocol.")
        
        return self._build_enhanced_a2a_application()

    def _build_enhanced_a2a_application(self) -> JSONRPCApplication:
        """
        Build enhanced A2A application - Complex logic in adapter layer
        Following Google A2A best practices: AgentExecutor only handles run/cancel
        """
        # Use unified enhanced adapter
        # Use the unified adapter directly
        enhanced_adapter = self.adapter
        log.info("Using UnifiedIsekAdapter with complete A2A features")
        
        # Use A2A compliant protocol layer executor - only handles run/cancel
        agent_executor = A2ACompliantAgentExecutor(self.url, enhanced_adapter)
        
        # Use standard task store (complex task management in adapter)
        request_handler = DefaultRequestHandler(
            agent_executor=agent_executor,
            task_store=InMemoryTaskStore(),
        )

        return A2AStarletteApplication(
            agent_card=agent_executor.get_a2a_agent_card(),
            http_handler=request_handler,
        )

    def enable_enhanced_features(
        self, 
        enable_long_tasks: bool = True,
        enable_enhanced_features: bool = True
    ):
        """Dynamically enable enhanced features"""
        self.enable_long_tasks = enable_long_tasks
        self.enable_enhanced_features = enable_enhanced_features
        
        # Rebuild application
        self.a2a_application = self.build_a2a_application()
        log.info("Enhanced A2A features enabled")

    def get_task_progress(self, task_id: str) -> Optional[dict]:
        """Get local task progress (from adapter)"""
        try:
            adapter = self.a2a_application.http_handler.agent_executor.adapter
            if hasattr(adapter, 'task_store'):
                return adapter.task_store.get_task_progress(task_id)
            return None
        except Exception as e:
            log.error(f"Failed to get local task progress for {task_id}: {str(e)}")
            return None

    def get_session_info(self, context_id: str) -> Optional[dict]:
        """Get local session info (from adapter)"""
        try:
            adapter = self.a2a_application.http_handler.agent_executor.adapter
            if hasattr(adapter, 'session_manager'):
                return adapter.session_manager.get_session_summary(context_id)
            return None
        except Exception as e:
            log.error(f"Failed to get local session info for {context_id}: {str(e)}")
            return None
    
