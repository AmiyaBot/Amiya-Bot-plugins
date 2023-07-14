import os

from amiyabot import PluginInstance, Message, Chain, Equal, event_bus
from core import load_resource
from core.util import TimeRecorder
from core.database.bot import Admin

from .initialize import ArknightsGameData, ArknightsConfig

curr_dir = os.path.dirname(__file__)


def initialize_data():
    ArknightsConfig.initialize()
    ArknightsGameData.initialize()
    event_bus.publish('gameDataInitialized')


class ArknightsGameDataPluginInstance(PluginInstance):
    def install(self):
        initialize_data()


bot = ArknightsGameDataPluginInstance(
    name='明日方舟数据解析',
    version='1.0',
    plugin_id='amiyabot-arknights-gamedata',
    plugin_type='official',
    description='明日方舟游戏数据解析，为内置的静态类提供数据。',
    document=f'{curr_dir}/README.md',
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

    load_resource()

    return Chain(data).text(f'更新完成，耗时{time_rec.total()}')
