import os
import configparser

from amiyabot import PluginInstance, Message, Chain
from core.util import any_match

curr_dir = os.path.dirname(__file__)

bot = PluginInstance(
    name='自定义回复',
    version='1.0',
    plugin_id='amiyabot-talking',
    plugin_type='official',
    description='可以自定义一问一答的简单对话',
    document=f'{curr_dir}/README.md'
)


async def check_talk(data: Message):
    config = configparser.ConfigParser()
    config.read(f'{curr_dir}/talking.ini', encoding='utf-8')

    key = any_match(data.text, config.sections())
    if key:
        setattr(data, 'reply', config.get(key, 'reply'))
        return True


@bot.on_message(verify=check_talk)
async def _(data: Message):
    reply: str = getattr(data, 'reply')

    return Chain(data).text(reply.replace('{nickname}', data.nickname))
