# ISEKDAPP Dependencies Documentation

## Overview
This document outlines all dependencies required for the ISEKDAPP project, which consists of:
- **Frontend**: React/Next.js Electron application (`agent_client/client_ui/`)
- **Backend**: Python FastAPI client backend (`agent_client/client_backend/`)
- **Server**: Python ISEK agent server (`agent_server/`)

## System Requirements

### Base Requirements
- **Node.js**: >= 22.17.0
- **Python**: >= 3.10.10
- **npm**: Latest version
- **pip**: Latest version

### External Services
- **etcd Registry**: 47.236.116.81:2379 (configured in config.json files)

## Frontend Dependencies (`agent_client/client_ui/`)

### Production Dependencies
```json
{
  "@ai-sdk/openai": "^1.3.22",
  "@assistant-ui/react": "^0.10.25", 
  "@assistant-ui/react-ai-sdk": "^0.10.15",
  "@assistant-ui/react-markdown": "^0.10.6",
  "@radix-ui/react-avatar": "^1.1.10",
  "@radix-ui/react-dialog": "^1.1.14",
  "@radix-ui/react-scroll-area": "^1.2.9",
  "@radix-ui/react-separator": "^1.1.7",
  "@radix-ui/react-slot": "^1.2.3",
  "@radix-ui/react-tooltip": "^1.2.7",
  "ai": "^4.3.16",
  "class-variance-authority": "^0.7.1",
  "clsx": "^2.1.1",
  "lucide-react": "^0.511.0",
  "next": "15.3.2",
  "react": "^19.1.0",
  "react-dom": "^19.1.0", 
  "remark-gfm": "^4.0.1",
  "tailwind-merge": "^3.3.0",
  "tw-animate-css": "^1.3.0"
}
```

### Development Dependencies
```json
{
  "@eslint/eslintrc": "^3",
  "@tailwindcss/postcss": "^4",
  "@types/node": "^22",
  "@types/react": "^19",
  "@types/react-dom": "^19",
  "concurrently": "^8.2.2",
  "electron": "^37.2.0",
  "electron-builder": "^26.0.12",
  "electron-is-dev": "^2.0.0",
  "eslint": "^9",
  "eslint-config-next": "15.3.2",
  "node": "^22.17.0",
  "tailwindcss": "^4",
  "typescript": "^5",
  "wait-on": "^7.2.0"
}
```

## Backend & Server Dependencies (Python)

### Core Python Dependencies
```
# Web Framework
fastapi==0.104.1
uvicorn==0.24.0

# Utilities  
python-dotenv==1.0.0
requests==2.31.0
aiohttp==3.9.1

# ISEK Framework
isek==0.2.1
a2a-sdk==0.2.14

# Development/Testing
pytest
pytest-asyncio
```

### Built-in Python Modules (No Installation Required)
- `sqlite3` - Database operations
- `asyncio` - Async support
- `json` - JSON handling
- `logging` - Logging functionality
- `datetime` - Date/time operations
- `uuid` - UUID generation
- `os` - Operating system interface

## Project Structure

```
ISEKDAPP/
├── agent_client/
│   ├── client_ui/           # React/Next.js Electron Frontend
│   │   ├── package.json     # Node.js dependencies
│   │   └── node_modules/    # Installed npm packages
│   └── client_backend/      # Python FastAPI Backend
│       ├── isek_client.py   # Main client logic
│       ├── config.json      # Client configuration
│       └── shared_formats.py
├── agent_server/            # Python ISEK Agent Server
│   ├── app.py              # Main server application
│   ├── config.json         # Server configuration  
│   ├── mapper/             # Database mappers
│   ├── modules/            # Core modules
│   ├── service/            # Business services
│   └── shared/             # Shared utilities
├── requirements.txt        # Python dependencies (consolidated)
├── quick-start.sh         # Setup script
└── DEPENDENCIES.md        # This documentation
```

## Installation Instructions

### Quick Setup (Recommended)
```bash
# Run the automated setup script
chmod +x setup.sh
./setup.sh
```

### Manual Setup

#### 1. Frontend Setup
```bash
cd agent_client/client_ui
npm install
```

#### 2. Python Dependencies Setup
```bash
# Install Python dependencies (from project root)
pip install -r requirements.txt

# Or install ISEK package separately if needed
pip install isek
```

#### 3. Verify Installation
```bash
# Check Node.js dependencies
cd agent_client/client_ui && npm list --depth=0

# Check Python dependencies  
pip list | grep -E "(fastapi|uvicorn|aiohttp|a2a-sdk)"
```

## Running the Application

### Development Mode
```bash
# Frontend (from agent_client/client_ui/)
npm run dev

# Backend (from agent_client/client_backend/)  
python -m uvicorn app:app --host 0.0.0.0 --port 5001 --reload

# Server (from agent_server/)
python app.py
```

### Production Build
```bash
# Frontend build
cd agent_client/client_ui && npm run build

# Electron distribution
npm run dist:mac  # or dist:win for Windows
```

## Configuration Files

### Client Configuration (`agent_client/client_backend/config.json`)
```json
{
  "node_id": "isek_client_node",
  "port": 8082,
  "p2p": true,
  "p2p_server_port": 9001,
  "registry": {
    "host": "47.236.116.81", 
    "port": 2379
  },
  "backend_port": 5001,
  "frontend_port": 3000
}
```

### Server Configuration (`agent_server/config.json`) 
```json
{
  "node_id": "a_nameless_agent",
  "port": 8888,
  "p2p": true,
  "p2p_server_port": 9000,
  "registry": {
    "host": "47.236.116.81",
    "port": 2379
  }
}
```

## Troubleshooting

### Common Issues
1. **Port Conflicts**: Ensure ports 3000, 5001, 8082, 8888, 9000, 9001 are available
2. **Registry Connection**: Verify etcd registry at 47.236.116.81:2379 is accessible
3. **Python Path**: Ensure ISEK package is properly installed and accessible
4. **Node Version**: Use Node.js >= 22.17.0 for compatibility

### Dependency Conflicts
- If you encounter npm dependency conflicts, try: `npm install --legacy-peer-deps`
- For Python conflicts, consider using a virtual environment: `python -m venv venv && source venv/bin/activate`

## Updates

To update dependencies:
```bash
# Frontend
cd agent_client/client_ui && npm update

# Python  
pip install --upgrade -r requirements.txt
```

## Security Notes
- All configurations use external etcd registry (47.236.116.81:2379)
- No sensitive credentials are stored in configuration files
- A2A protocol handles secure peer-to-peer communication