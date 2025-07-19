"""
Default implementation of message handling module
"""

from typing import Dict, Any, List
import json
import uuid
from datetime import datetime
from .base import BaseMessageHandler
from isek.utils.log import log

# Import shared message formats
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from shared import create_agent_response


class DefaultMessageHandler(BaseMessageHandler):
    """Default implementation of message handling"""
    
    def __init__(self):
        log.info("DefaultMessageHandler initialized")
    
    def parse_message(self, message: str) -> Dict[str, Any]:
        """Parse incoming message with standardized format"""
        try:
            # Try to parse as JSON first
            if message.strip().startswith('{'):
                data = json.loads(message)
                
                # Validate required fields for different message types
                msg_type = data.get("type", "unknown")
                
                if msg_type == "chat":
                    # Ensure required fields for chat messages
                    if "user_id" not in data:
                        data["user_id"] = data.get("session_id", "unknown_user")
                    if "user_message" not in data and "messages" in data:
                        # Extract user message from messages array
                        user_msgs = [m for m in data["messages"] if m.get("role") == "user"]
                        if user_msgs:
                            data["user_message"] = user_msgs[-1].get("content", "")
                
                return {
                    "success": True,
                    "type": msg_type,
                    "data": data
                }
            else:
                # Plain text message - treat as chat with default user_id
                return {
                    "success": True,
                    "type": "chat",
                    "data": {
                        "type": "chat",
                        "user_id": "default_user",  # Default when user_id not available
                        "session_id": "",
                        "user_message": message,
                        "messages": [{"role": "user", "content": message}],
                        "system_prompt": "",
                        "timestamp": datetime.now().isoformat(),
                        "request_id": str(uuid.uuid4())
                    }
                }
        except json.JSONDecodeError:
            # If not valid JSON, treat as plain text chat
            return {
                "success": True,
                "type": "chat",
                "data": {
                    "type": "chat",
                    "user_id": "default_user",
                    "session_id": "",
                    "user_message": message,
                    "messages": [{"role": "user", "content": message}],
                    "system_prompt": "",
                    "timestamp": datetime.now().isoformat(),
                    "request_id": str(uuid.uuid4())
                }
            }
        except Exception as e:
            log.error(f"Error parsing message: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def format_response(self, response_data: Dict[str, Any]) -> str:
        """Format response for sending back to client"""
        try:
            return json.dumps(response_data, ensure_ascii=False)
        except Exception as e:
            log.error(f"Error formatting response: {e}")
            return json.dumps({
                "success": False,
                "error": "Failed to format response"
            })
    
    async def handle_chat_message(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle chat message and generate response"""
        try:
            data = parsed_data["data"]
            session_id = data.get("session_id", "")
            user_id = data.get("user_id", "")
            messages = data.get("messages", [])
            system_prompt = data.get("system_prompt", "")
            user_message = data.get("user_message", "")
            request_id = data.get("request_id", "")
            
            log.info(f"Handling chat message from user {user_id} in session {session_id}")
            
            # Generate AI response
            ai_response = await self._generate_ai_response(session_id, messages, system_prompt, user_message)
            
            # Use standardized response format
            return create_agent_response(
                success=True,
                content=ai_response["content"],
                tool_calls=ai_response.get("tool_calls", []),
                request_id=request_id
            )
            
        except Exception as e:
            log.error(f"Error handling chat message: {e}")
            return create_agent_response(
                success=False,
                error=str(e)
            )
    
    async def handle_session_lifecycle(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle session lifecycle events"""
        try:
            data = parsed_data["data"]
            action = data.get("action", "")
            session_id = data.get("session_id", "")
            user_id = data.get("user_id", "")
            request_id = data.get("request_id", "")
            
            log.info(f"Session lifecycle event: {action} for session {session_id} from user {user_id}")
            
            # Use standardized response format
            return create_agent_response(
                success=True,
                content=f"Session {action} acknowledged",
                request_id=request_id
            )
            
        except Exception as e:
            log.error(f"Error handling session lifecycle: {e}")
            return create_agent_response(
                success=False,
                error=str(e)
            )
    
    def get_message_type(self, parsed_data: Dict[str, Any]) -> str:
        """Extract message type from parsed data"""
        return parsed_data.get("type", "unknown")
    
    async def _generate_ai_response(self, session_id: str, messages: List[Dict], system_prompt: str, user_message: str) -> Dict[str, Any]:
        """Generate AI response"""
        try:
            # Check for team formation keywords
            if self._should_trigger_team_formation(user_message):
                return {
                    "content": "正在为您组建AI项目开发小队...",
                    "tool_calls": [{
                        "id": f"call_{uuid.uuid4().hex[:8]}",
                        "type": "function",
                        "function": {
                            "name": "team-formation",
                            "arguments": {
                                "task": "AI项目开发小队",
                                "requiredRoles": ["工程师", "数据科学家", "前端开发", "项目经理"],
                                "maxMembers": 4
                            }
                        }
                    }]
                }
            
            # Regular AI response
            responses = [
                "我理解您的问题，让我来帮助您。",
                "这是一个很好的问题，我来为您分析一下。",
                "根据您的描述，我建议考虑以下几个方面。",
                "让我来为您提供一些有用的信息。",
                "好的，我会根据您的需求为您提供相应的解决方案。",
                "这个问题很有意思，让我详细为您解答。"
            ]
            
            import random
            response = random.choice(responses)
            
            return {
                "content": response,
                "tool_calls": []
            }
            
        except Exception as e:
            log.error(f"Error generating AI response: {e}")
            return {
                "content": "抱歉，我暂时无法处理您的请求。",
                "tool_calls": []
            }
    
    def _should_trigger_team_formation(self, message: str) -> bool:
        """Check if message should trigger team formation tool call"""
        keywords = ["组队", "小队", "recruit", "team", "招聘", "组建", "协作"]
        return any(keyword in message.lower() for keyword in keywords)


class JsonMessageHandler(DefaultMessageHandler):
    """JSON-specific message handler"""
    
    def parse_message(self, message: str) -> Dict[str, Any]:
        """Parse JSON message strictly"""
        try:
            data = json.loads(message)
            return {
                "success": True,
                "type": data.get("type", "unknown"),
                "data": data
            }
        except json.JSONDecodeError as e:
            log.error(f"Invalid JSON message: {e}")
            return {
                "success": False,
                "error": f"Invalid JSON format: {str(e)}"
            }


class PlainTextMessageHandler(DefaultMessageHandler):
    """Plain text message handler"""
    
    def parse_message(self, message: str) -> Dict[str, Any]:
        """Parse plain text message"""
        return {
            "success": True,
            "type": "chat",
            "data": {
                "type": "chat",
                "user_message": message,
                "messages": [{"role": "user", "content": message}]
            }
        }