import asyncio
import time
import json
import hmac
import hashlib

from urllib import parse
from typing import Any, Optional, Dict, Tuple
from dataclasses import dataclass
from amiyabot.network.httpRequests import http_requests
from amiyabot.log import LoggerManager
from datetime import datetime
from pathlib import Path
from core import AmiyaBotPluginInstance
from core.resource import remote_config
from amiyabot.builtin.lib.browserService import basic_browser_service

try:
    import ujson as json
except ImportError:
    import json

log = LoggerManager('SKLand')
RESOURCE_PATH = Path(__file__).parent / 'resource'


class Constants:
    DATA_PATH = RESOURCE_PATH / 'constants.json'
    data: Dict[str, Any] = None
    update_time: datetime = None
    remote_time: datetime = None

    async def sync(self):
        if self.data is not None:
            return
        while True:
            res = await http_requests.get(
                remote_config.remote.plugin + '/api/v1/updatetime'
            )
            if res:
                try:
                    res = json.loads(res)['data']
                    self.remote_time = datetime.strptime(res['skland'], '%Y-%m-%d %H:%M:%S')
                    break
                except Exception as e:
                    pass
            log.warning('获取远程更新时间失败, 正在重试...')
            await asyncio.sleep(1)
        if self.DATA_PATH.exists():
            self.update_time = datetime.fromtimestamp(self.DATA_PATH.stat().st_mtime)
        if (
            not self.remote_time
            or not self.update_time
            or self.remote_time > self.update_time
        ):
            log.info('远程数据有更新, 正在获取最新数据')
            while True:
                res = await http_requests.get(
                    remote_config.remote.plugin + '/api/v1/skland'
                )
                if res:
                    try:
                        self.data = json.loads(res)['data']
                        with self.DATA_PATH.open('w', encoding='utf-8') as f:
                            json.dump(self.data, f, ensure_ascii=False, indent=4)
                        self.update_time = datetime.now()
                        log.info('远程数据获取成功')
                        break
                    except Exception as e:
                        pass
                log.warning('获取远程数据失败, 正在重试...')
                await asyncio.sleep(1)
        else:
            self.data = json.loads(self.DATA_PATH.read_text(encoding='utf-8'))


constants = Constants()


class SKLandAPI:
    users: Dict[str, 'SKLandUser']
    bot: AmiyaBotPluginInstance

    def __init__(self):
        self.users: Dict[str, SKLandUser] = {}

    def set_bot(self, bot: AmiyaBotPluginInstance):
        self.bot = bot

    @property
    def user_id_map(self):
        return {item.user_id: token for token, item in self.users.items()}

    async def user(self, token: str):
        await constants.sync()
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

        self.users[token] = SKLandUser(code, cred, token, user_id, sign_token, self.bot)

        return self.users[token]

    async def __get_grant(self, token: str) -> Tuple[str, str]:
        type_value = 1 if len(token) > 30 else 0

        code = ''
        user_id = ''
        payload = {
            'appCode': constants.data['APP_CODE'],
            'token': token,
            'type': type_value,
        }
        res = await http_requests.post(
            constants.data['GRANT_CODE_URL'],
            payload,
            headers=constants.data['REQUEST_HEADERS_BASE'],
        )
        if res:
            data = json.loads(res)
            if data['status'] == 0:
                code = data['data']['code']
                user_id = data['data']['uid']

        return code, user_id

    async def __get_cred(self, code: str) -> Tuple[str, str]:
        cred = ''
        sign_token = ''

        payload = {'code': code, 'kind': 1}
        headers = {
            **constants.data['REQUEST_HEADERS_BASE'],
            'dId': await self.__get_did(),
        }
        res = await http_requests.post(
            constants.data['CRED_CODE_URL'], payload, headers=headers
        )
        if res:
            data = json.loads(res)
            if data['code'] == 0:
                cred = data['data']['cred']
                sign_token = data['data']['token']

        return cred, sign_token

    async def __get_did(self) -> str:
        template_path = RESOURCE_PATH / 'template.html'
        temp_path = RESOURCE_PATH / 'temp.html'
        html_content = template_path.read_text(encoding='utf-8')
        sm_conf = json.dumps(constants.data['SKLAND_SM_CONFIG']).replace("\\", "")
        html_content = html_content.replace('{{config}}', sm_conf)
        temp_path.write_text(html_content, encoding='utf-8')

        browser = basic_browser_service.browser
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(f'file://{temp_path}')
        await page.wait_for_selector('.did')
        element = await page.query_selector('.did')
        device_id = await element.inner_text()
        await context.close()
        temp_path.unlink(missing_ok=True)
        return device_id


@dataclass
class SKLandUser:
    code: str
    cred: str
    token: str
    user_id: str
    sign_token: str
    bot: AmiyaBotPluginInstance

    async def get_timestamp(self) -> str:
        config = self.bot.get_config('skland')
        if config.get('web_timestamp', False):
            res = await http_requests.get(constants.data['BINDING_URL'])
            if res:
                res = json.loads(res)
                return str(res['data']['timestamp'])
        return str(int(time.time()) - config.get('timestamp_delay', 2))

    async def generate_sign(
        self, path: str, body_or_query: str, timestamp: str
    ) -> Tuple[str, Dict[str, Any]]:
        header_ca = constants.data['SIGN_HEADERS_BASE'].copy()
        header_ca['timestamp'] = timestamp
        header_ca_str = json.dumps(header_ca, separators=(',', ':'))

        s = path + body_or_query + timestamp + header_ca_str
        hmac_sha256 = hmac.new(
            self.sign_token.encode('utf-8'), s.encode('utf-8'), hashlib.sha256
        ).hexdigest()
        md5_hash = hashlib.md5(hmac_sha256.encode('utf-8')).hexdigest()
        return md5_hash, header_ca

    async def get_headers(
        self, url: str, method: str = 'get', body: Optional[dict] = None
    ) -> Dict[str, str]:
        header = constants.data['REQUEST_HEADERS_BASE'].copy()
        header['cred'] = self.cred
        timestamp = await self.get_timestamp()
        url_parsed = parse.urlparse(url)

        if method.lower() == 'get':
            if body:
                body_or_query = parse.urlencode(body)
            else:
                body_or_query = url_parsed.query
        else:
            body_or_query = json.dumps(body, separators=(',', ':')) if body else ''

        sign, header_ca = await self.generate_sign(
            url_parsed.path, body_or_query, timestamp
        )
        header['sign'] = sign
        header.update(header_ca)
        return header

    async def request_url(self, url: str) -> Optional[dict]:
        headers = await self.get_headers(url)
        res = await http_requests.get(url, headers=headers)
        if res:
            try:
                data = json.loads(res)
                return data
            except Exception as e:
                log.warning(repr(e))

    async def check(self):
        data = await self.request_url(constants.data['CRED_CHECK_URL'])
        if data:
            return data['code'] == 0

    async def refresh_token(self):
        data = await self.request_url(constants.data['REFRESH_URL'])
        if data:
            if data['code'] == 0:
                self.token = data['data']['token']
                return self.token

    async def character_info(self, uid: str) -> Optional[dict]:
        data = await self.request_url(f'{constants.data["USER_INFO_URL"]}?uid={uid}')
        if data:
            if data['code'] == 0:
                return data['data']

    async def cultivate_player(self, uid: str) -> Optional[dict]:
        data = await self.request_url(f'{constants.data["PLAYER_URL"]}?uid={uid}')
        if data:
            if data['code'] == 0:
                return data['data']

    async def cultivate_character(self, char_id: str) -> Optional[dict]:
        data = await self.request_url(
            f'{constants.data["CHARACTER_URL"]}?characterld={char_id}'
        )
        if data:
            if data['code'] == 0:
                return data['data']

    async def binding(self) -> Optional[dict]:
        data = await self.request_url(constants.data['BINDING_URL'])
        if data:
            if data['code'] == 0:
                return data['data']
