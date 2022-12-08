import os
import shutil
import configparser

from amiyabot import PluginInstance, Message, Chain
from core.util import any_match, create_dir

curr_dir = os.path.dirname(__file__)
ini_file = 'resource/plugins/talking/talking.ini'


class TalkPluginInstance(PluginInstance):
    def install(self):
        if not os.path.exists(ini_file):
            create_dir(ini_file, is_file=True)
            shutil.copy(f'{curr_dir}/talking.ini', ini_file)


bot = TalkPluginInstance(
    name='自定义回复',
    version='1.1',
    plugin_id='amiyabot-talking',
    plugin_type='official',
    description='可以自定义一问一答的简单对话',
    document=f'{curr_dir}/README.md'
)


async def check_talk(data: Message):
    config = configparser.ConfigParser()
    config.read(ini_file, encoding='utf-8')

    key = any_match(data.text, config.sections())
    if key:
        setattr(data, 'reply', config.get(key, 'reply'))
        return True


@bot.on_message(verify=check_talk, check_prefix=False)
async def _(data: Message):
    reply: str = getattr(data, 'reply')

    return Chain(data).text(reply.replace('{nickname}', data.nickname))
