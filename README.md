# ISEK UI - P2P Multi-Agent Chat Demo

ISEK UI is a desktop application based on Electron + Next.js that serves as a client for ISEK node, connecting to local ISEK node and enabling P2P chat with agents in the network.

## Architecture Overview

### Frontend (Electron + Next.js)
- **Location**: `electron/` directory
- **Function**: Provides user interface, manages chat threads and messages
- **Tech Stack**: Electron + Next.js + TypeScript + Tailwind CSS

### Backend (Python Flask)
- **Location**: `pybackend/` directory  
- **Function**: ISEK node client, responsible for connecting to local ISEK node and discovering agents
- **Tech Stack**: Python Flask + aiohttp + ISEK node protocol

### Communication Flow
1. Frontend discovers agents in ISEK node through backend API
2. User selects agent to create chat thread
3. Frontend sends message to backend
4. Backend sends message to target agent through ISEK node
5. Agent response returns through ISEK node
6. Backend sends response to frontend for display

## Development Environment Setup

### 1. Install Dependencies

   ```bash
# Install frontend dependencies
   npm install

# Install backend dependencies
cd pybackend
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
# Copy environment variable template
cp pybackend/env.example pybackend/.env

# Edit .env file to configure ISEK node connection
ISEK_NODE_URL=http://localhost:8000
```

### 3. Start Development Environment

#### Using ISEK Node Simulator (Recommended for Testing)

   ```bash
# Start ISEK Node simulator
cd pybackend
python mock_isek_node.py

# New terminal: Start backend service
cd pybackend
python app.py

# New terminal: Start frontend development server
   npm run dev

# New terminal: Start Electron
   npm run electron
   ```

#### Using Real ISEK Node

   ```bash
# Start ISEK node (refer to ISEK official documentation)
# https://github.com/isekOS/ISEK

# Start backend service
cd pybackend
python app.py

# New terminal: Start frontend development server
npm run dev

# New terminal: Start Electron
   npm run electron
   ```

## Features

### Agent Discovery
- Automatically discover available agents in the network through ISEK node
- Display agent names, descriptions, and capabilities
- Real-time agent status updates

### Chat Functionality
- P2P chat with agents in the network through ISEK node
- Support for multi-threaded conversations
- Save chat history
- Real-time message sending and receiving

### User Interface
- Modern desktop application interface
- Agent selector
- Chat thread management
- Responsive design

## Project Structure

```
ISEKDAPP/
├── electron/                 # Frontend application
│   ├── app/                 # Next.js application
│   ├── components/          # React components
│   ├── lib/                 # Utility libraries and type definitions
│   └── main.js              # Electron main process
├── pybackend/               # Backend service
│   ├── app.py               # Flask application main file
│   ├── isek_client.py       # ISEK node client
│   ├── mock_isek_node.py    # ISEK node simulator
│   ├── requirements.txt     # Python dependencies
│   └── env.example          # Environment variable template
├── package.json             # Project configuration
└── README.md               # Project documentation
```

## Build and Deployment

### Development Mode
   ```bash
npm run dev          # Start Next.js development server
npm run electron     # Start Electron application
   ```

### Production Build
   ```bash
# Build Next.js application
   npm run build

# Build Python backend
cd pybackend
pyinstaller --onefile app.py

# Package Electron application
   npm run dist
   ```

## ISEK Node Integration

### Current Status
- Connect to local ISEK node
- Discover agents through ISEK node
- Send messages to agents through ISEK node
- Use fallback agents when ISEK node is unavailable

### ISEK Node Interface
The backend expects ISEK node to provide the following interfaces:

- `GET /health` - Health check
- `GET /agents` - Get agent list
- `POST /chat` - Send message to agent

### Message Format
Message format sent to ISEK node:

```json
{
  "agent_id": "agent-123",
  "messages": [
    {"role": "user", "content": "Hello"}
  ],
  "system_prompt": "You are a friendly assistant"
}
```

### Testing
Use the provided simulator for testing:

     ```bash
# Start simulator
cd pybackend
python mock_isek_node.py

# Test health check
curl http://localhost:8000/health

# Test get agent list
curl http://localhost:8000/agents

# Test send message
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"isek-assistant-001","messages":[{"role":"user","content":"Hello"}]}'
```

### Future Plans
- Integrate real ISEK network protocol
- Support agent registration and discovery
- Implement P2P message transmission
- Add agent capability verification

## Tech Stack

- **Frontend**: Electron, Next.js, React, TypeScript, Tailwind CSS
- **Backend**: Python, Flask, aiohttp, ISEK node protocol
- **Build Tools**: Vite, Electron Builder
- **Development Tools**: ESLint, Prettier

## Contributing

Issues and Pull Requests are welcome!

## License

MIT License
