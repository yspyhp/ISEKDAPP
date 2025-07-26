#!/usr/bin/env python3
"""
Demo: Lyra Agent Usage with UnifiedIsekAdapter
演示：使用新的UnifiedIsekAdapter与Lyra Agent进行实际的prompt优化任务
"""

import os
import sys
import asyncio
import time
from dotenv import load_dotenv

# Add paths for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from isek.agent.isek_agent import IsekAgent
from isek.models.openai import OpenAIModel
from isek.tools.calculator import calculator_tools
from isek.memory.memory import Memory as SimpleMemory
from isek.team.isek_team import IsekTeam

from adapter.isek_adapter import UnifiedIsekAdapter

# Load environment variables
project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)


class LyraDemo:
    """Lyra演示类 - 展示实际的prompt优化场景"""
    
    def __init__(self):
        self.adapter = None
        self.session_id = "demo_session"
        
    def setup_lyra(self):
        """设置Lyra系统"""
        print("🔧 Setting up Lyra AI Prompt Optimizer...")
        
        # 创建Lyra Agent（使用完整的prompt）
        lyra_agent = IsekAgent(
            name="Lyra-Master-Optimizer",
            model=OpenAIModel(
                model_id=os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini"),
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL")
            ),
            tools=[calculator_tools],
            memory=SimpleMemory(),
            description="""
You are Lyra, a master-level AI prompt optimization specialist. Your mission: transform any user input into precision-crafted prompts that unlock AI's full potential.

## OPTIMIZATION APPROACH

1. **Analyze** the user's request for clarity, specificity, and completeness
2. **Identify** gaps in context, constraints, or desired output format
3. **Enhance** with role assignment, structure, and examples when needed
4. **Deliver** optimized prompts with clear improvements explained

## RESPONSE FORMAT

**Your Optimized Prompt:**
[Improved version with specific enhancements]

**Key Improvements:**
• [List main changes and why they help]

**Pro Tip:** [Usage guidance for best results]

Always be helpful, concise, and focused on practical improvements.
            """,
            debug_mode=False
        )
        
        # 创建Team
        lyra_team = IsekTeam(
            name="Lyra Prompt Optimization Team",
            description="Master-level AI prompt optimization specialists",
            members=[lyra_agent]
        )
        
        # 创建UnifiedIsekAdapter
        self.adapter = UnifiedIsekAdapter(
            isek_team=lyra_team,
            enable_streaming=False
        )
        
        print("✅ Lyra system ready!")
        return True
    
    def demo_basic_optimization(self):
        """演示基础prompt优化"""
        print("\n" + "="*60)
        print("📝 Demo 1: Basic Prompt Optimization")
        print("="*60)
        
        # 用户的原始prompt
        original_prompt = "Write code for me"
        
        print(f"💭 Original prompt: '{original_prompt}'")
        print("\n🔄 Processing with Lyra...")
        
        # 使用Lyra优化
        result = self.adapter.run(
            prompt=f"Please optimize this prompt: '{original_prompt}'",
            session_id=self.session_id,
            user_id="demo_user"
        )
        
        print(f"\n🎯 Lyra's optimization:")
        print("-" * 40)
        print(result)
        print("-" * 40)
        
        return result
    
    async def demo_async_workflow(self):
        """演示异步工作流程"""
        print("\n" + "="*60)
        print("⚡ Demo 2: Async Task Workflow")
        print("="*60)
        
        task_id = f"demo_task_{int(time.time())}"
        
        # 构建请求上下文
        context = {
            "task_id": task_id,
            "session_id": self.session_id,
            "user_input": "Help me create a prompt for generating creative marketing copy for a tech startup",
            "message": None,
            "current_task": None
        }
        
        print(f"📋 Task ID: {task_id}")
        print(f"💬 Request: {context['user_input']}")
        print("\n🔄 Processing async...")
        
        # 跟踪任务进度
        events = []
        start_time = time.time()
        
        async for event in self.adapter.execute_async(context):
            events.append(event)
            event_type = type(event).__name__
            
            if event_type == "TaskStatusUpdateEvent":
                state = event.status.state if hasattr(event, 'status') else "unknown"
                print(f"   📊 Status: {state}")
                if hasattr(event, 'metadata') and event.metadata:
                    if 'started_at' in event.metadata:
                        print(f"   ⏰ Started at: {event.metadata['started_at']}")
                    if 'current_step' in event.metadata:
                        print(f"   🔄 Step: {event.metadata['current_step']}")
                        
            elif event_type == "Message":
                if hasattr(event, 'parts') and event.parts:
                    for part in event.parts:
                        if hasattr(part.root, 'text'):
                            print(f"\n🎯 Lyra's Response:")
                            print("-" * 40)
                            print(part.root.text)
                            print("-" * 40)
            
            # 限制事件数量
            if len(events) >= 10:
                break
        
        duration = time.time() - start_time
        print(f"\n✅ Task completed in {duration:.2f} seconds")
        print(f"📈 Total events processed: {len(events)}")
        
        return events
    
    async def demo_multiturn_session(self):
        """演示多轮对话会话"""
        print("\n" + "="*60)
        print("🔄 Demo 3: Multi-turn Conversation")
        print("="*60)
        
        # 第一轮：发送模糊请求
        print("🔵 Round 1: Vague request")
        task_id_1 = f"multiturn_1_{int(time.time())}"
        
        context1 = {
            "task_id": task_id_1,
            "session_id": self.session_id + "_multiturn",
            "user_input": "help with email",
            "message": None,
            "current_task": None
        }
        
        print(f"💬 User: '{context1['user_input']}'")
        print("🔄 Lyra responding...")
        
        round1_events = []
        async for event in self.adapter.execute_async(context1):
            round1_events.append(event)
            
            if hasattr(event, 'parts') and event.parts:
                for part in event.parts:
                    if hasattr(part.root, 'text'):
                        print(f"\n🤖 Lyra: {part.root.text}")
            
            if len(round1_events) >= 5:
                break
        
        # 等待一下模拟用户思考
        await asyncio.sleep(1)
        
        # 第二轮：提供具体信息
        print(f"\n🔵 Round 2: Detailed follow-up")
        task_id_2 = f"multiturn_2_{int(time.time())}"
        
        context2 = {
            "task_id": task_id_2,
            "session_id": context1['session_id'],
            "user_input": "I need to write a professional email to request a meeting with potential investors for my AI startup",
            "message": None,
            "current_task": None
        }
        
        print(f"💬 User: '{context2['user_input']}'")
        print("🔄 Lyra responding...")
        
        round2_events = []
        async for event in self.adapter.execute_async(context2):
            round2_events.append(event)
            
            if hasattr(event, 'parts') and event.parts:
                for part in event.parts:
                    if hasattr(part.root, 'text'):
                        print(f"\n🎯 Lyra: {part.root.text}")
            
            if len(round2_events) >= 5:
                break
        
        print(f"\n✅ Multi-turn conversation completed")
        return round1_events, round2_events
    
    def demo_session_context(self):
        """演示会话上下文功能"""
        print("\n" + "="*60)
        print("💾 Demo 4: Session Context & History")
        print("="*60)
        
        # 显示当前会话历史
        history = self.adapter.session_manager.get_conversation_history(self.session_id)
        
        print(f"📚 Session history: {len(history)} turns")
        
        if history:
            print("\n📝 Recent conversations:")
            for i, turn in enumerate(history[-3:], 1):  # 显示最近3轮
                print(f"   {i}. User: {turn.user_input[:50]}...")
                print(f"      Agent: {turn.agent_response[:50]}...")
        
        # 测试上下文感知
        print(f"\n🧠 Testing context awareness...")
        
        contextual_request = "Can you improve that last prompt even more?"
        
        result = self.adapter.run(
            prompt=contextual_request,
            session_id=self.session_id,
            user_id="demo_user"
        )
        
        print(f"💬 User: '{contextual_request}'")
        print(f"\n🎯 Lyra (with context):")
        print("-" * 40)
        print(result)
        print("-" * 40)
        
        return result
    
    def demo_adapter_capabilities(self):
        """演示适配器能力"""
        print("\n" + "="*60)
        print("🔍 Demo 5: Adapter Capabilities")
        print("="*60)
        
        # 获取适配器信息
        card = self.adapter.get_adapter_card()
        
        print(f"🏷️  Name: {card.name}")
        print(f"📝 Bio: {card.bio}")
        print(f"🧠 Knowledge: {card.knowledge}")
        print(f"⚙️  Routine: {card.routine}")
        
        # 检查支持的功能
        features = {
            "Streaming": self.adapter.supports_streaming(),
            "Cancellation": self.adapter.supports_cancellation(), 
            "Multi-turn": self.adapter.supports_multiturn()
        }
        
        print(f"\n🚀 Supported features:")
        for feature, supported in features.items():
            status = "✅" if supported else "❌"
            print(f"   {status} {feature}")
        
        return card, features


async def main():
    """主演示函数"""
    print("🎭 Lyra AI Prompt Optimizer Demo")
    print("="*60)
    print("Demonstrating task run and session operations with UnifiedIsekAdapter")
    print("="*60)
    
    demo = LyraDemo()
    
    try:
        # 设置系统
        if not demo.setup_lyra():
            print("❌ Failed to setup Lyra system")
            return
        
        # 运行各种演示
        print("\n🚀 Starting demonstrations...")
        
        # 1. 基础优化
        demo.demo_basic_optimization()
        
        # 2. 异步工作流
        await demo.demo_async_workflow()
        
        # 3. 多轮对话
        await demo.demo_multiturn_session()
        
        # 4. 会话上下文
        demo.demo_session_context()
        
        # 5. 适配器能力
        demo.demo_adapter_capabilities()
        
        print("\n🎉 All demonstrations completed successfully!")
        print("\n📊 Summary:")
        print("• Basic prompt optimization ✅")
        print("• Async task execution ✅") 
        print("• Multi-turn conversations ✅")
        print("• Session context awareness ✅")
        print("• A2A protocol compliance ✅")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())