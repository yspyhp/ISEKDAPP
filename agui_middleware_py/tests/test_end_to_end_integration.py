"""
End-to-End Integration Test for AGUI Middleware
Tests the complete data flow: Frontend → AGUI → Service → Adapter → Translator → Node → Server
"""

import asyncio
import logging
import uuid
import json
from typing import Dict, Any, List
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.agui_service import AGUIService, AGUIRequest
from adapters.agui_adapter import AGUIAdapter
from core.isek_client import ISEKClient, ISEKNodeConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EndToEndIntegrationTest:
    """Complete end-to-end integration test for AGUI middleware"""
    
    def __init__(self):
        self.agui_service = None
        self.agui_adapter = None
        self.isek_client = None
        self.test_results = []
        
    async def setup(self):
        """Setup all components for testing"""
        try:
            logger.info("🔧 Setting up end-to-end integration test...")
            
            # 1. Initialize AGUI Adapter
            isek_config = {
                "registry": {
                    "host": "47.236.116.81",
                    "port": 2379
                }
            }
            
            self.agui_adapter = AGUIAdapter(isek_config)
            await self.agui_adapter.initialize()
            
            # 2. Create adapter registry
            adapter_registry = {
                "agui_adapter": self.agui_adapter
            }
            
            # 3. Initialize AGUI Service
            self.agui_service = AGUIService(adapter_registry)
            
            # 4. Setup ISEK Client (optional for extended testing)
            node_config = ISEKNodeConfig(
                node_id="test_middleware_node",
                host="0.0.0.0",
                port=8083,
                p2p_enabled=False
            )
            
            self.isek_client = ISEKClient(node_config, self._middleware_callback)
            await self.isek_client.initialize()
            
            logger.info("✅ End-to-end test setup complete")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to setup integration test: {e}")
            raise
    
    async def test_complete_data_flow(self) -> Dict[str, Any]:
        """Test the complete data flow through all layers"""
        test_name = "Complete Data Flow Test"
        logger.info(f"🧪 Starting {test_name}")
        
        try:
            # Create test AGUI request
            agui_request = AGUIRequest(
                agent_id="lyra_agent",
                messages=[
                    {
                        "role": "user",
                        "content": "Hello, please help me optimize this prompt: Write a creative story about AI"
                    }
                ],
                context={
                    "application": "test_app",
                    "user_preferences": {"language": "english"}
                },
                session_id=str(uuid.uuid4()),
                user_id="test_user"
            )
            
            logger.info(f"📤 Sending AGUI request: {agui_request.agent_id}")
            logger.info(f"   Request ID: {agui_request.request_id}")
            logger.info(f"   Session ID: {agui_request.session_id}")
            logger.info(f"   Message: {agui_request.messages[0]['content'][:50]}...")
            
            # Process through the complete pipeline
            response = await self.agui_service.process_agui_request(agui_request)
            
            # Verify response structure
            assert response is not None, "Response should not be None"
            assert response.request_id == agui_request.request_id, "Request ID should match"
            assert response.agent_id == agui_request.agent_id, "Agent ID should match"
            assert response.session_id == agui_request.session_id, "Session ID should match"
            assert isinstance(response.events, list), "Events should be a list"
            
            logger.info(f"📨 Received response with {len(response.events)} events")
            logger.info(f"   Status: {response.status}")
            
            # Log event details
            for i, event in enumerate(response.events):
                event_type = event.get('type', type(event).__name__)
                logger.info(f"   Event {i+1}: {event_type}")
                
                if hasattr(event, 'content'):
                    logger.info(f"     Content: {event.content[:100]}...")
                elif isinstance(event, dict) and 'data' in event:
                    data = event['data']
                    if 'content' in data:
                        logger.info(f"     Content: {data['content'][:100]}...")
                    elif 'error' in data:
                        logger.info(f"     Error: {data['error']}")
            
            result = {
                "test_name": test_name,
                "status": "passed" if response.status != "error" else "failed",
                "request_id": agui_request.request_id,
                "agent_id": agui_request.agent_id,
                "session_id": agui_request.session_id,
                "events_count": len(response.events),
                "response_status": response.status,
                "error": response.error if hasattr(response, 'error') else None,
                "timestamp": datetime.now().isoformat()
            }
            
            self.test_results.append(result)
            logger.info(f"✅ {test_name} completed: {result['status']}")
            return result
            
        except Exception as e:
            logger.error(f"❌ {test_name} failed: {e}")
            result = {
                "test_name": test_name,
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.test_results.append(result)
            return result
    
    async def test_streaming_data_flow(self) -> Dict[str, Any]:
        """Test streaming data flow through all layers"""
        test_name = "Streaming Data Flow Test"
        logger.info(f"🧪 Starting {test_name}")
        
        try:
            # Create test request for streaming
            agui_request = AGUIRequest(
                agent_id="lyra_agent",
                messages=[
                    {
                        "role": "user",
                        "content": "Please provide a detailed explanation of prompt engineering techniques"
                    }
                ],
                context={
                    "streaming": True,
                    "application": "test_app"
                },
                session_id=str(uuid.uuid4()),
                user_id="test_user"
            )
            
            logger.info(f"📤 Starting streaming request: {agui_request.agent_id}")
            
            events_received = []
            async for event in self.agui_service.stream_agui_request(agui_request):
                events_received.append(event)
                event_type = event.get('type', type(event).__name__)
                logger.info(f"📨 Streaming event: {event_type}")
                
                # Limit streaming for test purposes
                if len(events_received) >= 10:
                    break
            
            result = {
                "test_name": test_name,
                "status": "passed" if events_received else "failed",
                "request_id": agui_request.request_id,
                "agent_id": agui_request.agent_id,
                "session_id": agui_request.session_id,
                "events_streamed": len(events_received),
                "timestamp": datetime.now().isoformat()
            }
            
            self.test_results.append(result)
            logger.info(f"✅ {test_name} completed: streamed {len(events_received)} events")
            return result
            
        except Exception as e:
            logger.error(f"❌ {test_name} failed: {e}")
            result = {
                "test_name": test_name,
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.test_results.append(result)
            return result
    
    async def test_agent_discovery(self) -> Dict[str, Any]:
        """Test agent discovery functionality"""
        test_name = "Agent Discovery Test"
        logger.info(f"🧪 Starting {test_name}")
        
        try:
            # Test agent discovery through service
            agents = await self.agui_service.get_available_agents()
            
            logger.info(f"🔍 Discovered {len(agents)} agents:")
            for agent in agents:
                logger.info(f"   - {agent['id']}: {agent['name']} ({agent.get('url', 'no-url')})")
            
            # Verify expected agent is found
            lyra_found = any(agent['id'] == 'lyra_agent' for agent in agents)
            
            result = {
                "test_name": test_name,
                "status": "passed" if lyra_found else "warning",
                "agents_discovered": len(agents),
                "lyra_agent_found": lyra_found,
                "agent_list": [agent['id'] for agent in agents],
                "timestamp": datetime.now().isoformat()
            }
            
            self.test_results.append(result)
            logger.info(f"✅ {test_name} completed: {result['status']}")
            return result
            
        except Exception as e:
            logger.error(f"❌ {test_name} failed: {e}")
            result = {
                "test_name": test_name,
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.test_results.append(result)
            return result
    
    async def test_session_management(self) -> Dict[str, Any]:
        """Test session management functionality"""
        test_name = "Session Management Test"
        logger.info(f"🧪 Starting {test_name}")
        
        try:
            session_id = str(uuid.uuid4())
            
            # Create multiple requests with same session
            for i in range(3):
                agui_request = AGUIRequest(
                    agent_id="lyra_agent",
                    messages=[
                        {
                            "role": "user",
                            "content": f"Test message {i+1} for session management"
                        }
                    ],
                    context={"test_sequence": i+1},
                    session_id=session_id,
                    user_id="test_user"
                )
                
                response = await self.agui_service.process_agui_request(agui_request)
                logger.info(f"   Request {i+1} processed: {response.status}")
            
            # Check session info
            session_info = await self.agui_service.get_session_info(session_id)
            
            result = {
                "test_name": test_name,
                "status": "passed" if session_info else "failed",
                "session_id": session_id,
                "requests_processed": 3,
                "session_info": session_info,
                "timestamp": datetime.now().isoformat()
            }
            
            self.test_results.append(result)
            logger.info(f"✅ {test_name} completed: {result['status']}")
            return result
            
        except Exception as e:
            logger.error(f"❌ {test_name} failed: {e}")
            result = {
                "test_name": test_name,
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.test_results.append(result)
            return result
    
    async def test_protocol_conversion(self) -> Dict[str, Any]:
        """Test AGUI ↔ A2A protocol conversion"""
        test_name = "Protocol Conversion Test"
        logger.info(f"🧪 Starting {test_name}")
        
        try:
            # Test adapter's conversion capabilities directly
            test_input = {
                "agent_id": "lyra_agent",
                "messages": [
                    {
                        "role": "user", 
                        "content": "Convert this AGUI message to A2A format"
                    }
                ],
                "context": {"conversion_test": True},
                "session_id": str(uuid.uuid4()),
                "user_id": "test_user",
                "request_id": str(uuid.uuid4())
            }
            
            # Test AGUI to A2A conversion
            a2a_message = await self.agui_adapter._convert_agui_to_a2a(test_input)
            
            logger.info(f"📝 AGUI → A2A conversion result: {a2a_message[:100]}...")
            
            # Verify conversion
            assert isinstance(a2a_message, str), "A2A message should be string"
            assert len(a2a_message) > 0, "A2A message should not be empty"
            
            result = {
                "test_name": test_name,
                "status": "passed",
                "agui_input_length": len(str(test_input)),
                "a2a_output_length": len(a2a_message),
                "conversion_successful": True,
                "timestamp": datetime.now().isoformat()
            }
            
            self.test_results.append(result)
            logger.info(f"✅ {test_name} completed: {result['status']}")
            return result
            
        except Exception as e:
            logger.error(f"❌ {test_name} failed: {e}")
            result = {
                "test_name": test_name,
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.test_results.append(result)
            return result
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all integration tests"""
        logger.info("🚀 Starting complete end-to-end integration test suite")
        
        start_time = datetime.now()
        
        # Run all tests
        tests = [
            self.test_agent_discovery(),
            self.test_protocol_conversion(),
            self.test_complete_data_flow(),
            self.test_session_management(),
            self.test_streaming_data_flow()
        ]
        
        test_results = await asyncio.gather(*tests, return_exceptions=True)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Compile summary
        passed_tests = sum(1 for result in self.test_results if result.get('status') == 'passed')
        failed_tests = sum(1 for result in self.test_results if result.get('status') == 'failed')
        warning_tests = sum(1 for result in self.test_results if result.get('status') == 'warning')
        
        summary = {
            "test_suite": "End-to-End Integration Test",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "total_tests": len(self.test_results),
            "passed": passed_tests,
            "failed": failed_tests,
            "warnings": warning_tests,
            "success_rate": (passed_tests / len(self.test_results)) * 100 if self.test_results else 0,
            "detailed_results": self.test_results
        }
        
        logger.info(f"📊 Test Suite Summary:")
        logger.info(f"   Total Tests: {summary['total_tests']}")
        logger.info(f"   Passed: {summary['passed']}")
        logger.info(f"   Failed: {summary['failed']}")
        logger.info(f"   Warnings: {summary['warnings']}")
        logger.info(f"   Success Rate: {summary['success_rate']:.1f}%")
        logger.info(f"   Duration: {summary['duration_seconds']:.2f}s")
        
        return summary
    
    async def _middleware_callback(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Callback for ISEK middleware integration"""
        # This would be the bridge between A2A and AGUI protocols
        message = context.get('message', '')
        
        return {
            "content": f"Middleware processed: {message}",
            "status": "success",
            "session_id": context.get('session_id'),
            "timestamp": datetime.now().isoformat()
        }
    
    async def cleanup(self):
        """Cleanup test resources"""
        logger.info("🧹 Cleaning up test resources...")
        
        if self.isek_client:
            await self.isek_client.shutdown()
        
        logger.info("✅ Test cleanup complete")


async def main():
    """Main test runner"""
    logger.info("🎯 AGUI Middleware End-to-End Integration Test")
    logger.info("=" * 60)
    
    test_runner = EndToEndIntegrationTest()
    
    try:
        # Setup
        await test_runner.setup()
        
        # Run tests
        results = await test_runner.run_all_tests()
        
        # Output results
        print("\n" + "=" * 60)
        print("🏁 END-TO-END INTEGRATION TEST RESULTS")
        print("=" * 60)
        print(json.dumps(results, indent=2, default=str))
        
        # Return status based on results
        return 0 if results['failed'] == 0 else 1
        
    except Exception as e:
        logger.error(f"❌ Test suite failed with exception: {e}")
        return 1
        
    finally:
        await test_runner.cleanup()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)