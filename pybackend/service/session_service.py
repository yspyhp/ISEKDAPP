import json
from datetime import datetime
from typing import List

import requests

from mapper.models import Session, Message

class SessionService:
    def __init__(self):
        from mapper import sessionMapper, messageMapper
        self.session_mapper = sessionMapper
        self.message_mapper = messageMapper

    def get_user_sessions(self, base_url="http://127.0.0.1:6000", creator_id: str=None) -> List[Session]:
        """获取用户所有会话"""
        url = f"{base_url}/session/list?creator_id={creator_id}"
        response = requests.get(url)
        if response.status_code != 200:
            raise RuntimeError(f"get_user_sessions error[{response.content}]")
        return [Session.from_dict(c) for c in json.loads(response.content)]

    def get_session_by_id(self, base_url="http://127.0.0.1:6000", session_id: str=None, creator_id: str=None) -> Session:
        """获取用户所有会话"""
        url = f"{base_url}/session/get?creator_id={creator_id}&session_id={session_id}"
        response = requests.get(url)
        if response.status_code != 200:
            raise RuntimeError(f"get_session_by_id error[{response.content}]")
        return Session.from_dict(json.loads(response.content))

    def create_session(self, base_url="http://127.0.0.1:6000", session: Session=None) -> Session:
        """创建新会话"""
        url = f"{base_url}/session/create"
        request_body = json.dumps(session.__dict__)
        response = requests.post(url, data=request_body)
        if response.status_code != 200:
            raise RuntimeError(f"create_session error[{response.content}]")
        return Session.from_dict(json.loads(response.content))

    def delete_session(self, base_url="http://127.0.0.1:6000", session_id: str=None, creator_id: str=None) -> bool:
        """删除会话，同时删除关联的消息"""
        url = f"{base_url}/session/delete?creator_id={creator_id}&session_id={session_id}"
        response = requests.delete(url)
        if response.status_code != 200:
            raise RuntimeError(f"delete_session error[{response.content}]")
        return json.loads(response.content)

    def get_session_messages(self, base_url="http://127.0.0.1:6000", session_id: str=None, creator_id: str=None) -> List[Message]:
        """根据会话ID获取消息，需验证用户权限"""
        url = f"{base_url}/message/list?creator_id={creator_id}&session_id={session_id}"
        response = requests.get(url)
        if response.status_code != 200:
            raise RuntimeError(f"get_session_messages error[{response.content}]")
        return [Message.from_dict(c) for c in json.loads(response.content)]

    def create_message(self, base_url="http://127.0.0.1:6000", message: Message=None, creator_id: str=None) -> Message:
        """创建消息，需验证会话属于该用户"""
        url = f"{base_url}/message/create?creator_id={creator_id}"
        request_body = json.dumps(message.__dict__)
        response = requests.post(url, data=request_body)
        if response.status_code != 200:
            raise RuntimeError(f"create_message error[{response.content}]")
        return Message.from_dict(json.loads(response.content))


#
# from datetime import datetime
#
# session_json = {
#     'id': 'session1',
#     'title': 'Test Session',
#     'agent_id': 'agent123',
#     'agent_name': 'Test Agent',
#     'agent_description': 'This is a test agent',
#     'agent_address': 'http://localhost:8000',
#     'created_at': datetime.now().isoformat(),
#     'updated_at': datetime.now().isoformat(),
#     'message_count': 0,
#     'creator_id': "123"
# }
# session = Session.from_dict(session_json)
#
# message_json = {
#     'session_id': "session1",
#     'content': 'Hello, this is a test message',
#     'role': 'user',
#     'timestamp': datetime.now().isoformat(),
#     "creator_id": "123"
# }
# message = Message.from_dict(message_json)
#
#
# sessionService = SessionService()
# # print(sessionService.create_session(session))
#
# # print(sessionService.create_message(message, creator_id="123"))
#
# # print(sessionService.get_session_messages(session_id="session1", creator_id="123"))
#
# # print(sessionService.delete_session(session_id=1, creator_id=123))
#
# # print(sessionService.get_session_messages(session_id=1, creator_id=123))