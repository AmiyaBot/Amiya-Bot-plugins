import os
import re

from amiyabot import Message, Chain
from core import AmiyaBotPluginInstance

curr_dir = os.path.dirname(__file__)


class TalkPluginInstance(AmiyaBotPluginInstance):
    ...


bot = TalkPluginInstance(
    name='自定义回复',
    version='1.4',
    plugin_id='amiyabot-talking',
    plugin_type='official',
    description='可以自定义一问一答的简单对话',
    document=f'{curr_dir}/README.md',
    instruction=f'{curr_dir}/README_USE.md',
    global_config_schema=f'{curr_dir}/config_schema.json',
    global_config_default=f'{curr_dir}/config_default.yaml'
)


async def check_talk(data: Message):
    configs: list = bot.get_config('configs')

    def set_reply(_item):
        setattr(data, 'reply', _item['reply'])
        setattr(data, 'is_at', _item['is_at'])
        return True

    for item in configs:
        if item['direct'] == '仅群聊' and data.is_direct:
            continue
        if item['direct'] == '仅私聊' and not data.is_direct:
            continue

        if item['keyword_type'] == '包含关键词':
            if item['keyword'] in data.text:
                return set_reply(item)
        if item['keyword_type'] == '等于关键词':
            if item['keyword'] == data.text:
                return set_reply(item)
        if item['keyword_type'] == '正则匹配':
            if re.search(re.compile(item['keyword']), data.text):
                return set_reply(item)


@bot.on_message(verify=check_talk, check_prefix=False, allow_direct=True)
async def _(data: Message):
    reply: str = getattr(data, 'reply')
    is_at: bool = getattr(data, 'is_at')

    if os.path.exists(reply):
        return Chain(data, at=is_at).image(reply)

    return Chain(data, at=is_at).text(reply.replace('{nickname}', data.nickname))
