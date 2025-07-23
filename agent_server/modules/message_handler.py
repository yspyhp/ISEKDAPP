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
        """Parse incoming message with strict validation - throws exceptions for bad data"""
        # Handle ISEK framework wrapped messages
        if "contextId=" in message and "messageId=" in message and "parts=[Part(root=TextPart(" in message:
            # Extract JSON from ISEK message wrapper
            import re
            json_match = re.search(r"text='([^']*)'", message)
            if not json_match:
                raise ValueError("Could not extract JSON from ISEK message wrapper")
            
            json_str = json_match.group(1)
            # Unescape the JSON string
            json_str = json_str.replace('\\"', '"').replace('\\\\', '\\')
            
            try:
                data = json.loads(json_str)
                log.info(f"Extracted JSON from ISEK wrapper: {data}")
            except json.JSONDecodeError as e:
                log.error(f"Failed to parse extracted JSON: {e}")
                log.error(f"Extracted string was: {json_str}")
                raise ValueError(f"Invalid JSON in ISEK wrapper: {e}")
        
        # Try to parse as direct JSON
        elif message.strip().startswith('{'):
            data = json.loads(message)
            
        else:
            raise ValueError(f"Message must be JSON format, received: {message[:100]}...")
        
        # Strict validation of required fields
        msg_type = data.get("type")
        if not msg_type:
            raise ValueError("Message must contain 'type' field")
        
        if msg_type == "chat":
            required_fields = ["user_id", "session_id", "user_message"]
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Chat message missing required field: {field}")
            
            if not data["user_message"].strip():
                raise ValueError("Chat message cannot be empty")
                
        elif msg_type == "agent_config_request":
            if "node_id" not in data:
                raise ValueError("agent_config_request missing required field: node_id")
                
        elif msg_type == "session_lifecycle":
            required_fields = ["action", "session_id", "user_id"]
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"session_lifecycle message missing required field: {field}")
                    
        elif msg_type == "task":
            if "task_type" not in data:
                raise ValueError("task message missing required field: task_type")
        else:
            raise ValueError(f"Unsupported message type: {msg_type}")
        
        return {
            "success": True,
            "type": msg_type,
            "data": data
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
    
    def handle_chat_message(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
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
                self._save_user_message(session_id, user_message, actual_user)
            
            # Get session history for context if available
            session_history = []
            if self.session_manager and session_id:
                session_history = self._get_session_history(session_id, actual_user)
            
            # Agent runner is required - no fallbacks
            if not self.agent_runner:
                raise Exception("Agent runner not configured")
            
            log.info(f"Starting agent processing for session {session_short}")
            # Create enriched prompt with session history
            original_prompt = self._create_agent_prompt(data, session_history)
            log.info(f"Calling agent with prompt length: {len(original_prompt)}")
            
            # Call agent directly
            agent_response = self.agent_runner(original_prompt)
            log.info(f"Agent response: {agent_response[:100]}...")
            
            # Save response to session
            if self.session_manager and session_id:
                self._save_agent_message(session_id, agent_response, actual_user)
            
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
            log.error(f"Error handling chat message: {e}")
            raise
    
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
    
    
    def _save_user_message(self, session_id: str, content: str, user_id: str):
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
    
    def _save_agent_message(self, session_id: str, content: str, user_id: str):
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
    
    def _get_session_history(self, session_id: str, user_id: str) -> List[Dict]:
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
    


