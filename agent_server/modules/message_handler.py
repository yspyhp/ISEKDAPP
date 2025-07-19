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
            # Handle ISEK framework wrapped messages
            # The message might be a string representation of an ISEK message object
            if "contextId=" in message and "messageId=" in message and "parts=[Part(root=TextPart(" in message:
                # Extract JSON from ISEK message wrapper
                # Look for the JSON content inside TextPart text field
                import re
                json_match = re.search(r"text='([^']*)'", message)
                if json_match:
                    json_str = json_match.group(1)
                    # Unescape the JSON string
                    json_str = json_str.replace('\\"', '"').replace('\\\\', '\\')
                    try:
                        data = json.loads(json_str)
                        log.info(f"Extracted JSON from ISEK wrapper: {data}")
                    except json.JSONDecodeError as e:
                        log.error(f"Failed to parse extracted JSON: {e}")
                        log.error(f"Extracted string was: {json_str}")
                        # Fallback to treating the whole message as text
                        data = {"type": "chat", "user_message": message, "user_id": "unknown_user"}
                else:
                    log.warning("Could not extract JSON from ISEK message wrapper")
                    data = {"type": "chat", "user_message": message, "user_id": "unknown_user"}
            
            # Try to parse as direct JSON
            elif message.strip().startswith('{'):
                data = json.loads(message)
                
            else:
                # Plain text message - treat as chat with default user_id
                data = {
                    "type": "chat",
                    "user_id": "default_user",
                    "session_id": "",
                    "user_message": message,
                    "messages": [{"role": "user", "content": message}],
                    "system_prompt": "",
                    "timestamp": datetime.now().isoformat(),
                    "request_id": str(uuid.uuid4())
                }
            
            # Validate and normalize the parsed data
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
            elif msg_type == "agent_config_request":
                # Ensure required fields for agent config requests
                if "node_id" not in data:
                    log.warning("agent_config_request missing node_id")
            elif msg_type == "session_lifecycle":
                # Ensure required fields for session lifecycle messages
                if "action" not in data:
                    log.warning("session_lifecycle missing action")
            elif msg_type == "task":
                # Ensure required fields for task messages
                if "task_type" not in data:
                    log.warning("task message missing task_type")
            
            return {
                "success": True,
                "type": msg_type,
                "data": data
            }
                
        except json.JSONDecodeError as e:
            log.error(f"JSON decode error: {e}")
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
            
            # Use actual user_id from client (e.g., isek_client_node) instead of default_user
            actual_user = user_id if user_id and user_id != "default_user" else "unknown_user"
            session_short = session_id[:12] if session_id else "no_session"
            msg_preview = user_message[:60] + "..." if len(user_message) > 60 else user_message
            
            log.info(f"Chat received: user='{actual_user}' session='{session_short}' msg='{msg_preview}'")
            
            # Generate AI response with echo and tool calls
            ai_response = await self._generate_ai_response(session_id, messages, system_prompt, user_message, actual_user)
            
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
    
    async def _generate_ai_response(self, session_id: str, messages: List[Dict], system_prompt: str, user_message: str, user_id: str = "unknown") -> Dict[str, Any]:
        """Generate AI response with echo and tool calls"""
        try:
            # Check for team formation keywords
            if self._should_trigger_team_formation(user_message):
                call_id = f"call_{uuid.uuid4().hex[:8]}"
                return {
                    "content": "正在为您组建AI项目开发小队...",
                    "tool_calls": [{
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": "team-formation",
                            "arguments": {
                                "task": "AI项目开发小队",
                                "requiredRoles": ["工程师", "数据科学家", "前端开发", "项目经理"],
                                "maxMembers": 4,
                                "status": "recruiting",
                                "progress": 0.1,
                                "currentStep": "开始招募小队成员...",
                                "members": self._get_team_members()
                            }
                        }
                    }]
                }
            
            # Echo response with just the user message content
            echo_content = f"Echo: {user_message}"
            
            # No tool calls for regular echo, only for team formation
            log.info(f"Generated echo response for user '{user_id}'")
            
            return {
                "content": echo_content,
                "tool_calls": []
            }
            
        except Exception as e:
            log.error(f"Error generating AI response: {e}")
            return {
                "content": f"抱歉，我暂时无法处理您的请求。Error: {str(e)}",
                "tool_calls": []
            }
    
    def _should_trigger_team_formation(self, message: str) -> bool:
        """Check if message should trigger team formation tool call"""
        keywords = ["组队", "小队", "recruit", "team", "招聘", "组建", "协作"]
        return any(keyword in message.lower() for keyword in keywords)
    
    def _get_team_members(self) -> List[Dict[str, Any]]:
        """Get available team members for recruitment"""
        return [
            {
                "name": "Magic Image Agent",
                "role": "图像生成",
                "skill": "AI图片创作",
                "experience": "2年",
                "avatar": "🖼️",
                "description": "根据文本描述生成高质量图片，支持风格化和多场景渲染"
            },
            {
                "name": "Data Insight Agent",
                "role": "数据分析",
                "skill": "自动化数据洞察",
                "experience": "3年",
                "avatar": "📊",
                "description": "擅长大数据分析、趋势预测和可视化报告"
            },
            {
                "name": "Smart QA Agent",
                "role": "智能问答",
                "skill": "知识检索/FAQ",
                "experience": "2年",
                "avatar": "💡",
                "description": "快速响应用户问题，支持多领域知识库"
            },
            {
                "name": "Workflow Orchestrator",
                "role": "流程编排",
                "skill": "多Agent协作调度",
                "experience": "4年",
                "avatar": "🕹️",
                "description": "负责各智能体之间的任务分配与流程自动化"
            }
        ]


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