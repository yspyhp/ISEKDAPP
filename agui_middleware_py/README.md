# AGUI-ISEK Middleware

A Python middleware that bridges the AGUI (Agent-Guided User Interface) protocol with ISEK (Intelligent Software Engineering Kit) agents through A2A (Agent-to-Agent) communication.

## Architecture

```
AGUI Client/Frontend
        ↓ (HTTP/JSON)
    AGUI Middleware (This Project)
        ↓ (A2A Protocol)
    ISEK Node (Agent Discovery via ETCD)
        ↓ (Service Discovery)
    Target Agents (e.g., Lyra Agent)
        ↓ (OpenAI/LLM APIs)
    AI Response
```

## Features

### Core Functionality
- ✅ **ISEK Client Integration**: Creates ISEK node for A2A communication
- ✅ **Agent Discovery**: Discovers available agents via ETCD registry
- ✅ **Protocol Translation**: Converts between A2A and AGUI protocols
- ✅ **Agent Wrapping**: Makes ISEK agents compatible with AGUI interface
- ✅ **FastAPI Server**: Provides HTTP endpoints for AGUI clients

### AGUI Compatibility
- ✅ **Event-Driven Architecture**: Streams AGUI-compatible events
- ✅ **Strongly Typed Structures**: Uses AGUI core types (when available)
- ✅ **Agent Management**: Lists, runs, and monitors agents
- ✅ **Session Handling**: Maintains conversation continuity

### ISEK Integration
- ✅ **A2A Protocol**: Full A2A message support
- ✅ **Service Discovery**: ETCD-based agent discovery
- ✅ **Node Management**: ISEK node lifecycle management
- ✅ **Error Handling**: Robust error propagation

## Installation

### Prerequisites
- Python 3.8+
- Access to ETCD registry (default: 47.236.116.81:2379)
- Available ISEK agents to connect to

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Configuration
Edit `config.yaml`:

```yaml
middleware:
  name: "AGUI-ISEK Middleware"
  port: 8080

isek:
  node_id: "agui_middleware_node"
  host: "0.0.0.0"
  port: 8082
  registry:
    host: "47.236.116.81"
    port: 2379

agui:
  max_concurrent_sessions: 10
  stream_buffer_size: 1024

logging:
  level: "INFO"
```

## Usage

### Start the Middleware
```bash
python main.py
```

The server will start on `http://localhost:8080` by default.

### API Endpoints

#### Health Check
```bash
GET /health
```

#### Get Available Agents
```bash
GET /agents
```

#### Send Message to Agent
```bash
POST /agents/{agent_id}/message
Content-Type: application/json

{
  "message": "Hello, please help me optimize this prompt: 'Write a story'",
  "session_id": "optional-session-id",
  "metadata": {}
}
```

#### Run Agent with AGUI Input
```bash
POST /agents/{agent_id}/run
Content-Type: application/json

{
  "messages": [
    {
      "role": "user",
      "content": "Help me with prompt optimization"
    }
  ],
  "context": {
    "session_id": "my-session",
    "user_id": "user-123"
  }
}
```

#### AGUI-Compatible Endpoints
```bash
POST /agui/agents           # Get agents (AGUI format)
POST /agui/agents/{id}/run  # Run agent (AGUI format)
```

## Development

### Run Tests
```bash
python test_middleware.py
```

### Project Structure
```
agui_middleware_py/
├── core/
│   ├── __init__.py
│   ├── middleware.py          # Main middleware orchestrator
│   ├── isek_client.py         # ISEK node and A2A handling
│   ├── a2a_translator.py      # A2A ↔ AGUI translation
│   └── agent_wrapper.py       # ISEK agent → AGUI wrapper
├── main.py                    # FastAPI server
├── config.yaml               # Configuration
├── requirements.txt           # Dependencies
├── test_middleware.py         # Test suite
└── README.md                 # This file
```

## Integration Examples

### With AGUI Frontend
```javascript
// JavaScript/TypeScript frontend
const response = await fetch('/agents/lyra_agent/message', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: "Optimize this prompt: 'Generate code'",
    session_id: "user-session-123"
  })
});

const result = await response.json();
console.log(result.response);
```

### With Python Client
```python
import httpx

async def send_to_agent():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8080/agents/lyra_agent/message",
            json={
                "message": "Help me improve this prompt",
                "session_id": "python-client-session"
            }
        )
        return response.json()
```

## Connecting to Lyra Agent

If you have a Lyra agent running (from the main ISEK DAPP project):

1. **Start Lyra Agent** (in separate terminal):
   ```bash
   cd /Users/sparkss/ISEKDAPP
   ./quick-start.sh --lyra --server-only --proxy
   ```

2. **Start AGUI Middleware**:
   ```bash
   cd /Users/sparkss/ISEKDAPP/agui_middleware_py
   python main.py
   ```

3. **Test Communication**:
   ```bash
   curl -X POST http://localhost:8080/agents/refresh
   curl http://localhost:8080/agents
   ```

## Configuration Options

### ISEK Configuration
- `node_id`: Unique identifier for this middleware node
- `host`/`port`: Network binding for ISEK node
- `registry`: ETCD connection details

### AGUI Configuration
- `max_concurrent_sessions`: Limit concurrent agent sessions
- `stream_buffer_size`: Buffer size for streaming responses
- `response_timeout`: Timeout for agent responses

### Logging
- `level`: Log level (DEBUG, INFO, WARNING, ERROR)
- `format`: Log message format

## Troubleshooting

### Common Issues

1. **"Middleware not initialized"**
   - Check ETCD connectivity
   - Verify configuration file
   - Check network permissions

2. **"Agent not found"**
   - Ensure target agents are running
   - Call `/agents/refresh` to update agent list
   - Check ETCD registry for agent registration

3. **Connection timeouts**
   - Verify network connectivity to ETCD
   - Check agent URLs are accessible
   - Increase timeout values in configuration

### Debug Mode
Set environment variable for verbose logging:
```bash
PYTHONPATH=. LOG_LEVEL=DEBUG python main.py
```

### Health Checks
Monitor middleware health:
```bash
curl http://localhost:8080/health
curl http://localhost:8080/status
```

## License

Part of the ISEK DAPP project. See main project LICENSE for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Run test suite: `python test_middleware.py`
5. Submit pull request

## Related Projects

- **ISEK DAPP**: Main project with Lyra agent
- **AGUI**: Official AGUI documentation and SDK
- **A2A Protocol**: Agent-to-Agent communication standard