import time
import json
import hmac
import hashlib

from urllib import parse
from typing import Optional, Dict
from dataclasses import dataclass
from amiyabot.network.httpRequests import http_requests
from amiyabot.log import LoggerManager

log = LoggerManager('SKLand')


class SKLandAPI:
    agent = 'Skland/1.0.1 (com.hypergryph.skland; build:100001014; Android 31; ) Okhttp/4.11.0'
    headers = {
        'User-Agent': agent,
        'Accept-Encoding': 'gzip',
        'Connection': 'close',
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

        cred, sign_token = await self.__get_cred(code)
        if not cred:
            return None

        self.users[token] = SKLandUser(code, cred, token, user_id, sign_token)

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
        sign_token = ''

        payload = {'code': code, 'kind': 1}
        headers = {**self.headers, 'Host': 'zonai.skland.com'}
        res = await http_requests.post(
            'https://zonai.skland.com/api/v1/user/auth/generate_cred_by_code', payload, headers=headers
        )
        if res:
            data = json.loads(res)
            if data['code'] == 0:
                cred = data['data']['cred']
                sign_token = data['data']['token']

        return cred, sign_token


@dataclass
class SKLandUser:
    code: str
    cred: str
    token: str
    user_id: str
    sign_token: str

    def get_headers(self, url: str):
        t = str(int(time.time()) - 25)
        data = {
            'platform': '',
            'timestamp': t,
            'dId': '',
            'vName': '',
        }
        return {
            **SKLandAPI.headers,
            **data,
            'Host': 'zonai.skland.com',
            'Cred': self.cred,
            'Sign': generate_sign(data, t, url, self.sign_token),
        }

    async def user_info(self) -> Optional[dict]:
        url = 'https://zonai.skland.com/api/v1/user/me'
        headers = self.get_headers(url)
        res = await http_requests.get(url, headers=headers)
        if res:
            data = json.loads(res)
            if data['code'] == 0:
                return data['data']

    async def character_info(self, uid: str) -> Optional[dict]:
        url = f'https://zonai.skland.com/api/v1/game/player/info?uid={uid}'
        headers = self.get_headers(url)
        res = await http_requests.get(url, headers=headers)
        if res:
            data = json.loads(res)
            if data['code'] == 0:
                return data['data']

    async def cultivate_player(self, uid: str) -> Optional[dict]:
        url = f'https://zonai.skland.com/api/v1/game/cultivate/player?uid={uid}'
        headers = self.get_headers(url)
        res = await http_requests.get(url, headers=headers)
        if res:
            data = json.loads(res)
            if data['code'] == 0:
                return data['data']

    async def cultivate_character(self, char_id: str) -> Optional[dict]:
        url = f'https://zonai.skland.com/api/v1/game/cultivate/character?characterld={char_id}'
        headers = self.get_headers(url)
        res = await http_requests.get(url, headers=headers)
        if res:
            data = json.loads(res)
            if data['code'] == 0:
                return data['data']

    async def binding(self) -> Optional[dict]:
        url = f'https://zonai.skland.com/api/v1/game/player/binding'
        headers = self.get_headers(url)
        res = await http_requests.get(url, headers=headers)
        if res:
            data = json.loads(res)
            if data['code'] == 0:
                return data['data']


def generate_sign(data: dict, t: str, url: str, token: str):
    ca = json.dumps(data, separators=(',', ':'))
    p = parse.urlparse(url)
    s = p.path + p.query + t + ca
    hex_s = hmac.new(token.encode('utf-8'), s.encode('utf-8'), hashlib.sha256).hexdigest()
    sign = hashlib.md5(hex_s.encode('utf-8')).hexdigest().encode('utf-8').decode('utf-8')

    return sign
