# ISEK DAPP 项目结构

这个仓库包含 ISEK DAPP 的完整实现，包含三个主要程序：

## 📁 目录结构

```
ISEKDAPP/
├── agent_server/                    # 🔧 Agent Server 程序
│   ├── app.py                      # 服务器主入口
│   ├── session_adapter.py          # 模块化会话适配器
│   ├── modules/                    # 可插拔模块
│   │   ├── base.py                # 抽象基类
│   │   ├── session_manager.py     # 会话管理模块
│   │   ├── task_manager.py        # 任务管理模块
│   │   └── message_handler.py     # 消息处理模块
│   ├── shared/                    # 共享消息格式
│   ├── mapper/                    # 数据映射层
│   └── service/                   # 业务逻辑层
│
├── agent_client/                   # 👥 Agent Client 程序集
│   ├── client_backend/            # 🐍 Client 后端程序
│   │   ├── app.py                 # Flask API 服务器
│   │   ├── isek_client.py         # ISEK 节点客户端
│   │   ├── shared_formats.py      # 共享消息格式
│   │   └── requirements.txt       # Python 依赖
│   │
│   └── client_ui/                 # ⚡ Client 前端程序
│       ├── app/                   # Next.js 应用
│       ├── components/            # React 组件
│       ├── lib/                   # 工具库
│       ├── main.js               # Electron 主进程
│       ├── package.json          # Node.js 依赖
│       └── ...                   # 其他前端资源
│
├── logs/                          # 📄 运行时日志
├── quick-start.sh                 # 🚀 快速启动脚本
├── stop-all.sh                   # 🛑 停止所有服务脚本
└── isek_database.db              # 💾 SQLite 数据库
```

## 🎯 三个程序说明

### 1. 🔧 Agent Server (`agent_server/`)
- **功能**: ISEK 代理服务器，处理会话管理、任务执行
- **端口**: 8888
- **技术栈**: Python + ISEK Node + SQLite
- **特点**: 模块化架构，支持可插拔组件

### 2. 🐍 Client Backend (`agent_client/client_backend/`)
- **功能**: 客户端后端API服务器，连接前端和Agent Server
- **端口**: 5000
- **技术栈**: Python + Flask + ISEK Client
- **特点**: RESTful API + WebSocket streaming

### 3. ⚡ Client UI (`agent_client/client_ui/`)
- **功能**: 用户界面，支持Web和桌面应用
- **端口**: 3000 (Web), Electron (桌面)
- **技术栈**: Next.js + React + TypeScript + Electron
- **特点**: 现代响应式UI + 实时聊天界面

## 🚀 快速开始

### 启动所有服务
```bash
./quick-start.sh
```

### 停止所有服务
```bash
./stop-all.sh
```

### 单独启动服务

```bash
# 启动 Agent Server
cd agent_server
python3 app.py

# 启动 Client Backend
cd agent_client/client_backend
python3 app.py

# 启动 Client UI
cd agent_client/client_ui
npm run dev:frontend

# 启动 Electron (可选)
cd agent_client/client_ui
npm run dev:electron
```

## 🔗 服务通信

```
Client UI (3000) ←→ Client Backend (5000) ←→ Agent Server (8888)
     ↕                      ↕                        ↕
  用户界面              RESTful API           ISEK Node 通信
```

## 📊 日志和监控

所有服务的日志文件存储在 `logs/` 目录中：
- `agent_server.log` - Agent Server 日志
- `client_backend.log` - Client Backend 日志  
- `client_frontend.log` - Client UI 日志
- `electron.log` - Electron 应用日志

查看实时日志：
```bash
tail -f logs/*.log
```

## 🛠️ 开发说明

### 环境要求
- Python 3.8+
- Node.js 16+
- ETCD (外部注册中心)

### 安装依赖
```bash
# Python 依赖
cd agent_server && pip install -r requirements.txt
cd agent_client/client_backend && pip install -r requirements.txt

# Node.js 依赖
cd agent_client/client_ui && npm install
```

### 配置
复制并编辑环境变量文件：
```bash
cp env.example .env
```