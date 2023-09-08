import os
import shutil

from amiyabot import Message, Chain, Equal, event_bus

from core.util import TimeRecorder
from core.database.bot import Admin

from .builder import bot, initialize_data, download_gamedata, gamedata_path


@event_bus.subscribe('gameDataFetched')
def update(_):
    initialize_data()


@bot.on_message(keywords=Equal('更新资源'))
async def _(data: Message):
    if not bool(Admin.get_or_none(account=data.user_id)):
        return None

    if os.path.exists(gamedata_path) and not os.path.exists(f'{gamedata_path}/version.txt'):
        # noinspection PyBroadException
        try:
            shutil.rmtree(gamedata_path)
        except Exception:
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


@bot.on_message(keywords=Equal('清除立绘缓存'))
async def _(data: Message):
    if not bool(Admin.get_or_none(account=data.user_id)):
        return None

    time_rec = TimeRecorder()

    shutil.rmtree(f'{gamedata_path}/skin')

    return Chain(data).text(f'已清除立绘缓存，耗时{time_rec.total()}')
