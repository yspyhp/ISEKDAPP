#!/usr/bin/env python3
"""
Quick Test: Verify Lyra with UnifiedIsekAdapter
快速测试：验证Lyra与UnifiedIsekAdapter的集成
"""

import os
import sys
import asyncio

# Add paths for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 简单的功能验证测试
def test_import():
    """测试模块导入"""
    try:
        from adapter.isek_adapter import UnifiedIsekAdapter
        print("✅ UnifiedIsekAdapter import successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_adapter_creation():
    """测试适配器创建"""
    try:
        from adapter.isek_adapter import UnifiedIsekAdapter
        
        # 创建一个模拟的team对象
        class MockTeam:
            def __init__(self):
                self.name = "Mock Team"
                self.description = "Mock team for testing"
            
            def run(self, message, user_id="default", session_id="default"):
                return f"Mock response to: {message}"
        
        mock_team = MockTeam()
        adapter = UnifiedIsekAdapter(isek_team=mock_team, enable_streaming=False)
        
        print("✅ UnifiedIsekAdapter creation successful")
        print(f"   Name: {adapter.get_adapter_card().name}")
        print(f"   Features: streaming={adapter.supports_streaming()}, "
              f"cancellation={adapter.supports_cancellation()}, "
              f"multiturn={adapter.supports_multiturn()}")
        
        return True
    except Exception as e:
        print(f"❌ Adapter creation failed: {e}")
        return False

def test_basic_functionality():
    """测试基础功能"""
    try:
        from adapter.isek_adapter import UnifiedIsekAdapter
        
        class MockTeam:
            def __init__(self):
                self.name = "Mock Lyra Team"
                self.description = "Mock prompt optimization team"
            
            def run(self, message, user_id="default", session_id="default"):
                return f"Optimized prompt for: {message}"
        
        mock_team = MockTeam()
        adapter = UnifiedIsekAdapter(isek_team=mock_team, enable_streaming=False)
        
        # 测试同步调用
        result = adapter.run("Test prompt optimization", session_id="test_session")
        
        if result and "Optimized prompt" in result:
            print("✅ Basic run() method working")
            print(f"   Result: {result}")
        else:
            print(f"❌ Basic run() failed: {result}")
            return False
        
        # 测试会话管理
        session_context = adapter.session_manager.create_session_context("test_session")
        if session_context:
            print("✅ Session management working")
        else:
            print("❌ Session management failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        return False

async def test_async_functionality():
    """测试异步功能"""
    try:
        from adapter.isek_adapter import UnifiedIsekAdapter
        
        class MockTeam:
            def __init__(self):
                self.name = "Mock Async Team"
                self.description = "Mock team for async testing"
            
            def run(self, message, user_id="default", session_id="default"):
                return f"Async response: {message}"
        
        mock_team = MockTeam()
        adapter = UnifiedIsekAdapter(isek_team=mock_team, enable_streaming=False)
        
        # 测试异步执行
        context = {
            "task_id": "test_task_123",
            "session_id": "test_async_session",
            "user_input": "Test async execution",
            "message": None,
            "current_task": None
        }
        
        events = []
        async for event in adapter.execute_async(context):
            events.append(event)
            if len(events) >= 5:  # 限制事件数量
                break
        
        if events:
            print("✅ Async execution working")
            print(f"   Events generated: {len(events)}")
            
            # 检查事件类型
            event_types = [type(event).__name__ for event in events]
            print(f"   Event types: {event_types}")
            
            return True
        else:
            print("❌ Async execution failed: no events")
            return False
            
    except Exception as e:
        print(f"❌ Async functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("🧪 Quick Test: Lyra UnifiedIsekAdapter Integration")
    print("="*50)
    
    tests = [
        ("Import Test", test_import),
        ("Adapter Creation", test_adapter_creation),
        ("Basic Functionality", test_basic_functionality),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}...")
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} failed")
    
    # 异步测试
    print(f"\n📋 Async Functionality...")
    try:
        if asyncio.run(test_async_functionality()):
            passed += 1
        else:
            print("❌ Async Functionality failed")
    except Exception as e:
        print(f"❌ Async test error: {e}")
    
    total += 1  # 添加异步测试
    
    print(f"\n📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed! UnifiedIsekAdapter is working correctly.")
    else:
        print(f"⚠️ {total - passed} test(s) failed.")
    
    print("\n💡 To test with real Lyra agent:")
    print("   python test_lyra_operations.py")
    print("   python demo_lyra_usage.py")

if __name__ == "__main__":
    main()