# A2A Agent Server

基于Google A2A协议的最佳实践实现的代理服务器，集成Lyra团队，提供完整的任务管理、会话管理和多轮对话支持。

## 架构概述

本服务器遵循Google A2A最佳实践，采用分层架构设计：

```
A2A Protocol Layer (A2ACompliantAgentExecutor)
    ↓
Unified Enhanced Adapter (UnifiedEnhancedAdapter)
    ↓
ISEK Team Layer (IsekTeamAdapter)
    ↓
ISEK Agent Layer (Lyra Team)
```

### 核心原则

1. **AgentExecutor只负责run/cancel** - 不包含任何业务逻辑
2. **复杂逻辑在adapter层处理** - 任务管理、会话管理、多轮对话
3. **统一的adapter实现** - 一个adapter包含所有功能
4. **遵循A2A标准** - 完全兼容Google A2A协议

## 功能特性

### 🎯 任务管理
- **生命周期跟踪**: submitted → working → completed/failed/cancelled
- **进度报告**: 实时任务进度更新
- **任务取消**: 支持长时间任务的优雅取消
- **任务持久化**: 任务状态和元数据存储

### 💬 会话管理
- **对话历史**: 自动保存和检索对话记录
- **上下文感知**: 基于历史对话的智能响应
- **会话持久化**: 跨请求的会话状态维护
- **上下文构建**: 智能的提示词增强

### 🔄 多轮对话
- **信息收集**: 自动识别需要更多信息的请求
- **确认流程**: 用户确认机制
- **状态管理**: 多轮对话状态跟踪
- **优雅降级**: 处理异常情况

### ⚡ 长任务支持
- **可取消性**: 支持任务中断和清理
- **进度报告**: 实时更新任务进展
- **错误恢复**: 优雅处理异常情况
- **资源管理**: 合理管理任务资源

### 🌊 流式响应
- **实时输出**: 类似ChatGPT的打字效果
- **进度指示**: 流式处理进度显示
- **可配置**: 支持启用/禁用流式输出

### 🌐 P2P任务管理 (新增)
- **P2P任务状态查询**: `get_task_p2p()` - 通过P2P网络获取远程任务状态
- **P2P任务取消**: `cancel_task_p2p()` - 通过P2P网络取消远程任务
- **直接A2A任务管理**: `get_task()`, `cancel_task()` - 直接HTTP调用
- **任务进度查询**: `get_task_progress_p2p()` - P2P获取任务进度
- **会话信息查询**: `get_session_info_p2p()` - P2P获取会话状态

## 快速开始

### 1. 环境准备

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，添加必要的API密钥
```

### 2. 配置服务器

编辑 `config.json` 文件：

```json
{
  "node_id": "lyra-a2a-agent",
  "host": "localhost",
  "port": 8080,
  "a2a": {
    "enhanced_mode": true,
    "task_management": {
      "enable_cancellation": true
    },
    "streaming": {
      "enabled": false
    }
  }
}
```

### 3. 启动服务器

```bash
python server.py
```

服务器将在 `http://localhost:8080` 启动，支持以下端点：

- `POST /send_message` - 发送消息
- `POST /cancel_task` - 取消任务
- `GET /health` - 健康检查

## 配置说明

### A2A配置

```json
{
  "a2a": {
    "enhanced_mode": true,           // 启用增强功能
    "task_management": {
      "enable_cancellation": true,   // 启用任务取消
      "max_task_duration": 3600,     // 最大任务时长（秒）
      "progress_reporting": true     // 启用进度报告
    },
    "session_management": {
      "session_timeout": 1800,       // 会话超时（秒）
      "max_history_length": 100      // 最大历史记录数
    },
    "streaming": {
      "enabled": false,              // 启用流式响应
      "chunk_size": 5,               // 流式块大小
      "delay_ms": 50                 // 流式延迟（毫秒）
    },
    "multiturn_conversation": {
      "enabled": true,               // 启用多轮对话
      "max_turns": 10,               // 最大轮次
      "auto_timeout": 300            // 自动超时（秒）
    }
  }
}
```

## API使用示例

### 发送消息

```python
import requests

# 发送简单消息
response = requests.post("http://localhost:8080/send_message", json={
    "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "Help me optimize this prompt"}]
    }
})

print(response.json())
```

### 取消任务

```python
# 取消正在运行的任务
response = requests.post("http://localhost:8080/cancel_task", json={
    "task_id": "task_123"
})
```

### 多轮对话示例

```python
# 第一轮：用户发送简短请求
response1 = requests.post("http://localhost:8080/send_message", json={
    "message": {
        "role": "user", 
        "parts": [{"kind": "text", "text": "Help me"}]
    }
})

# 服务器响应：需要更多信息
# 返回：TaskStatusUpdateEvent(status="input-required")

# 第二轮：用户提供更多信息
response2 = requests.post("http://localhost:8080/send_message", json={
    "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "I need help with Python programming"}]
    }
}, headers={"task_id": "task_123"})
```

### P2P任务管理示例

```python
from agent_server.protocol.a2a_protocol import A2AProtocol

# 创建A2A协议实例
a2a = A2AProtocol(host="localhost", port=8080, p2p=True, p2p_server_port=9000)

# P2P发送消息
response = a2a.send_p2p_message(
    sender_node_id="my-node",
    p2p_address="/ip4/127.0.0.1/tcp/9001/p2p/QmRemoteNode",
    message="分析这个数据集"
)

# P2P获取任务状态
task_status = a2a.get_task_p2p(
    sender_node_id="my-node",
    p2p_address="/ip4/127.0.0.1/tcp/9001/p2p/QmRemoteNode",
    task_id="task_123"
)

# P2P取消任务
cancel_result = a2a.cancel_task_p2p(
    sender_node_id="my-node",
    p2p_address="/ip4/127.0.0.1/tcp/9001/p2p/QmRemoteNode",
    task_id="task_123"
)

# P2P获取任务进度
progress = a2a.get_task_progress_p2p(
    sender_node_id="my-node",
    p2p_address="/ip4/127.0.0.1/tcp/9001/p2p/QmRemoteNode",
    task_id="task_123"
)

# 直接A2A任务管理（不通过P2P）
task_status = a2a.get_task(
    sender_node_id="my-node",
    target_address="http://remote-agent:8080",
    task_id="task_123"
)

cancel_result = a2a.cancel_task(
    sender_node_id="my-node", 
    target_address="http://remote-agent:8080",
    task_id="task_123"
)
```

## 架构组件

### A2ACompliantAgentExecutor

遵循A2A最佳实践的执行器，只负责：
- 调用adapter的run方法
- 调用adapter的cancel方法
- 不包含任何业务逻辑

### UnifiedEnhancedAdapter

统一的增强适配器，包含所有业务逻辑：

```python
class UnifiedEnhancedAdapter(Adapter):
    def __init__(self, base_adapter: Adapter, enable_streaming: bool = False):
        self.base_adapter = base_adapter
        self.session_manager = SessionManager()
        self.task_store = EnhancedTaskStore()
        self.running_tasks = {}
        self.conversation_states = {}
```

**核心方法**：
- `execute_async()` - 异步任务执行
- `cancel_async()` - 异步任务取消
- `_manage_session_context()` - 会话管理
- `_handle_multiturn_flow()` - 多轮对话处理

### SessionManager

独立的会话管理器，不依赖ISEK Memory：

```python
class SessionManager:
    def __init__(self):
        self.session_store = SessionStore()
        self.active_contexts = {}
```

**功能**：
- 会话创建和管理
- 对话历史存储
- 上下文构建
- 会话摘要生成

### EnhancedTaskStore

增强的任务存储，支持完整生命周期：

```python
class EnhancedTaskStore(InMemoryTaskStore):
    def __init__(self):
        self.task_metadata = {}
        self.task_history = {}
        self.task_artifacts = {}
        self.task_progress = {}
```

**功能**：
- 任务状态跟踪
- 进度管理
- 元数据存储
- 历史记录

## 开发指南

### 添加新的Adapter

```python
from agent_server.adapter.enhanced import UnifiedEnhancedAdapter

class MyCustomAdapter(UnifiedEnhancedAdapter):
    def __init__(self, my_base_adapter):
        super().__init__(my_base_adapter, enable_streaming=True)
    
    async def _execute_short_task(self, task_id: str, session_id: str, prompt: str):
        # 自定义短任务处理逻辑
        result = await self.my_custom_processing(prompt)
        yield new_agent_text_message(result)
```

### 扩展会话管理

```python
from utils.session import SessionManager

class CustomSessionManager(SessionManager):
    def get_conversation_context(self, session_id: str, limit: int = 5) -> str:
        # 自定义上下文构建逻辑
        context = super().get_conversation_context(session_id, limit)
        return self.enhance_context(context)
```

## 监控和调试

### 日志配置

```json
{
  "logging": {
    "level": "INFO",
    "format": "json",
    "file": "logs/a2a-agent.log"
  }
}
```

### 健康检查

```bash
curl http://localhost:8080/health
```

### 任务状态查询

```python
# 获取任务进度
progress = a2a_server.get_task_progress("task_123")

# 获取会话信息
session_info = a2a_server.get_session_info("session_456")
```

## 性能优化

### 配置建议

```json
{
  "a2a": {
    "performance": {
      "connection_pool_size": 10,
      "request_timeout": 60,
      "memory_optimization": true
    }
  }
}
```

### 最佳实践

1. **合理设置任务超时** - 避免长时间阻塞
2. **启用流式响应** - 改善用户体验
3. **配置会话清理** - 防止内存泄漏
4. **监控任务状态** - 及时发现异常

## 故障排除

### 常见问题

1. **任务无法取消**
   - 检查 `enable_cancellation` 配置
   - 确认adapter支持取消操作

2. **会话上下文丢失**
   - 检查会话超时设置
   - 确认SessionManager正常工作

3. **流式响应不工作**
   - 检查 `enable_streaming` 配置
   - 确认基础adapter支持流式输出

### 调试模式

```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 贡献指南

1. 遵循Google A2A最佳实践
2. 保持AgentExecutor的简洁性
3. 在adapter层实现复杂逻辑
4. 添加适当的测试和文档

## 许可证

MIT License

## 支持

如有问题，请查看：
- [Google A2A文档](https://github.com/a2aproject/A2A)
- [ISEK文档](https://github.com/isek-project/isek)
- [项目Issues](https://github.com/your-repo/issues)