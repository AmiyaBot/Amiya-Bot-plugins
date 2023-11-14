import re
import os
import shutil


from typing import List, Optional
from dataclasses import dataclass, asdict
from amiyabot.network.httpRequests import http_requests
from amiyabot.util import create_dir
from amiyabot.log import LoggerManager
from amiyabot import Message, Chain

from core import AmiyaBotPluginInstance

from .models import MODELS

log = LoggerManager('ERNIEBot')
curr_dir = os.path.dirname(__file__)
resource_dir = 'resource/plugins/ERNIEBot'

create_dir(resource_dir)

if not os.path.exists(f'{resource_dir}/template'):
    shutil.copytree(f'{curr_dir}/template', f'{resource_dir}/template')


class ERNIEBotPluginInstance(AmiyaBotPluginInstance):
    def new_chat(self):
        chat_bot = ERNIEBot(
            self.get_config('client_id'),
            self.get_config('client_secret'),
            self.get_config('model_name'),
            self.get_config('model_api'),
        )

        setting = self.get_config('setting')

        chat_bot.temperature = float(setting['temperature'])
        chat_bot.top_p = float(setting['top_p'])
        chat_bot.penalty_score = float(setting['penalty_score'])
        chat_bot.user_id = setting['user_id']

        system_file = f'{resource_dir}/template/' + setting['system']
        if setting['system'] and os.path.exists(system_file):
            with open(system_file, mode='r', encoding='utf-8') as file:
                chat_bot.system = file.read()

        return chat_bot

    @staticmethod
    def custom_chat(
        client_id: str,
        client_secret: str,
        model_name: str,
        model_api: str = '',
    ):
        return ERNIEBot(client_id, client_secret, model_name, model_api)


bot = ERNIEBotPluginInstance(
    name='千帆大模型 Beta',
    version='0.1',
    plugin_id='amiyabot-ernie-bot',
    plugin_type='official',
    description='百度智能云千帆大模型平台 API，默认调用 ERNIE-Bot 4.0 进行聊天对话',
    document=f'{curr_dir}/README.md',
    instruction=f'{curr_dir}/README_USE.md',
    global_config_schema=f'{curr_dir}/config_schema.json',
    global_config_default=f'{curr_dir}/config_default.yaml',
)


@dataclass
class ERNIEBotMessage:
    content: str
    role: str = 'user'


class ERNIEBot:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        model_name: str,
        model_api: str = '',
    ):
        self.temperature: float = float(0.95)
        self.top_p: float = float(0.8)
        self.penalty_score: float = float(1.0)
        self.system: str = ''
        self.user_id: str = ''

        self.__completions_url = model_api or MODELS[model_name]

        self.__client_id = client_id
        self.__client_secret = client_secret
        self.__access_token = ''

        self.__history: List[ERNIEBotMessage] = []

    @property
    def chat_payload(self):
        return {
            'temperature': self.temperature,
            'top_p': self.top_p,
            'penalty_score': self.penalty_score,
            'stream': False,
            'system': self.system,
            'user_id': self.user_id,
            'messages': [asdict(item) for item in self.__history],
        }

    async def get_access_token(self):
        if self.__access_token:
            return self.__access_token

        params = {
            'grant_type': 'client_credentials',
            'client_id': self.__client_id,
            'client_secret': self.__client_secret,
        }

        log.info('requesting access_token...')

        res = await http_requests.post('https://aip.baidubce.com/oauth/2.0/token', {}, params=params)
        if res:
            self.__access_token = res.json['access_token']
            return self.__access_token

        log.warning('access_token request failed.')

    async def chat(self, message: str) -> Optional[str]:
        token = await self.get_access_token()
        if token:
            self.__history.append(ERNIEBotMessage(message))

            res = await http_requests.post(self.__completions_url, self.chat_payload, params={'access_token': token})
            if res:
                result = res.json
                log.info(
                    '{object} tokens usage -- '
                    'prompt: {prompt_tokens} '
                    'completion: {completion_tokens} '
                    'total: {total_tokens}'.format(object=result['object'], **result['usage'])
                )
                log.debug('chat reply: {result}'.format(result=result['result']))

                self.__history.append(ERNIEBotMessage(result['result'], 'assistant'))

                return result['result']
            else:
                self.__history.pop(-1)

    async def clear_history(self):
        self.__history = []


@bot.on_message(keywords=re.compile('聊天$'))
async def _(data: Message):
    # confirm = await data.wait(Chain(data).text('开启聊天模式？对话期间其他所有功能均不可用，回复【确认】开始聊天'))
    # if not confirm or '确认' not in confirm.text:
    #     return

    with open(f'{curr_dir}/prompt/chat.txt', mode='r', encoding='utf-8') as prompt_file:
        prompt = prompt_file.read()

    chat_bot = bot.new_chat()
    res = await chat_bot.chat(f'{prompt}请向大家简单介绍一下你自己。')
    if not res:
        return

    await data.send(Chain(data, at=False).text(res))

    last_msg = None

    while True:
        talk = await data.wait_channel(force=True, clean=False, max_time=60)
        if not talk:
            res = await chat_bot.chat(f'{prompt}没人说话了，再见。')
            if res:
                await data.send(Chain(last_msg, at=False).text(res))
            return

        last_msg = talk.message

        messages = []
        for item in [last_msg] + talk.event.data:
            if item.text_original in ['不聊了', '结束']:
                res = await chat_bot.chat(f'{prompt}聊天结束，再见。')
                if res:
                    await data.send(Chain(item, at=False).text(res))
                talk.close_event()
                return

            if item.text_original:
                messages.append(item.text_original)

        talk.event.clean()

        if messages:
            res = await chat_bot.chat(prompt + '\n\n'.join(messages))
            if res:
                await data.send(Chain(last_msg, at=False).text(res))
