import os
import re
import configparser

from amiyabot import Message, Chain, Equal, event_bus
from amiyabot.util import extract_zip

from core import AmiyaBotPluginInstance, GitAutomation
from core.util import TimeRecorder
from core.database.bot import Admin

from .initialize import ArknightsGameData, ArknightsConfig

curr_dir = os.path.dirname(__file__)


def initialize_data():
    ArknightsConfig.initialize()
    ArknightsGameData.initialize()
    event_bus.publish('gameDataInitialized')


def download_gamedata():
    gamedata_path = 'resource/gamedata'
    repo = bot.get_config('repo')

    GitAutomation(gamedata_path, repo).update(['--depth 1'])

    if os.path.exists(f'{gamedata_path}/.gitmodules'):
        config = configparser.ConfigParser()
        config.read(f'{gamedata_path}/.gitmodules', encoding='utf-8')

        for submodule in config.values():
            path = submodule.get('path')
            url = submodule.get('url')
            if path:
                folder = f'{gamedata_path}/{path}'
                GitAutomation(folder, url).update(['--depth 1'])
                for root, _, files in os.walk(folder):
                    for file in files:
                        r = re.search(r'splice_\d+\.zip', file)
                        if r:
                            extract_zip(os.path.join(root, file), folder + '/skin', overwrite=True)

    event_bus.publish('gameDataFetched')


class ArknightsGameDataPluginInstance(AmiyaBotPluginInstance):
    def install(self):
        if bot.get_config('autoUpdate'):
            download_gamedata()
        else:
            initialize_data()


bot = ArknightsGameDataPluginInstance(
    name='明日方舟数据解析',
    version='1.5',
    plugin_id='amiyabot-arknights-gamedata',
    plugin_type='official',
    description='明日方舟游戏数据解析，为内置的静态类提供数据。',
    document=f'{curr_dir}/README.md',
    global_config_schema=f'{curr_dir}/config_schema.json',
    global_config_default=f'{curr_dir}/config_default.yaml',
    priority=999
)


@event_bus.subscribe('gameDataFetched')
def update(_):
    initialize_data()


@bot.on_message(keywords=Equal('更新资源'))
async def _(data: Message):
    if not bool(Admin.get_or_none(account=data.user_id)):
        return None

    await data.send(Chain(data).text('即将开始检查更新，更新过程中所有功能将会无响应...'))

    time_rec = TimeRecorder()

    download_gamedata()

    return Chain(data).text(f'更新完成，耗时{time_rec.total()}')
