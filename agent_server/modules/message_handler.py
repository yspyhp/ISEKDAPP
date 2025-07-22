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
        self.agent_runner = None  # Will be set by SessionAdapter
        self.session_manager = None  # Will be set by SessionAdapter
        log.info("DefaultMessageHandler initialized")
    
    def set_agent_runner(self, runner_func):
        """Set the agent runner function"""
        self.agent_runner = runner_func
        
    def set_session_manager(self, session_manager):
        """Set the session manager for saving messages"""
        self.session_manager = session_manager
    
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
        """Handle chat message with session management and agent processing"""
        try:
            data = parsed_data["data"]
            session_id = data.get("session_id", "")
            user_id = data.get("user_id", "")
            user_message = data.get("user_message", "")
            request_id = data.get("request_id", "")
            
            actual_user = user_id if user_id and user_id != "default_user" else "unknown_user"
            session_short = session_id[:12] if session_id else "no_session"
            msg_preview = user_message[:60] + "..." if len(user_message) > 60 else user_message
            
            log.info(f"Chat received: user='{actual_user}' session='{session_short}' msg='{msg_preview}'")
            
            # Save user message to session if session manager available
            if self.session_manager and session_id:
                await self._save_user_message(session_id, user_message, actual_user)
            
            # Get session history for context if available
            session_history = []
            if self.session_manager and session_id:
                session_history = await self._get_session_history(session_id, actual_user)
            
            # Process through agent if available
            if self.agent_runner:
                try:
                    log.info(f"Starting agent processing for session {session_short}")
                    # Create enriched prompt with session history
                    original_prompt = self._create_agent_prompt(data, session_history)
                    log.info(f"Calling agent with prompt length: {len(original_prompt)}")
                    
                    # Call agent with timeout protection
                    import concurrent.futures
                    
                    try:
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(self.agent_runner, original_prompt)
                            agent_response = future.result(timeout=30)  # 30 second timeout
                        log.info(f"Agent response received: {agent_response[:100]}...")
                    except concurrent.futures.TimeoutError:
                        log.error(f"Agent call timed out after 30 seconds for session {session_short}")
                        raise Exception("Agent response timeout")
                    
                    # Extract content from agent response
                    agent_content = self._extract_agent_content(agent_response)
                    
                    # Save agent response to session if session manager available
                    if self.session_manager and session_id:
                        await self._save_agent_message(session_id, agent_content, actual_user)
                    
                    # Parse agent response if it's JSON
                    try:
                        import json
                        parsed_response = json.loads(agent_response)
                        if isinstance(parsed_response, dict) and "content" in parsed_response:
                            return create_agent_response(
                                success=parsed_response.get("success", True),
                                content=parsed_response.get("content", ""),
                                tool_calls=parsed_response.get("tool_calls", []),
                                request_id=request_id
                            )
                    except (json.JSONDecodeError, TypeError):
                        pass
                    
                    return create_agent_response(
                        success=True,
                        content=agent_response,
                        request_id=request_id
                    )
                except Exception as e:
                    log.error(f"Agent processing failed: {e}")
                    # Fall back to AI response generation
                    ai_response = await self._generate_ai_response(session_id, session_history, user_message, actual_user)
                    if self.session_manager and session_id:
                        await self._save_agent_message(session_id, ai_response["content"], actual_user)
                    return create_agent_response(
                        success=True,
                        content=ai_response["content"],
                        tool_calls=ai_response.get("tool_calls", []),
                        request_id=request_id
                    )
            else:
                # Fallback to AI response generation with team formation support
                ai_response = await self._generate_ai_response(session_id, session_history, user_message, actual_user)
                
                # Save AI response to session if session manager available
                if self.session_manager and session_id:
                    await self._save_agent_message(session_id, ai_response["content"], actual_user)
                
                return create_agent_response(
                    success=True,
                    content=ai_response["content"],
                    tool_calls=ai_response.get("tool_calls", []),
                    request_id=request_id
                )
            
        except Exception as e:
            log.error(f"Error handling chat message: {e}")
            return create_agent_response(success=False, error=str(e))
    
    def _create_agent_prompt(self, data: Dict[str, Any], session_history: List[Dict]) -> str:
        """Create enriched prompt for agent with session history"""
        user_message = data.get("user_message", "")
        
        # If we have session history, create a more complete prompt
        if session_history:
            # Convert session history to client-compatible format
            messages = []
            for msg in session_history[-10:]:  # Last 10 messages for context
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Add current user message
            messages.append({
                "role": "user", 
                "content": user_message
            })
            
            # Create enriched data structure
            enriched_data = data.copy()
            enriched_data["messages"] = messages
            
            # For agents that can handle structured data, return JSON
            try:
                import json
                return json.dumps(enriched_data, ensure_ascii=False)
            except:
                pass
        
        # Fallback to simple user message
        return user_message
    
    def _extract_agent_content(self, agent_response: str) -> str:
        """Extract content from agent response for session storage"""
        try:
            import json
            parsed = json.loads(agent_response)
            if isinstance(parsed, dict) and "content" in parsed:
                return parsed["content"]
        except:
            pass
        return agent_response
    
    async def _save_user_message(self, session_id: str, content: str, user_id: str):
        """Save user message to session"""
        try:
            from mapper.models import Message
            import uuid
            message = Message(
                id=str(uuid.uuid4()),
                sessionId=session_id,
                content=content,
                tool="",  # Empty for regular messages
                role="user",
                timestamp=datetime.now().isoformat(),
                creatorId=user_id
            )
            result = self.session_manager.create_message(message, user_id)
            log.info(f"User message saved to session {session_id[:12]}: {content[:50]}...")
            return result
        except Exception as e:
            log.error(f"Error saving user message: {e}")
            raise
    
    async def _save_agent_message(self, session_id: str, content: str, user_id: str):
        """Save agent message to session"""
        try:
            from mapper.models import Message
            import uuid
            message = Message(
                id=str(uuid.uuid4()),
                sessionId=session_id,
                content=content,
                tool="",  # Empty for regular messages  
                role="assistant",
                timestamp=datetime.now().isoformat(),
                creatorId=user_id
            )
            result = self.session_manager.create_message(message, user_id)
            log.info(f"Agent message saved to session {session_id[:12]}: {content[:50]}...")
            return result
        except Exception as e:
            log.error(f"Error saving agent message: {e}")
            raise
    
    async def _get_session_history(self, session_id: str, user_id: str) -> List[Dict]:
        """Get session chat history in client-compatible ChatMessage format"""
        try:
            messages = self.session_manager.get_session_messages(session_id, user_id)
            
            # Convert to client ChatMessage format (matching types.ts)
            history = []
            for msg in messages:
                # Ensure we match the exact ChatMessage interface
                chat_message = {
                    "id": getattr(msg, 'id', str(uuid.uuid4())),
                    "sessionId": msg.sessionId,
                    "content": msg.content,
                    "role": msg.role,  # 'user' | 'assistant'
                    "timestamp": msg.timestamp
                }
                history.append(chat_message)
            
            return history
        except Exception as e:
            log.error(f"Error getting session history: {e}")
            return []
    
    async def _generate_ai_response(self, session_id: str, session_history: List[Dict], user_message: str, user_id: str = "unknown") -> Dict[str, Any]:
        """Generate AI response with echo and team formation support"""
        try:
            # Check for team formation keywords
            if self._should_trigger_team_formation(user_message):
                call_id = f"call_{uuid.uuid4().hex[:8]}"
                team_members = self._get_team_members()
                
                log.info(f"🔍 Server generating team formation response:")
                log.info(f"  - team_members count: {len(team_members)}")
                
                response = {
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
                                "status": "completed",
                                "progress": 1.0,
                                "currentStep": "小队组建完成！",
                                "members": team_members,
                                "teamStats": {
                                    "totalMembers": len(team_members),
                                    "skills": ["AI图片创作", "数据分析", "智能问答", "流程编排"]
                                }
                            }
                        }
                    }]
                }
                
                return response
            
            # Echo response with session context
            context_info = f" (历史记录: {len(session_history)} 条消息)" if session_history else ""
            echo_content = f"Echo: {user_message}{context_info}"
            
            log.info(f"Generated echo response for user '{user_id}' with {len(session_history)} history messages")
            
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
                "avatar": "🖼️",
                "description": "根据文本描述生成高质量图片，支持风格化和多场景渲染"
            },
            {
                "name": "Data Insight Agent",
                "role": "数据分析",
                "skill": "自动化数据洞察",
                "avatar": "📊",
                "description": "擅长大数据分析、趋势预测和可视化报告"
            },
            {
                "name": "Smart QA Agent",
                "role": "智能问答",
                "skill": "知识检索/FAQ",
                "avatar": "💡",
                "description": "快速响应用户问题，支持多领域知识库"
            },
            {
                "name": "Workflow Orchestrator",
                "role": "流程编排",
                "skill": "多Agent协作调度",
                "avatar": "🕹️",
                "description": "负责各智能体之间的任务分配与流程自动化"
            }
        ]

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
    


