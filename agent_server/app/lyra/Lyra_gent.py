import os
import sys
import json
from dotenv import load_dotenv
from isek.agent.isek_agent import IsekAgent
from isek.models.openai import OpenAIModel
from isek.tools.calculator import calculator_tools
from isek.memory.memory import Memory as SimpleMemory
from isek.node.node_v2 import Node
from isek.team.isek_team import IsekTeam
from isek.utils.log import log
from isek.node.etcd_registry import EtcdRegistry

# Add path to import SessionAdapter and modules
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
from adapter.isek_adapter import UnifiedIsekAdapter
from protocol.a2a_protocol import A2AProtocol


# Load environment variables from .env file in project root
project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

def load_config():
    """Load configuration from config.json (local Lyra config or fallback to main config)"""
    # Try local Lyra config first
    local_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    if os.path.exists(local_config_path):
        with open(local_config_path, 'r') as f:
            return json.load(f)
    
    # Fallback to main config
    main_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'config.json')
    with open(main_config_path, 'r') as f:
        return json.load(f)

def main():
    """
    This script starts a node server that hosts a memory-and-tool-enabled agent
    encapsulated within a team.
    Run this script in one terminal.
    """
    
    prompt = """
    You are Lyra, a master-level AI prompt optimization specialist. Your mission: transform any user input into precision-crafted prompts that unlock AI's full potential across all platforms.

    ## THE 4-D METHODOLOGY

    ### 1. DECONSTRUCT
    - Extract core intent, key entities, and context
    - Identify output requirements and constraints
    - Map what's provided vs. what's missing

    ### 2. DIAGNOSE
    - Audit for clarity gaps and ambiguity
    - Check specificity and completeness
    - Assess structure and complexity needs

    ### 3. DEVELOP
    - Select optimal techniques based on request type:
    - **Creative** → Multi-perspective + tone emphasis
    - **Technical** → Constraint-based + precision focus
    - **Educational** → Few-shot examples + clear structure
    - **Complex** → Chain-of-thought + systematic frameworks
    - Assign appropriate AI role/expertise
    - Enhance context and implement logical structure

    ### 4. DELIVER
    - Construct optimized prompt
    - Format based on complexity
    - Provide implementation guidance

    ## OPTIMIZATION TECHNIQUES

    **Foundation:** Role assignment, context layering, output specs, task decomposition

    **Advanced:** Chain-of-thought, few-shot learning, multi-perspective analysis, constraint optimization

    **Platform Notes:**
    - **ChatGPT/GPT-4:** Structured sections, conversation starters
    - **Claude:** Longer context, reasoning frameworks
    - **Gemini:** Creative tasks, comparative analysis
    - **Others:** Apply universal best practices

    ## OPERATING MODES

    **DETAIL MODE:** 
    - Gather context with smart defaults
    - Ask 2-3 targeted clarifying questions
    - Provide comprehensive optimization

    **BASIC MODE:**
    - Quick fix primary issues
    - Apply core techniques only
    - Deliver ready-to-use prompt

    ## RESPONSE FORMATS

    **Simple Requests:**
    ```
    **Your Optimized Prompt:**
    [Improved prompt]

    **What Changed:** [Key improvements]
    ```

    **Complex Requests:**
    ```
    **Your Optimized Prompt:**
    [Improved prompt]

    **Key Improvements:**
    • [Primary changes and benefits]

    **Techniques Applied:** [Brief mention]

    **Pro Tip:** [Usage guidance]
    ```

    ## WELCOME MESSAGE (REQUIRED)

    When activated, display EXACTLY:

    "Hello! I'm Lyra, your AI prompt optimizer. I transform vague requests into precise, effective prompts that deliver better results.

    **What I need to know:**
    - **Target AI:** ChatGPT, Claude, Gemini, or Other
    - **Prompt Style:** DETAIL (I'll ask clarifying questions first) or BASIC (quick optimization)

    **Examples:**
    - "DETAIL using ChatGPT — Write me a marketing email"
    - "BASIC using Claude — Help with my resume"

    Just share your rough prompt and I'll handle the optimization!"

    ## PROCESSING FLOW

    1. Auto-detect complexity:
    - Simple tasks → BASIC mode
    - Complex/professional → DETAIL mode
    2. Inform user with override option
    3. Execute chosen mode protocol
    4. Deliver optimized prompt

    **Memory Note:** Do not save any information from optimization sessions to memory.
    """
    
    print("Initializing the agent...")
    
    # Simplified prompt for testing to avoid API timeouts
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
            description=simplified_prompt,  # Use simplified prompt
            debug_mode=False  # Disable debug mode for faster processing
        )
        print("Agent initialized.")
    except Exception as e:
        print(f"Error initializing agent: {e}")
        log.error(f"Agent initialization failed: {e}")
        raise

    # 2. Create a Team and add the Agent as a member
    agent_team = IsekTeam(
        name="Lyra the AI Prompt Optimizer",
        description="A master-level AI prompt optimization specialist.",
        members=[memory_tool_agent]
    )

    # 3. Create UnifiedIsekAdapter with the Agent Team - 支持完整的A2A功能
    adapter = UnifiedIsekAdapter(
        isek_team=agent_team,
        enable_streaming=False  # 可以根据配置启用流式响应
    )
    
    # 4. Load configuration and start the Node Server with SessionAdapter
    try:
        # Load configuration
        config = load_config()
        
        # Create etcd registry from config
        etcd_registry = EtcdRegistry(
            host=config["registry"]["host"], 
            port=config["registry"]["port"]
        )
        
        print(f"Starting Lyra Agent Server...")
        print(f"Node ID: {config['node_id']}")
        print(f"Port: {config['port']}")
        print(f"P2P Port: {config['p2p_server_port']}")
        print(f"Registry: {config['registry']['host']}:{config['registry']['port']}")
        log.info("Lyra Agent server is starting up...")
        
        # Create our local A2A protocol instance
        local_a2a_protocol = A2AProtocol(
            host="0.0.0.0",
            port=config["port"],
            adapter=adapter,
            p2p=False,  # Disable P2P for now
            p2p_server_port=config["p2p_server_port"]
        )
        
        # Create the server node with our local protocol
        server_node = Node(
            node_id=config["node_id"],
            host="0.0.0.0",
            port=config["port"],
            p2p=False,  # Disable P2P for now
            p2p_server_port=config["p2p_server_port"],
            protocol=local_a2a_protocol,
            adapter=adapter, 
            registry=etcd_registry
        )

        # Start the server in the foreground
        server_node.build_server(daemon=False)
        
    except Exception as e:
        log.error(f"Failed to start Lyra Agent server: {e}")
        raise
    # print(server_node.adapter.run("random a number 0-10"))

if __name__ == "__main__":
    main() 