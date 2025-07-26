"""
验证ISEK Node的A2A消息处理
测试我们的UnifiedIsekAdapter是否能正确处理A2A协议消息
"""

import os
import sys
import json
import asyncio
import time
from typing import Dict, Any
from dotenv import load_dotenv

# Add paths for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from isek.agent.isek_agent import IsekAgent
from isek.models.openai import OpenAIModel
from isek.tools.calculator import calculator_tools
from isek.memory.memory import Memory as SimpleMemory
from isek.node.node_v2 import Node
from isek.team.isek_team import IsekTeam
from isek.utils.log import log
from isek.node.etcd_registry import EtcdRegistry

from adapter.isek_adapter import UnifiedIsekAdapter

# Load environment variables
project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)


class A2AIntegrationTester:
    """A2A集成测试器"""
    
    def __init__(self):
        self.test_results = {}
        
    def load_test_config(self):
        """加载测试配置"""
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # 使用测试端口避免冲突
        config['port'] = 8082
        config['p2p_server_port'] = 9002
        config['node_id'] = 'a2a-test-node'
        
        return config
    
    def create_test_team(self):
        """创建测试团队"""
        print("📝 Creating test team...")
        
        # 简化的测试prompt
        test_prompt = """You are a test agent for A2A protocol validation.
        Respond briefly to any message with 'A2A Test Response: [user message]'"""
        
        try:
            # 创建测试agent
            test_agent = IsekAgent(
                name="A2A-Test-Agent",
                model=OpenAIModel(
                    model_id=os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini"),
                    api_key=os.getenv("OPENAI_API_KEY"),
                    base_url=os.getenv("OPENAI_BASE_URL")
                ),
                tools=[calculator_tools],
                memory=SimpleMemory(),
                description=test_prompt,
                debug_mode=False
            )
            
            # 创建团队
            test_team = IsekTeam(
                name="A2A Test Team",
                description="Team for testing A2A protocol integration",
                members=[test_agent]
            )
            
            print("✅ Test team created successfully")
            return test_team
            
        except Exception as e:
            print(f"❌ Failed to create test team: {e}")
            raise
    
    async def test_adapter_compatibility(self):
        """测试适配器兼容性"""
        print("\n🔧 Testing adapter compatibility...")
        
        try:
            # 创建测试团队
            test_team = self.create_test_team()
            
            # 创建UnifiedIsekAdapter
            adapter = UnifiedIsekAdapter(
                isek_team=test_team,
                enable_streaming=False
            )
            
            # 测试ISEK基础接口
            print("   Testing ISEK base interface...")
            
            # 1. 测试run()方法
            test_message = "Hello, this is a test message"
            result = adapter.run(prompt=test_message)
            
            if result and isinstance(result, str):
                print(f"   ✅ run() method works: {result[:50]}...")
                self.test_results['run_method'] = True
            else:
                print(f"   ❌ run() method failed: {result}")
                self.test_results['run_method'] = False
            
            # 2. 测试get_adapter_card()方法
            adapter_card = adapter.get_adapter_card()
            
            if adapter_card and hasattr(adapter_card, 'name'):
                print(f"   ✅ get_adapter_card() works: {adapter_card.name}")
                self.test_results['adapter_card'] = True
            else:
                print(f"   ❌ get_adapter_card() failed: {adapter_card}")
                self.test_results['adapter_card'] = False
            
            # 3. 测试A2A增强接口
            print("   Testing A2A enhanced interface...")
            
            # 测试异步方法
            async def test_async():
                context = {
                    "task_id": "test_task_123",
                    "session_id": "test_session_456", 
                    "user_input": "Test A2A message",
                    "message": None,
                    "current_task": None
                }
                
                events = []
                try:
                    async for event in adapter.execute_async(context):
                        events.append(event)
                        print(f"   🔍 Debug event: {type(event).__name__}")
                        if hasattr(event, 'message'):
                            print(f"   🔍 Debug error message: {event.message}")
                        if hasattr(event, 'code'):
                            print(f"   🔍 Debug error code: {event.code}")
                        if hasattr(event, 'data'):
                            print(f"   🔍 Debug error data: {event.data}")
                        if len(events) >= 3:  # 限制事件数量避免无限循环
                            break
                except Exception as e:
                    print(f"   🔍 Debug exception: {e}")
                    import traceback
                    traceback.print_exc()
                
                return events
            
            # 运行异步测试
            events = await test_async()
            
            if events:
                print(f"   ✅ execute_async() works: {len(events)} events generated")
                self.test_results['execute_async'] = True
                
                # 检查事件类型
                event_types = [type(event).__name__ for event in events]
                print(f"   Event types: {event_types}")
            else:
                print("   ❌ execute_async() failed: no events generated")
                self.test_results['execute_async'] = False
            
            print("✅ Adapter compatibility test completed")
            
        except Exception as e:
            print(f"❌ Adapter compatibility test failed: {e}")
            self.test_results['adapter_compatibility'] = False
            raise
    
    async def test_node_integration(self):
        """测试Node集成"""
        print("\n🌐 Testing Node integration...")
        
        try:
            # 创建测试团队和适配器
            test_team = self.create_test_team()
            adapter = UnifiedIsekAdapter(
                isek_team=test_team,
                enable_streaming=False
            )
            
            # 加载配置
            config = self.load_test_config()
            
            # 创建etcd注册中心（可选）
            try:
                etcd_registry = EtcdRegistry(
                    host=config.get("registry", {}).get("host", "localhost"),
                    port=config.get("registry", {}).get("port", 2379)
                )
                print("   ✅ ETCD registry created")
            except Exception as e:
                print(f"   ⚠️ ETCD registry failed, using None: {e}")
                etcd_registry = None
            
            # 创建Node
            print(f"   Creating Node on port {config['port']}...")
            test_node = Node(
                node_id=config["node_id"],
                port=config["port"],
                adapter=adapter,
                registry=etcd_registry
            )
            
            print("   ✅ Node created successfully")
            
            # 测试适配器调用
            print("   Testing adapter call through node...")
            test_response = test_node.adapter.run("Test message for node integration")
            
            if test_response:
                print(f"   ✅ Node adapter call works: {test_response[:50]}...")
                self.test_results['node_integration'] = True
            else:
                print("   ❌ Node adapter call failed")
                self.test_results['node_integration'] = False
            
            print("✅ Node integration test completed")
            
        except Exception as e:
            print(f"❌ Node integration test failed: {e}")
            self.test_results['node_integration'] = False
            raise
    
    async def test_a2a_message_flow(self):
        """测试A2A消息流程"""
        print("\n💬 Testing A2A message flow...")
        
        try:
            # 创建适配器
            test_team = self.create_test_team()
            adapter = UnifiedIsekAdapter(
                isek_team=test_team,
                enable_streaming=False
            )
            
            # 模拟A2A消息上下文
            a2a_context = {
                "task_id": "a2a_test_task_789",
                "session_id": "a2a_test_session_101",
                "user_input": "Test A2A message processing",
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Test A2A message processing"}],
                    "messageId": "test_msg_123"
                },
                "current_task": None
            }
            
            print("   Processing A2A message...")
            
            # 收集所有事件
            events = []
            async for event in adapter.execute_async(a2a_context):
                events.append(event)
                print(f"   📨 Event: {type(event).__name__}")
                
                # 检查是否有文本消息
                if hasattr(event, 'text') or hasattr(event, 'content'):
                    content = getattr(event, 'text', getattr(event, 'content', ''))
                    if content:
                        print(f"   💬 Content: {content[:100]}...")
                        
                # 检查是否是错误事件
                if hasattr(event, 'message') and hasattr(event, 'code'):
                    print(f"   ❌ Error: {event.message}")
                    print(f"   🔍 Code: {event.code}")
                    if hasattr(event, 'data'):
                        print(f"   📊 Data: {event.data}")
                
                # 限制事件数量
                if len(events) >= 5:
                    break
            
            if events:
                print(f"   ✅ A2A message flow works: {len(events)} events processed")
                self.test_results['a2a_message_flow'] = True
                
                # 分析事件类型
                event_summary = {}
                for event in events:
                    event_type = type(event).__name__
                    event_summary[event_type] = event_summary.get(event_type, 0) + 1
                
                print(f"   Event summary: {event_summary}")
            else:
                print("   ❌ A2A message flow failed: no events generated")
                self.test_results['a2a_message_flow'] = False
            
            print("✅ A2A message flow test completed")
            
        except Exception as e:
            print(f"❌ A2A message flow test failed: {e}")
            self.test_results['a2a_message_flow'] = False
            raise
    
    async def test_session_management(self):
        """测试会话管理"""
        print("\n💾 Testing session management...")
        
        try:
            test_team = self.create_test_team()
            adapter = UnifiedIsekAdapter(
                isek_team=test_team,
                enable_streaming=False
            )
            
            # 测试会话创建和管理
            session_id = "test_session_999"
            
            # 创建会话上下文
            session_context = adapter.session_manager.create_session_context(session_id)
            
            if session_context and session_context.get('session_id') == session_id:
                print("   ✅ Session creation works")
                self.test_results['session_creation'] = True
            else:
                print("   ❌ Session creation failed")
                self.test_results['session_creation'] = False
            
            # 测试对话记录保存
            adapter.session_manager.save_conversation_turn(
                session_id, 
                "Test user input", 
                "Test agent response"
            )
            
            # 获取对话历史
            history = adapter.session_manager.get_conversation_history(session_id)
            
            if history and len(history) > 0:
                print(f"   ✅ Conversation history works: {len(history)} turns")
                self.test_results['conversation_history'] = True
            else:
                print("   ❌ Conversation history failed")
                self.test_results['conversation_history'] = False
            
            print("✅ Session management test completed")
            
        except Exception as e:
            print(f"❌ Session management test failed: {e}")
            self.test_results['session_management'] = False
            raise
    
    def print_test_summary(self):
        """打印测试摘要"""
        print("\n" + "="*60)
        print("📊 A2A Integration Test Summary")
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
            print("\n🎉 All tests passed! A2A integration is working correctly.")
        else:
            print(f"\n⚠️ {total_tests - passed_tests} test(s) failed. Please check the implementation.")


async def main():
    """主测试函数"""
    print("🚀 Starting A2A Integration Tests")
    print("="*60)
    
    tester = A2AIntegrationTester()
    
    try:
        # 运行所有测试
        await tester.test_adapter_compatibility()
        await tester.test_node_integration()
        await tester.test_a2a_message_flow()
        await tester.test_session_management()
        
    except Exception as e:
        print(f"❌ Critical test failure: {e}")
    
    finally:
        # 打印测试摘要
        tester.print_test_summary()


if __name__ == "__main__":
    asyncio.run(main())