import re
import os
import json
import asyncio

from typing import List
from amiyabot import QQGuildBotInstance, GroupConfig
from amiyabot.network.httpRequests import http_requests
from core import log, Message, Chain, Equal, AmiyaBotPluginInstance
from core.util import any_match, create_dir
from core.resource import remote_config
from core.database.user import UserInfo, UserGachaInfo
from core.database.bot import OperatorConfig, Admin

from .gachaBuilder import GachaBuilder, curr_dir, Pool, PoolSpOperator, bot_caller
from .box import get_user_box

pool_image = 'resource/plugins/gacha/pool'
create_dir(pool_image)


class GachaPluginInstance(AmiyaBotPluginInstance):
    @staticmethod
    async def sync_pool(force: bool = False):
        if not force:
            if Pool.get_or_none():
                return False

        res = await http_requests.get(remote_config.remote.plugin + '/api/v1/gacha')
        if res:
            async with log.catch('pool sync error:'):
                res = json.loads(res)['data']

                OperatorConfig.delete().execute()
                PoolSpOperator.delete().execute()
                Pool.delete().execute()

                OperatorConfig.batch_insert(res['OperatorConfig'])
                Pool.batch_insert(res['Pool'])

                return True

    def install(self):
        asyncio.create_task(self.sync_pool())
        bot_caller['plugin_instance'] = self


bot = GachaPluginInstance(
    name='明日方舟模拟抽卡',
    version='2.4',
    plugin_id='amiyabot-arknights-gacha',
    plugin_type='official',
    description='明日方舟抽卡模拟，可自由切换卡池',
    document=f'{curr_dir}/README.md',
    instruction=f'{curr_dir}/README_USE.md',
    global_config_default=f'{curr_dir}/config/global_config_default.json',
    global_config_schema=f'{curr_dir}/config/global_config_schema.json',
)

re_list = [r'抽卡\d+次', r'寻访\d+次', r'抽\d+次', r'\d+次寻访', r'\d+连寻访', r'\d+连抽', r'\d+连', r'\d+抽']

bot.set_group_config(GroupConfig('gacha', allow_direct=True))


def find_once(reg, text):
    r = re.compile(reg)
    f = r.findall(text)
    if len(f):
        return f[0]
    return ''


def change_pool(item: Pool, user_id=None):
    task = UserGachaInfo.update(gacha_pool=item.id).where((UserGachaInfo.user_id == user_id) if user_id else None)
    task.execute()

    pic = []
    for root, dirs, files in os.walk(pool_image):
        for file in files:
            if item.pool_name in file:
                pic.append(os.path.join(root, file))

    text = [
        f'{"所有" if not user_id else ""}博士的卡池已切换为{"【限定】" if item.limit_pool != 0 else ""}【{item.pool_name}】\n'
    ]
    if item.pickup_6:
        text.append('[[cl ★★★★★★@#FF4343 cle]] %s' % item.pickup_6.replace(',', '、'))
    if item.pickup_5:
        text.append('[[cl ★★★★★@#FEA63A cle]　] %s' % item.pickup_5.replace(',', '、'))
    if item.pickup_4:
        text.append('[[cl ☆☆☆☆@#A288B5 cle]　　] %s' % item.pickup_4.replace(',', '、'))

    return '\n'.join(text), pic[-1] if pic else ''


@bot.on_message(group_id='gacha', keywords=['抽', '连', '寻访'], level=3)
async def _(data: Message):
    try:
        gc = GachaBuilder(data)
    except Exception as e:
        log.error(e)
        return Chain(data).text('无法初始化卡池')

    coupon = gc.user_gacha.coupon
    message = data.text_digits

    reply = Chain(data)

    times = 0

    for item in re_list:
        r = re.search(item, message)
        if r:
            times = int(find_once(r'\d+', find_once(item, message)))

    if not times:
        if '单抽' in data.text:
            times = 1

    if times:
        user_info: UserInfo = UserInfo.get_user(data.user_id)

        coupon_need = times
        point_need = 0

        if times > 300:
            return reply.text('博士不要着急，罗德岛的资源要好好规划使用哦，先试试 300 次以内的寻访吧 (#^.^#)')
        if times > coupon:
            coupon_need = coupon
            point_need = (times - coupon) * 600

            if user_info.jade_point >= point_need:
                await data.send(Chain(data).text(f'寻访凭证剩余{coupon}张，将消耗{point_need}合成玉'))
            else:
                return reply.text(
                    f'博士，您的寻访资源不够哦~\n寻访凭证剩余{coupon}张\n合成玉剩余{user_info.jade_point}'
                )

        if times <= 10:
            return gc.detailed_mode(times, coupon_need, point_need)
        else:
            return gc.continuous_mode(times, coupon_need, point_need)

    if any_match(message, ['多少', '几']):
        text = '博士的寻访凭证还剩余 %d 张~' % coupon
        if coupon:
            text += '\n博士，快去获得您想要的干员吧 ☆_☆'
        return reply.text(text)


@bot.on_message(group_id='gacha', keywords=['保底'])
async def _(data: Message):
    user: UserGachaInfo = UserGachaInfo.get_or_create(user_id=data.user_id)[0]

    break_even_rate = 98
    if user.gacha_break_even > 50:
        break_even_rate -= (user.gacha_break_even - 50) * 2

    return Chain(data).text(
        f'当前已经抽取了 {user.gacha_break_even} 次而未获得六星干员\n下次抽出六星干员的概率为 {100 - break_even_rate}%'
    )


@bot.on_message(group_id='gacha', keywords=['卡池', '池子'], level=5)
async def _(data: Message):
    all_pools: List[Pool] = Pool.select()

    message = data.text

    if any_match(message, ['切换', '更换']):
        selected = None
        for item in all_pools:
            if item.pool_name in data.text_original:
                selected = item

        if not selected:
            r = re.search(r'(\d+)', data.text_digits)
            if r:
                index = int(r.group(1)) - 1
                if 0 <= index < len(all_pools):
                    selected = all_pools[index]

        if selected:
            all_people = False
            if type(data.instance) is QQGuildBotInstance:
                if bool(Admin.get_or_none(account=data.user_id)):
                    all_people = '所有人' in data.text

            change_res = change_pool(selected, data.user_id if not all_people else None)
            if change_res[1]:
                return Chain(data).image(change_res[1]).text_image(change_res[0])
            return Chain(data).text_image(change_res[0])

    text = '博士，这是可更换的卡池列表：\n\n'
    text += '|卡池名称|卡池名称|卡池名称|卡池名称|\n|----|----|----|----|\n'

    for index, item in enumerate(all_pools):
        text += f'|<span style="color: red; padding-right: 5px; font-weight: bold;">{index + 1}</span> {item.pool_name}'
        if (index + 1) % 4 == 0:
            text += '|\n'

    text += '\n\n> 如需切换卡池，请回复【<span style="color: red">序号</span>】或和阿米娅说「阿米娅切换卡池 "卡池名称" 」\n或「阿米娅切换第 N 个卡池」'

    wait = await data.wait(Chain(data).markdown(text))
    if wait:
        r = re.search(r'(\d+)', wait.text_digits)
        if r:
            index = int(r.group(1)) - 1
            if 0 <= index < len(all_pools):
                change_res = change_pool(all_pools[index], data.user_id)
                if change_res[1]:
                    return Chain(data).image(change_res[1]).text_image(change_res[0])
                return Chain(data).text_image(change_res[0])
            else:
                return Chain(data).text('博士，要告诉阿米娅准确的卡池序号哦')


@bot.on_message(group_id='gacha', keywords=['box'])
async def _(data: Message):
    res = get_user_box(data.user_id)

    if type(res) is str:
        return Chain(data).text(res)

    return Chain(data).image(res)


@bot.on_message(keywords=Equal('同步卡池'))
async def _(data: Message):
    if Admin.get_or_none(account=data.user_id):
        confirm = await data.wait(Chain(data).text('同步将使用官方DEMO的数据覆盖现有设置，回复"确认"开始同步。'))
        if confirm is not None and confirm.text == '确认':
            await data.send(Chain(data).text(f'开始同步...'))

            if await GachaPluginInstance.sync_pool(force=True):
                await data.send(Chain(data).text(f'同步成功。'))
            else:
                await data.send(Chain(data).text(f'同步失败，数据请求失败。'))
