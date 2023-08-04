import json

from amiyabot.network.httpRequests import http_requests


class SKLandAPI:
    def __init__(self, token: str):
        self.uid = ''
        self.code = ''
        self.cred = ''

        self.token = token
        self.headers = {
            'Origin': 'https://www.skland.com',
            'Referer': 'https://www.skland.com/',
            'Content-Type': 'application/json;charset=UTF-8',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,eo;q=0.8,en;q=0.7',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36'
        }

    async def get_code(self):
        if not self.code:
            payload = {
                'appCode': '4ca99fa6b56cc2ba',
                'token': self.token,
                'type': 0
            }
            res = await http_requests.post('https://as.hypergryph.com/user/oauth2/v2/grant', payload,
                                           headers=self.headers)
            if res:
                data = json.loads(res)
                if data['status'] == 0:
                    self.uid = data['data']['uid']
                    self.code = data['data']['code']

        return self.code

    async def get_cred(self):
        if not self.cred:
            payload = {
                'code': self.code,
                'kind': 1
            }
            headers = {
                **self.headers,
                'Host': 'zonai.skland.com'
            }
            res = await http_requests.post('https://zonai.skland.com/api/v1/user/auth/generate_cred_by_code', payload,
                                           headers=headers)
            if res:
                data = json.loads(res)
                if data['code'] == 0:
                    self.cred = data['data']['cred']

        return self.cred

    async def get_user_info(self):
        if not await self.get_code():
            return None
        if not await self.get_cred():
            return None

        headers = {
            **self.headers,
            'Host': 'zonai.skland.com',
            'Cred': self.cred
        }
        res = await http_requests.get('https://zonai.skland.com/api/v1/user/me', headers=headers)
        if res:
            data = json.loads(res)
            if data['code'] == 0:
                return data['data']
