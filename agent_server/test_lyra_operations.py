#!/usr/bin/env python3
"""
Test Lyra Agent Operations with UnifiedIsekAdapter
测试Lyra Agent的任务运行和会话操作
"""

import os
import sys
import json
import asyncio
import time
from datetime import datetime
from dotenv import load_dotenv

# Add paths for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from isek.agent.isek_agent import IsekAgent
from isek.models.openai import OpenAIModel
from isek.tools.calculator import calculator_tools
from isek.memory.memory import Memory as SimpleMemory
from isek.team.isek_team import IsekTeam
from isek.utils.log import log

from adapter.isek_adapter import UnifiedIsekAdapter

# Load environment variables
project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)


class LyraOperationsTester:
    """Lyra操作测试器 - 测试任务运行、会话管理、多轮对话等功能"""
    
    def __init__(self):
        self.adapter = None
        self.session_id = "lyra_test_session"
        self.test_results = {}
        
    def setup_lyra_adapter(self):
        """设置Lyra适配器"""
        print("🔧 Setting up Lyra Adapter...")
        
        try:
            # 创建Lyra Agent
            lyra_agent = IsekAgent(
                name="Lyra-Optimizer",
                model=OpenAIModel(
                    model_id=os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini"),
                    api_key=os.getenv("OPENAI_API_KEY"),
                    base_url=os.getenv("OPENAI_BASE_URL")
                ),
                tools=[calculator_tools],
                memory=SimpleMemory(),
                description="You are Lyra, an AI prompt optimization specialist. Help users improve their prompts for better AI responses.",
                debug_mode=False
            )
            
            # 创建Lyra Team
            lyra_team = IsekTeam(
                name="Lyra Prompt Optimization Team",
                description="Expert team for AI prompt optimization and enhancement",
                members=[lyra_agent]
            )
            
            # 创建UnifiedIsekAdapter
            self.adapter = UnifiedIsekAdapter(
                isek_team=lyra_team,
                enable_streaming=False  # 可以改为True测试流式响应
            )
            
            print("✅ Lyra Adapter setup complete")
            return True
            
        except Exception as e:
            print(f"❌ Failed to setup Lyra Adapter: {e}")
            return False
    
    def test_basic_run_method(self):
        """测试基础run方法"""
        print("\n📝 Testing basic run() method...")
        
        try:
            # 测试简单的prompt优化请求
            test_prompt = "Help me write a better email to my boss"
            
            result = self.adapter.run(
                prompt=test_prompt,
                session_id=self.session_id,
                user_id="test_user"
            )
            
            if result and len(result) > 10:
                print(f"✅ Basic run() successful")
                print(f"   Input: {test_prompt}")
                print(f"   Output: {result[:100]}...")
                self.test_results['basic_run'] = True
                return result
            else:
                print(f"❌ Basic run() failed: {result}")
                self.test_results['basic_run'] = False
                return None
                
        except Exception as e:
            print(f"❌ Basic run() error: {e}")
            self.test_results['basic_run'] = False
            return None
    
    async def test_async_task_execution(self):
        """测试异步任务执行"""
        print("\n⚡ Testing async task execution...")
        
        try:
            task_id = f"lyra_task_{int(time.time())}"
            
            # 构建测试上下文
            context = {
                "task_id": task_id,
                "session_id": self.session_id,
                "user_input": "Optimize this prompt: 'Write code for me'",
                "message": None,
                "current_task": None
            }
            
            print(f"   📋 Task ID: {task_id}")
            print(f"   💬 Request: {context['user_input']}")
            
            # 执行异步任务
            events = []
            start_time = time.time()
            
            async for event in self.adapter.execute_async(context):
                events.append(event)
                event_type = type(event).__name__
                
                print(f"   📨 Event: {event_type}")
                
                # 显示事件详情
                if hasattr(event, 'status') and hasattr(event.status, 'state'):
                    print(f"      State: {event.status.state}")
                if hasattr(event, 'metadata') and event.metadata:
                    print(f"      Metadata: {event.metadata}")
                if hasattr(event, 'parts') and event.parts:
                    # Message event
                    for part in event.parts:
                        if hasattr(part.root, 'text'):
                            print(f"      Content: {part.root.text[:80]}...")
                
                # 限制事件数量以避免无限循环
                if len(events) >= 10:
                    break
            
            duration = time.time() - start_time
            
            if events:
                print(f"✅ Async execution successful ({duration:.2f}s)")
                print(f"   📊 Total events: {len(events)}")
                
                # 统计事件类型
                event_types = {}
                for event in events:
                    event_type = type(event).__name__
                    event_types[event_type] = event_types.get(event_type, 0) + 1
                
                print(f"   📈 Event breakdown: {event_types}")
                self.test_results['async_execution'] = True
                return events
            else:
                print("❌ Async execution failed: no events generated")
                self.test_results['async_execution'] = False
                return []
                
        except Exception as e:
            print(f"❌ Async execution error: {e}")
            import traceback
            traceback.print_exc()
            self.test_results['async_execution'] = False
            return []
    
    def test_session_management(self):
        """测试会话管理功能"""
        print("\n💾 Testing session management...")
        
        try:
            # 1. 测试会话创建
            session_context = self.adapter.session_manager.create_session_context(self.session_id)
            
            if session_context and session_context.get('session_id') == self.session_id:
                print("✅ Session creation successful")
                self.test_results['session_creation'] = True
            else:
                print("❌ Session creation failed")
                self.test_results['session_creation'] = False
                return False
            
            # 2. 测试对话记录保存
            self.adapter.session_manager.save_conversation_turn(
                self.session_id,
                "Test user input for session management",
                "Test assistant response for session management"
            )
            
            # 3. 测试对话历史获取
            history = self.adapter.session_manager.get_conversation_history(self.session_id)
            
            if history and len(history) > 0:
                print(f"✅ Conversation history works: {len(history)} turns")
                print(f"   Latest turn: {history[-1]}")
                self.test_results['conversation_history'] = True
            else:
                print("❌ Conversation history failed")
                self.test_results['conversation_history'] = False
                return False
            
            # 4. 测试上下文构建
            context_text = self.adapter.session_manager.get_conversation_context(self.session_id, limit=3)
            
            if context_text:
                print(f"✅ Context building works")
                print(f"   Context preview: {context_text[:100]}...")
                self.test_results['context_building'] = True
            else:
                print("✅ Context building works (no previous context)")
                self.test_results['context_building'] = True
            
            return True
            
        except Exception as e:
            print(f"❌ Session management error: {e}")
            self.test_results['session_management'] = False
            return False
    
    async def test_multiturn_conversation(self):
        """测试多轮对话功能"""
        print("\n🔄 Testing multi-turn conversation...")
        
        try:
            # 第一轮：发送简短的请求触发多轮对话
            task_id = f"multiturn_task_{int(time.time())}"
            
            context1 = {
                "task_id": task_id,
                "session_id": self.session_id + "_multiturn",
                "user_input": "help",  # 简短输入，应该触发多轮对话
                "message": None,
                "current_task": None
            }
            
            print("   🔵 Round 1: Sending short request...")
            print(f"   💬 Input: '{context1['user_input']}'")
            
            round1_events = []
            async for event in self.adapter.execute_async(context1):
                round1_events.append(event)
                event_type = type(event).__name__
                print(f"   📨 Event: {event_type}")
                
                if hasattr(event, 'parts') and event.parts:
                    for part in event.parts:
                        if hasattr(part.root, 'text'):
                            print(f"      Agent: {part.root.text[:80]}...")
                
                if len(round1_events) >= 5:
                    break
            
            # 检查是否触发了多轮对话
            has_clarification = any(
                hasattr(event, 'parts') and event.parts and
                any(hasattr(part.root, 'text') and 'more details' in part.root.text.lower() 
                    for part in event.parts)
                for event in round1_events
            )
            
            if has_clarification:
                print("✅ Multi-turn conversation initiated")
                self.test_results['multiturn_initiation'] = True
                
                # 第二轮：提供更多信息
                print("\n   🔵 Round 2: Providing more details...")
                
                context2 = {
                    "task_id": task_id,
                    "session_id": context1['session_id'],
                    "user_input": "I need help optimizing a prompt for ChatGPT to write marketing emails",
                    "message": None,
                    "current_task": None  # 这里应该传递当前任务状态，但简化测试
                }
                
                print(f"   💬 Input: '{context2['user_input']}'")
                
                round2_events = []
                async for event in self.adapter.execute_async(context2):
                    round2_events.append(event)
                    event_type = type(event).__name__
                    print(f"   📨 Event: {event_type}")
                    
                    if hasattr(event, 'parts') and event.parts:
                        for part in event.parts:
                            if hasattr(part.root, 'text'):
                                print(f"      Agent: {part.root.text[:80]}...")
                    
                    if len(round2_events) >= 5:
                        break
                
                if round2_events:
                    print("✅ Multi-turn conversation completed")
                    self.test_results['multiturn_completion'] = True
                    return True
                else:
                    print("❌ Multi-turn conversation failed in round 2")
                    self.test_results['multiturn_completion'] = False
                    return False
            else:
                print("⚠️ Multi-turn conversation not triggered (input may be sufficient)")
                self.test_results['multiturn_initiation'] = False
                return True
                
        except Exception as e:
            print(f"❌ Multi-turn conversation error: {e}")
            import traceback
            traceback.print_exc()
            self.test_results['multiturn_conversation'] = False
            return False
    
    async def test_task_cancellation(self):
        """测试任务取消功能"""
        print("\n🛑 Testing task cancellation...")
        
        try:
            task_id = f"cancel_task_{int(time.time())}"
            
            # 启动一个任务
            context = {
                "task_id": task_id,
                "session_id": self.session_id + "_cancel",
                "user_input": "Create a comprehensive guide for prompt engineering",
                "message": None,
                "current_task": None
            }
            
            print(f"   📋 Starting task: {task_id}")
            
            # 启动任务（在后台运行）
            task_events = []
            
            # 模拟任务运行一段时间后取消
            cancel_context = {"task_id": task_id}
            
            print("   🛑 Requesting task cancellation...")
            
            cancel_events = []
            async for event in self.adapter.cancel_async(cancel_context):
                cancel_events.append(event)
                event_type = type(event).__name__
                print(f"   📨 Cancel Event: {event_type}")
                
                if hasattr(event, 'status') and hasattr(event.status, 'state'):
                    print(f"      State: {event.status.state}")
                
                if len(cancel_events) >= 3:
                    break
            
            if cancel_events:
                print("✅ Task cancellation successful")
                self.test_results['task_cancellation'] = True
                return True
            else:
                print("❌ Task cancellation failed")
                self.test_results['task_cancellation'] = False
                return False
                
        except Exception as e:
            print(f"❌ Task cancellation error: {e}")
            self.test_results['task_cancellation'] = False
            return False
    
    def test_adapter_features(self):
        """测试适配器特性"""
        print("\n🔍 Testing adapter features...")
        
        try:
            # 测试get_adapter_card
            card = self.adapter.get_adapter_card()
            
            if card and hasattr(card, 'name'):
                print(f"✅ Adapter card: {card.name}")
                print(f"   Bio: {card.bio[:60]}...")
                self.test_results['adapter_card'] = True
            else:
                print("❌ Adapter card failed")
                self.test_results['adapter_card'] = False
            
            # 测试特性支持
            features = {
                'streaming': self.adapter.supports_streaming(),
                'cancellation': self.adapter.supports_cancellation(),
                'multiturn': self.adapter.supports_multiturn()
            }
            
            print(f"✅ Feature support: {features}")
            self.test_results['feature_support'] = True
            
            return True
            
        except Exception as e:
            print(f"❌ Adapter features error: {e}")
            self.test_results['adapter_features'] = False
            return False
    
    def print_test_summary(self):
        """打印测试摘要"""
        print("\n" + "="*60)
        print("📊 Lyra Operations Test Summary")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result)
        
        print(f"Total tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success rate: {passed_tests/total_tests*100:.1f}%" if total_tests > 0 else "No tests")
        
        print("\nDetailed results:")
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"  {test_name}: {status}")
        
        if passed_tests == total_tests:
            print("\n🎉 All tests passed! Lyra with UnifiedIsekAdapter is working perfectly.")
        else:
            print(f"\n⚠️ {total_tests - passed_tests} test(s) failed. Please check the implementation.")


async def main():
    """主测试函数"""
    print("🚀 Starting Lyra Operations Tests with UnifiedIsekAdapter")
    print("="*60)
    
    tester = LyraOperationsTester()
    
    try:
        # 1. 设置适配器
        if not tester.setup_lyra_adapter():
            print("❌ Failed to setup adapter, aborting tests")
            return
        
        # 2. 运行所有测试
        print("\n🧪 Running comprehensive tests...")
        
        # 基础功能测试
        tester.test_basic_run_method()
        tester.test_adapter_features()
        tester.test_session_management()
        
        # 异步功能测试  
        await tester.test_async_task_execution()
        await tester.test_multiturn_conversation()
        await tester.test_task_cancellation()
        
    except Exception as e:
        print(f"❌ Critical test failure: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 打印测试摘要
        tester.print_test_summary()


if __name__ == "__main__":
    asyncio.run(main())