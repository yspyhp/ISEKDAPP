#!/usr/bin/env python3
"""
Interactive Lyra Session
与Lyra进行交互式对话，测试各种prompt优化场景
"""

import os
import sys
import asyncio
import uuid
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


class InteractiveLyra:
    """交互式Lyra会话"""
    
    def __init__(self):
        self.adapter = None
        self.session_id = f"interactive_{str(uuid.uuid4())[:8]}"
        self.running = True
        
    def setup(self):
        """初始化Lyra系统"""
        print("🔧 Initializing Lyra AI Prompt Optimizer...")
        
        try:
            # 创建Lyra Agent
            lyra_agent = IsekAgent(
                name="Lyra-Interactive",
                model=OpenAIModel(
                    model_id=os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini"),
                    api_key=os.getenv("OPENAI_API_KEY"),
                    base_url=os.getenv("OPENAI_BASE_URL")
                ),
                tools=[calculator_tools],
                memory=SimpleMemory(),
                description="""
You are Lyra, a master-level AI prompt optimization specialist. 

Your role:
1. Analyze user prompts for clarity, specificity, and effectiveness
2. Provide optimized versions with clear improvements
3. Explain why each change makes the prompt better
4. Offer practical tips for prompt engineering

Always respond in this format:
**Your Optimized Prompt:**
[Enhanced version]

**Key Improvements:**
• [Specific changes made]

**Pro Tip:** [Additional guidance]
                """,
                debug_mode=False
            )
            
            # 创建Team
            lyra_team = IsekTeam(
                name="Interactive Lyra Team",
                description="Interactive AI prompt optimization specialist",
                members=[lyra_agent]
            )
            
            # 创建UnifiedIsekAdapter
            self.adapter = UnifiedIsekAdapter(
                isek_team=lyra_team,
                enable_streaming=False
            )
            
            print("✅ Lyra is ready!")
            return True
            
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            return False
    
    def print_welcome(self):
        """打印欢迎信息"""
        print("\n" + "="*60)
        print("🎭 Welcome to Interactive Lyra Session")
        print("="*60)
        print("I'm Lyra, your AI prompt optimization specialist!")
        print()
        print("💡 What I can help you with:")
        print("   • Optimize your AI prompts for better results")
        print("   • Explain why certain prompt structures work better")
        print("   • Provide tips for effective prompt engineering")
        print()
        print("📝 How to use:")
        print("   • Type your prompt that needs optimization")
        print("   • Type 'async [prompt]' for async task execution")
        print("   • Type 'history' to see conversation history")
        print("   • Type 'help' for more commands")
        print("   • Type 'quit' to exit")
        print()
        print(f"🔗 Session ID: {self.session_id}")
        print("="*60)
    
    def print_help(self):
        """打印帮助信息"""
        print("\n📖 Available Commands:")
        print("   • [your prompt] - Get prompt optimization")
        print("   • async [prompt] - Use async execution (shows task progress)")
        print("   • history - Show conversation history")
        print("   • context - Show current session context")
        print("   • features - Show adapter capabilities")
        print("   • clear - Clear session history")
        print("   • help - Show this help")
        print("   • quit - Exit session")
        print()
        print("💡 Example prompts to optimize:")
        print("   • 'Write code for me'")
        print("   • 'Help with my resume'")
        print("   • 'Create a marketing email'")
        print("   • 'Explain machine learning'")
    
    def show_history(self):
        """显示对话历史"""
        history = self.adapter.session_manager.get_conversation_history(self.session_id)
        
        if not history:
            print("📚 No conversation history yet.")
            return
            
        print(f"\n📚 Conversation History ({len(history)} turns):")
        print("-" * 40)
        
        for i, turn in enumerate(history, 1):
            print(f"{i}. User: {turn.user_input}")
            print(f"   Lyra: {turn.agent_response[:100]}{'...' if len(turn.agent_response) > 100 else ''}")
            print()
    
    def show_context(self):
        """显示会话上下文"""
        context_text = self.adapter.session_manager.get_conversation_context(self.session_id, limit=3)
        
        if context_text:
            print(f"\n🧠 Current Session Context:")
            print("-" * 40)
            print(context_text)
            print("-" * 40)
        else:
            print("🧠 No session context available yet.")
    
    def show_features(self):
        """显示适配器功能"""
        card = self.adapter.get_adapter_card()
        
        print(f"\n🔍 Adapter Information:")
        print(f"   Name: {card.name}")
        print(f"   Bio: {card.bio}")
        
        features = {
            "Streaming": self.adapter.supports_streaming(),
            "Cancellation": self.adapter.supports_cancellation(),
            "Multi-turn": self.adapter.supports_multiturn()
        }
        
        print(f"\n🚀 Supported Features:")
        for feature, supported in features.items():
            status = "✅" if supported else "❌"
            print(f"   {status} {feature}")
    
    def clear_history(self):
        """清除会话历史"""
        # 重新生成session_id来模拟清除历史
        old_session = self.session_id
        self.session_id = f"interactive_{str(uuid.uuid4())[:8]}"
        print(f"🗑️ Session history cleared. New session: {self.session_id}")
    
    async def handle_async_request(self, user_input):
        """处理异步请求"""
        task_id = f"task_{str(uuid.uuid4())[:8]}"
        
        context = {
            "task_id": task_id,
            "session_id": self.session_id,
            "user_input": user_input,
            "message": None,
            "current_task": None
        }
        
        print(f"\n⚡ Processing async task: {task_id}")
        print("🔄 Task progress:")
        
        events = []
        async for event in self.adapter.execute_async(context):
            events.append(event)
            event_type = type(event).__name__
            
            if event_type == "TaskStatusUpdateEvent":
                if hasattr(event, 'status') and hasattr(event.status, 'state'):
                    print(f"   📊 {event.status.state}")
                if hasattr(event, 'metadata') and event.metadata:
                    if 'current_step' in event.metadata:
                        print(f"   🔄 {event.metadata['current_step']}")
                        
            elif event_type == "Message":
                if hasattr(event, 'parts') and event.parts:
                    for part in event.parts:
                        if hasattr(part.root, 'text'):
                            print(f"\n🎯 Lyra's Response:")
                            print("-" * 40)
                            print(part.root.text)
                            print("-" * 40)
            
            if len(events) >= 10:
                break
        
        print(f"✅ Task completed ({len(events)} events)")
    
    def handle_sync_request(self, user_input):
        """处理同步请求"""
        print("\n🔄 Processing with Lyra...")
        
        result = self.adapter.run(
            prompt=f"Please optimize this prompt: '{user_input}'",
            session_id=self.session_id,
            user_id="interactive_user"
        )
        
        print(f"\n🎯 Lyra's Response:")
        print("-" * 40)
        print(result)
        print("-" * 40)
    
    async def run(self):
        """运行交互式会话"""
        if not self.setup():
            return
            
        self.print_welcome()
        
        while self.running:
            try:
                user_input = input("\n💬 You: ").strip()
                
                if not user_input:
                    continue
                    
                # 处理命令
                if user_input.lower() == 'quit':
                    self.running = False
                    print("👋 Thanks for using Lyra! Goodbye!")
                    break
                    
                elif user_input.lower() == 'help':
                    self.print_help()
                    
                elif user_input.lower() == 'history':
                    self.show_history()
                    
                elif user_input.lower() == 'context':
                    self.show_context()
                    
                elif user_input.lower() == 'features':
                    self.show_features()
                    
                elif user_input.lower() == 'clear':
                    self.clear_history()
                    
                elif user_input.lower().startswith('async '):
                    # 异步执行
                    prompt = user_input[6:]  # 移除 'async ' 前缀
                    if prompt:
                        await self.handle_async_request(prompt)
                    else:
                        print("❌ Please provide a prompt after 'async'")
                        
                else:
                    # 正常的prompt优化请求
                    self.handle_sync_request(user_input)
                    
            except KeyboardInterrupt:
                print("\n👋 Session interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                print("Type 'help' for available commands.")


async def main():
    """主函数"""
    interactive = InteractiveLyra()
    await interactive.run()


if __name__ == "__main__":
    asyncio.run(main())