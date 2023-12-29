import json
import re
import os
import shutil
import traceback

from typing import List, Optional
from dataclasses import dataclass, asdict
from amiyabot.network.httpRequests import http_requests
from amiyabot.util import create_dir
from amiyabot.log import LoggerManager
from amiyabot import Message, Chain

from core import AmiyaBotPluginInstance, Requirement
from core import bot as main_bot

log = LoggerManager('ERNIEBot')
curr_dir = os.path.dirname(__file__)
resource_dir = 'resource/plugins/ERNIEBot'

create_dir(resource_dir)

if not os.path.exists(f'{resource_dir}/template'):
    shutil.copytree(f'{curr_dir}/template', f'{resource_dir}/template')


def generate_schema():
    filepath = f'{curr_dir}/config_schema.json'

    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        log.info(f'Failed to load JSON from {filepath}.')
        return None

    model_list_str = ['...']

    if 'amiyabot-blm-library' in main_bot.plugins:
        blm_library = main_bot.plugins['amiyabot-blm-library']
        model_list = blm_library.model_list()

        model_list_str = model_list_str + [model['model_name'] for model in model_list]

    try:
        data['properties']['model_name']['enum'] = model_list_str
    except KeyError as e:
        stack_trace = traceback.format_exc()
        log.info(f'Expected keys not found in the JSON structure: {e}\n{stack_trace}')

    return data


class ERNIEBotPluginInstance(AmiyaBotPluginInstance):
    def get_template(self):
        setting = self.get_config('setting')

        system_file = f'{resource_dir}/template/' + setting['system']
        template = None

        if setting['system'] and os.path.exists(system_file):
            with open(system_file, mode='r', encoding='utf-8') as file:
                template = file.read()
        else:
            system_file = f'{curr_dir}/template/Amiya.txt'
            if os.path.exists(system_file):
                with open(system_file, mode='r', encoding='utf-8') as file:
                    template = file.read()

        return template


bot = ERNIEBotPluginInstance(
    name='简易兔兔聊天',
    version='0.3',
    plugin_id='amiyabot-chat-bot',
    plugin_type='official',
    description='一个简易的使用BLM库进行聊天的插件',
    document=f'{curr_dir}/README.md',
    requirements=[Requirement('amiyabot-blm-library')],
    instruction=f'{curr_dir}/README_USE.md',
    global_config_schema=generate_schema,
    global_config_default=f'{curr_dir}/config_default.yaml',
)


@dataclass
class ERNIEBotMessage:
    content: str
    role: str = 'user'


@bot.on_message(keywords=re.compile('聊天$'))
async def _(data: Message):
    # confirm = await data.wait(Chain(data).text('开启聊天模式？对话期间其他所有功能均不可用，回复【确认】开始聊天'))
    # if not confirm or '确认' not in confirm.text:
    #     return
    if 'amiyabot-blm-library' not in main_bot.plugins:
        return Chain(data).text('未安装BLM库插件，无法使用聊天功能')

    blm_library = main_bot.plugins['amiyabot-blm-library']

    model = bot.get_config('model_name')

    model_obj = blm_library.get_model(model)
    if not model_obj:
        return Chain(data).text('指定的模型不存在')

    with open(f'{curr_dir}/prompt/chat.txt', mode='r', encoding='utf-8') as prompt_file:
        prompt = prompt_file.read()

    starting_prompt = bot.get_template()

    if not starting_prompt:
        return Chain(data).text('未找到人设模板文件')

    res = await blm_library.chat_flow(f'{starting_prompt}请向大家简单介绍一下你自己。', model)
    if not res:
        return

    await data.send(Chain(data, at=False).text(res))

    last_msg = None

    while True:
        talk = await data.wait_channel(force=True, clean=False, max_time=60)
        if not talk:
            res = await blm_library.chat_flow(f'{prompt}没人说话了，再见。', model)
            if res:
                await data.send(Chain(last_msg, at=False).text(res))
            return

        last_msg = talk.message

        messages = []
        images = []
        for item in [last_msg] + talk.event.data:
            if item.text_original in ['不聊了', '结束']:
                res = await blm_library.chat_flow(f'{prompt}聊天结束，再见。', model)
                if res:
                    await data.send(Chain(item, at=False).text(res))
                talk.close_event()
                return

            if item.text_original:
                messages.append(item.text_original)
            
            if item.image:
                images = images + item.image

        talk.event.clean()

        if messages:
            command = []
            command = [{"type":"text","text":prompt + '\n\n'.join(messages)}]
            if model_obj["supported_feature"].__contains__("vision"):
                command = command + [{"type":"image_url","url":imgPath} for imgPath in images]
                images = []
            res = await blm_library.chat_flow(command, model)
            if res:
                await data.send(Chain(last_msg, at=False).text(res))
