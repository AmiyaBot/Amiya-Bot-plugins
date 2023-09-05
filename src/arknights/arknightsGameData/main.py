import os

from amiyabot import Message, Chain, Equal, event_bus

from core import AmiyaBotPluginInstance, GitAutomation, log
from core.util import TimeRecorder
from core.database.bot import Admin

from .builder import ArknightsGameData, ArknightsConfig, gamedata_path

curr_dir = os.path.dirname(__file__)
repo = 'https://gitee.com/amiya-bot/amiya-bot-assets.git'


def initialize_data():
    ArknightsConfig.initialize()
    ArknightsGameData.initialize()
    event_bus.publish('gameDataInitialized')


def download_gamedata():
    if os.path.exists(gamedata_path) and not os.path.exists(f'{gamedata_path}/version.txt'):
        log.warning(f'资源已不可用，请删除 {gamedata_path} 目录并发送“更新资源”或重启。')
        return

    GitAutomation(gamedata_path, repo).update(['--depth 1'])

    event_bus.publish('gameDataFetched')


class ArknightsGameDataPluginInstance(AmiyaBotPluginInstance):
    def install(self):
        if bot.get_config('autoUpdate') or not os.path.exists(gamedata_path):
            download_gamedata()
        else:
            initialize_data()


bot = ArknightsGameDataPluginInstance(
    name='明日方舟数据解析',
    version='1.8',
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

    if os.path.exists(gamedata_path) and not os.path.exists(f'{gamedata_path}/version.txt'):
        return Chain(data).text(f'资源已不可用，请删除 {gamedata_path} 目录并重试。')

    await data.send(Chain(data).text('即将开始检查更新，更新过程中所有功能将会无响应...'))

    time_rec = TimeRecorder()

    download_gamedata()

    return Chain(data).text(f'更新完成，耗时{time_rec.total()}')


@bot.on_message(keywords=Equal('解析资源'))
async def _(data: Message):
    if not bool(Admin.get_or_none(account=data.user_id)):
        return None

    await data.send(Chain(data).text('即将开始解析资源，解析过程中所有功能将会无响应...'))

    time_rec = TimeRecorder()

    initialize_data()

    return Chain(data).text(f'解析完成，耗时{time_rec.total()}')
