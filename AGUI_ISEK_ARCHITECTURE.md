# AGUI-ISEK 集成架构文档

## 整体架构

### 通信链路
```
前端 (Web UI) 
    ↓ AGUI Protocol (Events/Messages)
AGUI Middleware (agui_middleware_py)
    ↓ A2A Protocol (JSON-RPC + Events)
ISEK Node (Client) 
    ↓ ETCD Registry + ISEK P2P Protocol
ISEK Node (Server)
    ↓ A2A Protocol (深度融合)
Agent (Lyra/其他)
```

## 核心组件

### Client 端 (agui_middleware_py)

**职责**: 连接前端，协议转换，消息转发
- **agui_adapter.py**: AGUI ↔ A2A 协议转换
- **isek_client.py**: ISEK Node 管理和服务发现
- **a2a_translator.py**: 专门的协议翻译器
- **middleware.py**: 核心中间件逻辑

**不包含**: TaskStore, AgentExecutor (这些是 Server 端组件)

### Server 端 (agent_server)

**职责**: Agent 执行，任务管理，会话管理
- **a2a_protocol.py**: A2A Server + TaskStore + AgentExecutor
- **isek_adapter.py**: Agent 执行逻辑 + 复杂业务逻辑
- **session.py**: 会话管理
- **task.py**: 任务存储和生命周期管理

## 关键发现：ISEK Response 与 A2A 深度融合

通过源码分析发现，**ISEK Adapter 直接产生完整的 A2A 事件流**：

### A2A 事件类型 (Adapter 输出)
```python
# 1. 任务状态事件
TaskStatusUpdateEvent(
    contextId=session_id,
    taskId=task_id,
    status=TaskStatus(state=TaskState.working),
    final=False,
    metadata={...}
)

# 2. 消息事件
new_agent_text_message("response content")

# 3. 错误事件
A2AError(code=-32602, message="error details")

# 4. 任务创建事件
new_task(...)
```

### 完整事件流示例
```python
async def execute_async(context) -> AsyncGenerator[A2AEvent, None]:
    # 1. 任务开始
    yield TaskStatusUpdateEvent(status=TaskState.working)
    
    # 2. 进度更新 (长任务)
    yield TaskStatusUpdateEvent(metadata={"progress": 0.3})
    
    # 3. 中间消息
    yield new_agent_text_message("Processing...")
    
    # 4. 最终结果
    yield new_agent_text_message("Final result")
    
    # 5. 任务完成
    yield TaskStatusUpdateEvent(status=TaskState.completed, final=True)
```

## 协议转换 (修正版)

### 入向流程
```
AGUI Events → A2A JSON-RPC → ISEK Message → Adapter Context
```

### 出向流程 (关键)
```
Adapter → A2A Events Stream → ISEK Response → A2A JSON-RPC → AGUI Events
```

**重要**: Adapter 直接输出 A2A 原生事件，ISEK Node 无需再次转换，只需透传。

## ISEK Node 通信机制

### 服务发现
- **注册**: 通过 ETCD Registry 注册节点信息
- **发现**: Client 查询 ETCD 获取可用 Server 节点
- **健康检查**: 定期更新节点状态

### 消息传递
- **协议**: ISEK P2P Protocol (非直接 HTTP)
- **路由**: 通过 ETCD 路由到目标节点
- **可靠性**: 支持重试和故障转移

### 会话管理
- **Session ID**: 贯穿整个调用链
- **Context 传递**: RequestContext 和 TaskStore 信息透传
- **状态同步**: Client 和 Server 状态一致性

## 数据流详解

### 1. 请求阶段
```json
// AGUI Input
{
  "messages": [...],
  "agent_id": "lyra_agent",
  "session_id": "uuid"
}

// A2A JSON-RPC (Client → Server)
{
  "jsonrpc": "2.0",
  "method": "message/send",
  "params": {
    "message": {...},
    "metadata": {
      "session_id": "uuid",
      "requestContext": {...}
    }
  }
}

// Adapter Context (Server 端)
{
  "task_id": "uuid",
  "session_id": "uuid", 
  "user_input": "user message",
  "current_task": {...}
}
```

### 2. 响应阶段
```python
# Adapter 输出 (A2A Events)
async for event in adapter.execute_async(context):
    if isinstance(event, TaskStatusUpdateEvent):
        # 任务状态更新
    elif isinstance(event, new_agent_text_message):
        # 文本消息
    elif isinstance(event, A2AError):
        # 错误处理

# 转换为 AGUI Events
{
  "type": "message",
  "content": "...",
  "role": "assistant",
  "timestamp": "..."
}
```

## 实现要点

### 1. Adapter 设计
- **输入**: RequestContext (包含 session_id, task_id, user_input)
- **输出**: AsyncGenerator[A2AEvent] (原生 A2A 事件流)
- **状态**: 内置 TaskStore 和 SessionManager

### 2. Protocol 集成
- **Client**: 仅需 A2A Client (发送请求，接收事件流)
- **Server**: 需要完整 A2A Server (TaskStore, AgentExecutor, RequestHandler)
- **通信**: 通过 ISEK Node P2P，非直接 HTTP

### 3. 错误处理
- **超时**: ISEK Node 级别的超时处理
- **重试**: 自动重试和故障转移
- **降级**: HTTP JSON-RPC 作为 fallback

## 部署架构

### Client 部署
```
agui_middleware_py/
├── adapters/agui_adapter.py    # AGUI协议适配
├── core/isek_client.py         # ISEK节点管理  
├── core/a2a_translator.py      # 协议转换
└── main.py                     # 启动入口
```

### Server 部署  
```
agent_server/
├── protocol/a2a_protocol.py    # A2A服务器
├── adapter/isek_adapter.py     # Agent适配器
├── app/lyra/                   # Lyra Agent
└── utils/                      # 会话/任务管理
```

### 网络拓扑
```
[前端] ←→ [AGUI Middleware] ←→ [ETCD] ←→ [Agent Server] ←→ [Agent]
        (Client Node)              (Registry)   (Server Node)
```

这个架构确保了：
1. **协议原生性**: Adapter 直接输出 A2A 事件
2. **状态一致性**: 会话和任务状态透传
3. **可扩展性**: 通过 ETCD 支持多节点
4. **容错性**: 多级降级和重试机制

## 改进建议 (Improvements)

### 1. 完整 A2A 通信方法支持

当前实现主要支持 `message/send`，建议扩展到完整的 A2A 协议：

#### 1.1 核心协议方法
```python
# 当前已实现
- message/send (✓)

# 建议新增
- message/stream     # 流式响应支持
- tasks/get         # 任务状态查询  
- tasks/cancel      # 任务取消
- tasks/progress    # 任务进度查询
```

#### 1.2 P2P 通信包装
```python
# ISEK Node P2P 模式支持
class AGUIAdapter:
    def __init__(self, isek_node_config, enable_p2p=True):
        self.enable_p2p = enable_p2p
        
    async def send_message_p2p(self, p2p_address: str, message: str):
        """P2P 包装消息发送"""
        if self.enable_p2p:
            return await self._send_via_p2p(p2p_address, message)
        else:
            return await self._send_via_http(target_url, message)
            
    async def get_task_status_p2p(self, p2p_address: str, task_id: str):
        """P2P 任务状态查询"""
        
    async def cancel_task_p2p(self, p2p_address: str, task_id: str):
        """P2P 任务取消"""
```

### 2. 异步通信增强

#### 2.1 完整异步方法支持
```python
class AGUIAdapter:
    async def execute_async(self, context: dict) -> AsyncGenerator[Any, None]:
        """异步执行 - 已实现"""
        
    async def cancel_async(self, context: dict) -> AsyncGenerator[Any, None]:
        """异步取消 - 建议新增"""
        
    async def get_status_async(self, task_id: str) -> Dict[str, Any]:
        """异步状态查询 - 建议新增"""
        
    async def stream_response_async(self, context: dict) -> AsyncGenerator[str, None]:
        """异步流式响应 - 建议新增"""
```

#### 2.2 事件流管理
```python
# A2A 完整事件类型支持
class A2AEventHandler:
    async def handle_task_status_update(self, event: TaskStatusUpdateEvent):
        """处理任务状态更新"""
        
    async def handle_message_event(self, event: MessageEvent):
        """处理消息事件"""
        
    async def handle_error_event(self, event: A2AError):
        """处理错误事件"""
        
    async def handle_streaming_event(self, event: StreamEvent):
        """处理流式事件 - 新增"""
```

### 3. 任务管理增强

#### 3.1 长任务支持
```python
class EnhancedTaskManager:
    async def create_long_task(self, task_id: str, estimated_duration: int):
        """创建长时间任务"""
        
    async def report_progress(self, task_id: str, progress: float, message: str):
        """报告任务进度"""
        
    async def handle_task_cancellation(self, task_id: str):
        """处理任务取消"""
        
    async def cleanup_expired_tasks(self):
        """清理过期任务"""
```

#### 3.2 会话状态管理
```python
class SessionManager:
    async def create_persistent_session(self, session_id: str):
        """创建持久化会话"""
        
    async def sync_session_state(self, session_id: str, remote_node: str):
        """同步会话状态"""
        
    async def handle_session_recovery(self, session_id: str):
        """会话恢复处理"""
```

### 4. 流式响应完整支持

#### 4.1 Server-Sent Events (SSE)
```python
class StreamingHandler:
    async def create_sse_stream(self, session_id: str) -> AsyncGenerator[str, None]:
        """创建 SSE 流"""
        
    async def handle_stream_interruption(self, session_id: str):
        """处理流中断"""
        
    async def stream_task_progress(self, task_id: str) -> AsyncGenerator[dict, None]:
        """流式任务进度"""
```

#### 4.2 实时事件推送
```python
# 支持实时事件推送到前端
async def push_real_time_events(self, agui_events: AsyncGenerator):
    """推送实时事件到 AGUI 前端"""
    async for event in agui_events:
        await self.websocket_manager.broadcast(event)
```

### 5. 错误处理和重试机制

#### 5.1 智能重试
```python
class ReliableCommunication:
    async def send_with_exponential_backoff(self, message: str, max_retries: int = 3):
        """指数退避重试"""
        
    async def circuit_breaker_send(self, target: str, message: str):
        """断路器模式发送"""
        
    async def fallback_communication(self, primary_failed: bool):
        """降级通信机制"""
```

#### 5.2 健康检查
```python
class HealthMonitor:
    async def check_node_health(self, node_id: str) -> bool:
        """检查节点健康状态"""
        
    async def auto_failover(self, failed_node: str):
        """自动故障转移"""
        
    async def load_balance_requests(self, available_nodes: List[str]):
        """负载均衡请求"""
```

### 6. 安全和认证增强

#### 6.1 身份验证
```python
class A2AAuthentication:
    async def authenticate_node(self, node_id: str, credentials: dict) -> bool:
        """节点身份验证"""
        
    async def generate_session_token(self, session_id: str) -> str:
        """生成会话令牌"""
        
    async def validate_message_signature(self, message: dict) -> bool:
        """验证消息签名"""
```

### 7. 监控和观测性

#### 7.1 指标收集
```python
class MetricsCollector:
    async def track_message_latency(self, start_time: float, end_time: float):
        """跟踪消息延迟"""
        
    async def track_task_completion_rate(self, task_id: str, success: bool):
        """跟踪任务完成率"""
        
    async def export_prometheus_metrics(self):
        """导出 Prometheus 指标"""
```

### 8. 配置和部署改进

#### 8.1 动态配置
```python
# config.yaml 增强
agui_adapter:
  communication:
    enable_p2p: true
    enable_streaming: true
    enable_task_management: true
    retry_config:
      max_retries: 3
      backoff_factor: 2
    timeout_config:
      message_timeout: 30
      task_timeout: 300
      stream_timeout: 60
```

#### 8.2 部署模式
```python
# 支持多种部署模式
- standalone      # 单机模式
- cluster         # 集群模式  
- edge           # 边缘部署
- hybrid         # 混合模式
```

这些改进将使 AGUI-ISEK 集成更加完整、可靠和功能丰富。