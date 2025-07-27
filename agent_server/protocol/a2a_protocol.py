"""
A2A Protocol Implementation
A2A协议实现 - 遵循Google A2A最佳实践，AgentExecutor只负责run/cancel，复杂逻辑在adapter层
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
    A2A合规的Agent Executor - 只负责run/cancel，不包含任何业务逻辑
    所有复杂逻辑（任务管理、会话管理、多轮对话等）都在Adapter层处理
    遵循Google A2A最佳实践
    """
    
    def __init__(self, url: str, adapter: Adapter):
        self.url = url
        self.adapter = adapter

    def get_a2a_agent_card(self) -> AgentCard:
        """获取A2A代理卡片信息"""
        adapter_card = self.adapter.get_adapter_card()
        return AgentCard(
            name=adapter_card.name,
            description=f"A2A-enabled: {adapter_card.bio}",
            url=self.url,
            version="5.0.0",  # 升级版本号
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
        执行任务 - 仅负责调用adapter.run()，不包含业务逻辑
        遵循A2A最佳实践：AgentExecutor不处理逻辑，通过adapter处理
        """
        try:
            # 构建adapter上下文
            adapter_context = self._build_adapter_context(context)
            
            # 检查是否使用增强adapter
            # 使用统一adapter进行所有处理
            async for event in self.adapter.execute_async(adapter_context):
                await event_queue.enqueue_event(event)
                
        except Exception as e:
            # 最小化的异常处理
            await event_queue.enqueue_event(A2AError(
                code=-32603,
                message=f"Executor failed: {str(e)}",
                data={"task_id": context.task_id}
            ))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """
        取消任务 - 仅负责调用adapter.cancel()，不包含业务逻辑
        遵循A2A最佳实践：AgentExecutor不处理逻辑，通过adapter处理
        """
        try:
            # 构建adapter上下文
            adapter_context = self._build_adapter_context(context)
            
            # 检查adapter是否支持异步取消
            # 统一adapter支持取消
            async for event in self.adapter.cancel_async(adapter_context):
                await event_queue.enqueue_event(event)
                
        except Exception as e:
            # 最小化的异常处理
            await event_queue.enqueue_event(A2AError(
                code=-32603,
                message=f"Cancel failed: {str(e)}"
            ))
    
    def _build_adapter_context(self, context: RequestContext) -> dict:
        """构建传递给adapter的上下文 - 只做数据转换"""
        return {
            "task_id": context.task_id,
            "session_id": context.context_id,
            "user_input": context.get_user_input(),
            "message": context.message,
            "current_task": context.current_task
        }


def build_send_message_request(sender_node_id, message):
    """构建P2P消息请求"""
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
    """构建P2P任务请求（get_task, cancel_task等）"""
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
    A2A协议实现 - 遵循Google A2A最佳实践
    - AgentExecutor只负责run/cancel
    - 复杂逻辑在adapter层处理
    - 支持任务管理、会话管理、多轮对话
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
        """启动A2A服务器"""
        uvicorn.run(self.a2a_application.build(), host="0.0.0.0", port=self.port)

    def bootstrap_p2p_extension(self):
        """启动P2P扩展"""
        if self.p2p and self.p2p_server_port:
            self.__bootstrap_p2p_server()

    def __bootstrap_p2p_server(self):
        """启动P2P服务器"""
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
        """加载P2P上下文"""
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
        """停止服务器"""
        pass

    def send_p2p_message(self, sender_node_id, p2p_address, message):
        """发送P2P消息"""
        request = build_send_message_request(sender_node_id, message)
        request_body = request.model_dump(mode="json", exclude_none=True)
        response = httpx.post(
            url=f"http://localhost:{self.p2p_server_port}/call_peer?p2p_address={urllib.parse.quote(p2p_address)}",
            json=request_body,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
        response_body = json.loads(response.content)
        return response_body["result"]["parts"][0]["text"]

    def send_message(self, sender_node_id, target_address, message):
        """发送A2A消息"""
        httpx_client = httpx.AsyncClient(timeout=60)
        client = A2AClient(httpx_client=httpx_client, url=target_address)
        request = build_send_message_request(sender_node_id, message)
        response = asyncio.run(client.send_message(request))
        return response.model_dump(mode="json", exclude_none=True)["result"]["parts"][0]["text"]

    def get_task_p2p(self, sender_node_id: str, p2p_address: str, task_id: str, **kwargs) -> Dict[str, Any]:
        """P2P获取任务状态"""
        try:
            task_request = build_task_request(sender_node_id, task_id, "get_task", **kwargs)
            
            response = httpx.post(
                url=f"http://localhost:{self.p2p_server_port}/call_peer?p2p_address={urllib.parse.quote(p2p_address)}",
                json=task_request,
                headers={"Content-Type": "application/json"},
                timeout=60,
            )
            
            if response.status_code == 200:
                response_body = json.loads(response.content)
                return response_body.get("result", {})
            else:
                return {
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "task_id": task_id,
                    "status": "error"
                }
                
        except Exception as e:
            log.error(f"P2P get_task failed for task {task_id}: {str(e)}")
            return {
                "error": str(e),
                "task_id": task_id,
                "status": "error"
            }

    def cancel_task_p2p(self, sender_node_id: str, p2p_address: str, task_id: str, **kwargs) -> Dict[str, Any]:
        """P2P取消任务"""
        try:
            task_request = build_task_request(sender_node_id, task_id, "cancel_task", **kwargs)
            
            response = httpx.post(
                url=f"http://localhost:{self.p2p_server_port}/call_peer?p2p_address={urllib.parse.quote(p2p_address)}",
                json=task_request,
                headers={"Content-Type": "application/json"},
                timeout=60,
            )
            
            if response.status_code == 200:
                response_body = json.loads(response.content)
                return response_body.get("result", {})
            else:
                return {
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "task_id": task_id,
                    "status": "cancel_failed"
                }
                
        except Exception as e:
            log.error(f"P2P cancel_task failed for task {task_id}: {str(e)}")
            return {
                "error": str(e),
                "task_id": task_id,
                "status": "cancel_failed"
            }

    def get_task(self, sender_node_id: str, target_address: str, task_id: str, **kwargs) -> Dict[str, Any]:
        """直接A2A获取任务状态"""
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
        """直接A2A取消任务"""
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
        """构建A2A应用 - 遵循Google A2A最佳实践"""
        if not self.adapter or not isinstance(self.adapter, Adapter):
            raise ValueError("A Adapter must be provided to the A2AProtocol.")
        
        return self._build_enhanced_a2a_application()

    def _build_enhanced_a2a_application(self) -> JSONRPCApplication:
        """
        构建增强版的A2A应用 - 复杂逻辑在adapter层
        遵循Google A2A最佳实践：AgentExecutor只负责run/cancel
        """
        # 使用统一的增强adapter
        # Use the unified adapter directly
        enhanced_adapter = self.adapter
        log.info("Using UnifiedIsekAdapter with complete A2A features")
        
        # 使用A2A合规的协议层执行器 - 只负责run/cancel
        agent_executor = A2ACompliantAgentExecutor(self.url, enhanced_adapter)
        
        # 使用标准任务存储（复杂任务管理在adapter中）
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
        """动态启用增强功能"""
        self.enable_long_tasks = enable_long_tasks
        self.enable_enhanced_features = enable_enhanced_features
        
        # 重新构建应用
        self.a2a_application = self.build_a2a_application()
        log.info("Enhanced A2A features enabled")

    def get_task_progress(self, task_id: str) -> Optional[dict]:
        """获取本地任务进度（从adapter中获取）"""
        try:
            adapter = self.a2a_application.http_handler.agent_executor.adapter
            if hasattr(adapter, 'task_store'):
                return adapter.task_store.get_task_progress(task_id)
            return None
        except Exception as e:
            log.error(f"Failed to get local task progress for {task_id}: {str(e)}")
            return None

    def get_session_info(self, context_id: str) -> Optional[dict]:
        """获取本地会话信息（从adapter中获取）"""
        try:
            adapter = self.a2a_application.http_handler.agent_executor.adapter
            if hasattr(adapter, 'session_manager'):
                return adapter.session_manager.get_session_summary(context_id)
            return None
        except Exception as e:
            log.error(f"Failed to get local session info for {context_id}: {str(e)}")
            return None
    
    def get_task_progress_p2p(self, sender_node_id: str, p2p_address: str, task_id: str) -> Optional[dict]:
        """P2P获取任务进度"""
        result = self.get_task_p2p(sender_node_id, p2p_address, task_id, action_type="get_progress")
        return result if not result.get("error") else None
    
    def get_session_info_p2p(self, sender_node_id: str, p2p_address: str, context_id: str) -> Optional[dict]:
        """P2P获取会话信息"""
        result = self.get_task_p2p(sender_node_id, p2p_address, context_id, action_type="get_session")
        return result if not result.get("error") else None