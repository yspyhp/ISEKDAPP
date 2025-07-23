# ISEK Native A2A Node Implementation Guide

## Overview

This guide provides comprehensive instructions for modifying ISEK nodes to use native A2A (Agent-to-Agent) protocol instead of JSON string message parsing. The native A2A implementation offers better performance, protocol compliance, and enhanced capabilities.

## Current Architecture vs Native A2A

### Current JSON String Approach
```
User Request → Node → JSON String → Adapter Parse → Agent Team → JSON Response
```

### Native A2A Approach  
```
User Request → NativeA2ANode → A2A Protocol → NativeA2AAdapter → Agent Team → A2A Response
```

## Key Differences

| Aspect | Current JSON Approach | Native A2A Approach |
|--------|----------------------|-------------------|
| Message Format | JSON strings | A2A protocol objects |
| Communication | HTTP with JSON parsing | Native A2A JSON-RPC 2.0 |
| Agent Discovery | Manual node discovery | Automatic A2A agent discovery |
| Task Management | Basic execution | Advanced task lifecycle |
| Session Management | Simple state | Cross-agent session migration |
| Streaming | Limited support | Native A2A streaming |

## Implementation Steps

### Step 1: Install A2A Dependencies

Ensure the Google A2A SDK is installed:
```bash
pip install a2a-sdk  # Install if not already available
```

### Step 2: Replace Standard Node with NativeA2ANode

#### Before (Current Approach):
```python
# agent_server/app/lyra/Lyra_gent.py
from isek.node.node_v2 import Node

# Create standard node
server_node = Node(
    node_id=config["node_id"],
    port=config["port"], 
    adapter=session_adapter,  # SessionAdapter with JSON parsing
    registry=etcd_registry
)
```

#### After (Native A2A Approach):
```python
# agent_server/app/lyra/Lyra_gent.py
import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

from a2a.native_a2a_node import create_native_a2a_node

# Create native A2A node - no adapter needed!
server_node = create_native_a2a_node(
    agent_team=agent_team,  # Pass agent team directly
    host="localhost",
    port=config["port"],
    node_id=config["node_id"],
    registry=etcd_registry
)
```

### Step 3: Update Node Configuration

#### Enhanced Node Registration
The native A2A node automatically registers with enhanced metadata:

```python
# Automatic registration includes:
node_metadata = {
    "url": f"http://{self.host}:{self.port}",
    "peer_id": f"a2a_peer_{self.node_id}",
    "p2p_address": f"a2a://{self.host}:{self.port}",
    "protocol": "native_a2a",
    "a2a_enabled": True,
    "agent_name": "Lyra Agent",
    "agent_description": "AI prompt optimization specialist",
    "agent_capabilities": {...},
    "agent_skills": [...]
}
```

### Step 4: Enhanced Message Processing

#### Native A2A Message Handling
The native node automatically handles different request types:

```python
# Automatic request routing:
- Task execution: "execute task: analyze data"
- Capability queries: "can you generate images?"
- Agent discovery: "find agent with analytics capability"
- Session messages: Regular chat with session context
- Chat messages: Direct agent team interaction
```

### Step 5: Advanced A2A Features

#### Agent Discovery
```python
# In your agent team logic:
node = get_current_node()  # Your native A2A node

# Discover agents by capability
agents = await node.discover_agents_by_capability("image_generation")

# Delegate tasks to other agents
result = await node.delegate_task_to_agent(
    task_type="data_analysis",
    task_data={"dataset": "user_data.csv"},
    target_agent_id="analytics_agent_001"
)
```

#### Cross-Agent Session Management
```python
# Sessions automatically managed across agents
# Session state migrates when delegating to other agents
# No manual session handling needed
```

## Complete Implementation Example

### Updated Lyra_gent.py

```python
import os
import sys
import json
from dotenv import load_dotenv
from isek.agent.isek_agent import IsekAgent
from isek.models.openai import OpenAIModel
from isek.tools.calculator import calculator_tools
from isek.memory.memory import Memory as SimpleMemory
from isek.team.isek_team import IsekTeam
from isek.utils.log import log
from isek.node.etcd_registry import EtcdRegistry

# Add path for A2A components
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
from a2a.native_a2a_node import create_native_a2a_node

# Load environment variables
project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

def load_config():
    """Load configuration from config.json"""
    local_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    if os.path.exists(local_config_path):
        with open(local_config_path, 'r') as f:
            return json.load(f)
    
    main_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'config.json')
    with open(main_config_path, 'r') as f:
        return json.load(f)

def main():
    """Start native A2A agent server"""
    
    # Initialize agent with simplified prompt
    simplified_prompt = """You are Lyra, an AI prompt optimization specialist. 
    You help users improve their prompts to get better AI responses.
    For any user request, provide a brief, helpful response about prompt optimization."""
    
    try:
        memory_tool_agent = IsekAgent(
            name="LV9-Agent",
            model=OpenAIModel(
                model_id=os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini"),
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL")
            ),
            tools=[calculator_tools],
            memory=SimpleMemory(),
            description=simplified_prompt,
            debug_mode=False
        )
        print("Agent initialized.")
    except Exception as e:
        print(f"Error initializing agent: {e}")
        log.error(f"Agent initialization failed: {e}")
        raise

    # Create agent team
    agent_team = IsekTeam(
        name="Lyra the AI Prompt Optimizer",
        description="A master-level AI prompt optimization specialist.",
        members=[memory_tool_agent]
    )

    try:
        # Load configuration
        config = load_config()
        
        # Create etcd registry from config
        etcd_registry = EtcdRegistry(
            host=config["registry"]["host"], 
            port=config["registry"]["port"]
        )
        
        print(f"Starting Native A2A Lyra Agent Server...")
        print(f"Node ID: {config['node_id']}")
        print(f"Port: {config['port']}")
        print(f"Registry: {config['registry']['host']}:{config['registry']['port']}")
        print(f"Protocol: Native A2A")
        log.info("Native A2A Lyra Agent server is starting up...")
        
        # Create native A2A server node - NO ADAPTER NEEDED!
        server_node = create_native_a2a_node(
            agent_team=agent_team,  # Pass agent team directly
            host="localhost",
            port=config["port"],
            node_id=config["node_id"],
            registry=etcd_registry
        )

        # Start the server in the foreground
        server_node.build_server(daemon=False)
        
    except Exception as e:
        log.error(f"Failed to start Native A2A Lyra Agent server: {e}")
        raise

if __name__ == "__main__":
    main()
```

## Migration Checklist

### Pre-Migration Verification
- [ ] Verify A2A SDK is installed: `pip list | grep a2a`
- [ ] Backup current working implementation
- [ ] Test current functionality before migration

### Migration Steps
- [ ] Update import statements to include native A2A components
- [ ] Replace `Node()` instantiation with `create_native_a2a_node()`
- [ ] Remove `SessionAdapter` and `EnhancedSessionAdapter` references
- [ ] Pass `agent_team` directly to native node
- [ ] Update configuration if needed

### Post-Migration Testing
- [ ] Verify server starts without errors
- [ ] Test basic agent team functionality
- [ ] Verify A2A protocol compliance
- [ ] Test enhanced features (agent discovery, task delegation)
- [ ] Performance comparison with previous implementation

## Key Benefits of Native A2A

### 1. **Protocol Compliance**
- Fully compliant with Google A2A protocol v0.2
- Proper JSON-RPC 2.0 over HTTP(S) implementation
- Native agent card support

### 2. **Enhanced Capabilities**
- Automatic agent discovery
- Advanced task management with lifecycle tracking
- Cross-agent session management and migration
- Native streaming support

### 3. **Better Performance**
- Eliminates JSON string parsing overhead
- Direct A2A object manipulation
- Optimized communication patterns

### 4. **Simplified Architecture**
- No need for adapters and JSON parsing
- Direct agent team integration
- Reduced code complexity

## Advanced Usage

### Custom Agent Cards
```python
# The native node automatically generates enhanced agent cards
node = create_native_a2a_node(agent_team=agent_team, ...)
card = node.get_a2a_agent_card()

# Card includes:
# - Dynamic skill discovery
# - Capability introspection  
# - Performance metrics
# - Real-time status
```

### Task Delegation
```python
# Delegate complex tasks to specialized agents
result = await node.delegate_task_to_agent(
    task_type="image_generation",
    task_data={
        "prompt": "Create a logo for my startup",
        "style": "modern",
        "format": "PNG"
    },
    target_agent_id="image_specialist_agent"
)
```

### Session Migration
```python
# Sessions automatically migrate when tasks are delegated
# Agent A starts conversation -> delegates to Agent B -> Agent B continues with full context
```

## Troubleshooting

### Common Issues

1. **A2A SDK Not Available**
   ```
   Error: A2A SDK not available. Install with: pip install a2a-sdk
   ```
   Solution: Install the A2A SDK

2. **Import Errors**
   ```
   ImportError: cannot import name 'create_native_a2a_node'
   ```
   Solution: Ensure the A2A directory is in the correct path

3. **Port Conflicts**
   ```
   Error: Port already in use
   ```
   Solution: Check and modify port configuration

### Debug Mode
Enable debug logging for troubleshooting:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Conclusion

The native A2A implementation provides a significant upgrade to ISEK nodes, offering:
- Better protocol compliance
- Enhanced agent communication
- Advanced task and session management
- Improved performance
- Simplified architecture

The migration is straightforward and provides immediate benefits with minimal code changes.