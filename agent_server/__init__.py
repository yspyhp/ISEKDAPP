import json

import requests

url = 'https://api.coze.cn/v3/chat/message/list?conversation_id=7528021215995379722&chat_id=7528021215995396106&'
headers = {
    "Authorization": "Bearer pat_ehYJLwcHflqZWB6peSvOMbptRRKt5dLbrkBi2Z9Xzcd2WBSk8mPjtRsmZIgdVJy5",
    "Content-Type": "application/json"
}

response = requests.get(url=url, headers=headers)
print(json.loads(response.content))