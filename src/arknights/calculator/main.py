import os
import re

from amiyabot import PluginInstance
from core import Message, Chain

from .jade import calc_jade
from .money import calc_money

curr_dir = os.path.dirname(__file__)

bot = PluginInstance(
    name='明日方舟计算器',
    version='1.0',
    plugin_id='amiyabot-arknights-calculator',
    plugin_type='official',
    description='计算合成玉获得数量或龙门币花费数量等',
    document=f'{curr_dir}/README.md',
)


@bot.on_message(keywords=['/计算合成玉'], level=3)
async def action(data: Message):
    wait = await data.wait(Chain(data).text('博士，请说明需要计算从今天起的合成玉的截止日期，可以为时间、日期或节日'))
    if not wait or not wait.text:
        return None

    return await calc_jade(Chain(wait), wait.text)


@bot.on_message(keywords=re.compile(r'多少(合成)?玉'), allow_direct=True, level=3)
async def _(data: Message):
    reply = Chain(data)

    return await calc_jade(reply, data.text_original)


@bot.on_message(keywords=re.compile(r'(凑|计算|花掉|花费)\s*(\d+)\s*龙门币'), allow_direct=True, level=3)
async def _(data: Message):
    money = int(data.verify.keypoint[1])

    return Chain(data).text(calc_money(money))
