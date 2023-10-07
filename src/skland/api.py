import json

from typing import Optional, Dict
from dataclasses import dataclass
from amiyabot.network.httpRequests import http_requests
from amiyabot.log import LoggerManager

log = LoggerManager('SKLand')


class SKLandAPI:
    headers = {
        'Origin': 'https://www.skland.com',
        'Referer': 'https://www.skland.com/',
        'Content-Type': 'application/json;charset=UTF-8',
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,eo;q=0.8,en;q=0.7',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/105.0.0.0 Safari/537.36',
    }

    def __init__(self):
        self.users: Dict[str, SKLandUser] = {}

    @property
    def user_id_map(self):
        return {item.user_id: token for token, item in self.users.items()}

    async def user(self, token: str):
        if token in self.users:
            return self.users[token]

        code, user_id = await self.__get_grant(token)
        if not user_id:
            return None

        if user_id in self.user_id_map:
            del self.users[self.user_id_map[user_id]]

        cred = await self.__get_cred(code)
        if not cred:
            return None

        self.users[token] = SKLandUser(code, cred, token, user_id)

        return self.users[token]

    async def __get_grant(self, token: str):
        type_value = 1 if len(token) > 30 else 0

        code = ''
        user_id = ''
        payload = {'appCode': '4ca99fa6b56cc2ba', 'token': token, 'type': type_value}
        res = await http_requests.post('https://as.hypergryph.com/user/oauth2/v2/grant', payload, headers=self.headers)
        if res:
            data = json.loads(res)
            if data['status'] == 0:
                code = data['data']['code']
                user_id = data['data']['uid']

        return code, user_id

    async def __get_cred(self, code: str):
        cred = ''
        payload = {'code': code, 'kind': 1}
        headers = {**self.headers, 'Host': 'zonai.skland.com'}
        res = await http_requests.post(
            'https://zonai.skland.com/api/v1/user/auth/generate_cred_by_code', payload, headers=headers
        )
        if res:
            data = json.loads(res)
            if data['code'] == 0:
                cred = data['data']['cred']

        return cred


@dataclass
class SKLandUser:
    code: str
    cred: str
    token: str
    user_id: str

    async def user_info(self) -> Optional[dict]:
        headers = {**SKLandAPI.headers, 'Host': 'zonai.skland.com', 'Cred': self.cred}
        res = await http_requests.get('https://zonai.skland.com/api/v1/user/me', headers=headers)
        if res:
            data = json.loads(res)
            if data['code'] == 0:
                return data['data']

    async def character_info(self, uid: str) -> Optional[dict]:
        headers = {**SKLandAPI.headers, 'Host': 'zonai.skland.com', 'Cred': self.cred}
        res = await http_requests.get(f'https://zonai.skland.com/api/v1/game/player/info?uid={uid}', headers=headers)
        if res:
            data = json.loads(res)
            if data['code'] == 0:
                return data['data']
