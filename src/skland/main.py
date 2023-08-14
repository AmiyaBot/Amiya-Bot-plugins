import os
import json

from amiyabot import TencentBotInstance, ChainBuilder
from amiyabot.database import *
from core import AmiyaBotPluginInstance, Message, Chain
from core.database.user import UserBaseModel

from .api import SKLandAPI, log

curr_dir = os.path.dirname(__file__)
skland_api = SKLandAPI()


@table
class UserToken(UserBaseModel):
    user_id: str = CharField(primary_key=True)
    token: str = CharField(null=True)


class SKLandPluginInstance(AmiyaBotPluginInstance):
    @staticmethod
    async def get_token(user_id: str):
        rec: UserToken = UserToken.get_or_none(user_id=user_id)
        if rec:
            return rec.token

    @staticmethod
    async def get_user_info(token: str):
        user = await skland_api.user(token)
        if not user:
            log.warning('森空岛用户获取失败。')
            return None

        return await user.user_info()

    @staticmethod
    async def get_character_info(token: str, uid: str):
        user = await skland_api.user(token)
        if not user:
            log.warning('森空岛用户获取失败。')
            return None

        return await user.character_info(uid)


class WaitALLRequestsDone(ChainBuilder):
    @classmethod
    async def on_page_rendered(cls, page):
        await page.wait_for_load_state('networkidle')


bot = SKLandPluginInstance(
    name='森空岛（Beta）',
    version='2.2',
    plugin_id='amiyabot-skland',
    plugin_type='official',
    description='通过森空岛 API 查询玩家信息展示游戏数据',
    document=f'{curr_dir}/README.md',
    instruction=f'{curr_dir}/README_USE.md',
)


async def is_token_str(data: Message):
    try:
        res = json.loads(data.text)
        token = res['data']['content']

        return True, 10, token
    except Exception:
        pass

    return False


async def check_user_info(data: Message):
    token = await bot.get_token(data.user_id)
    if not token:
        await data.send(Chain(data).text('博士，您尚未绑定 Token，请发送 “兔兔绑定” 查看绑定说明。'))
        return None, None

    user_info = await bot.get_user_info(token)
    if not user_info:
        await data.send(Chain(data).text('Token 无效，无法获取信息，请重新绑定或确认您是否具备森空岛测试资格。>.<'))
        return None, token

    return user_info, token


@bot.on_message(keywords=['我的游戏信息'], level=5)
async def _(data: Message):
    user_info, token = await check_user_info(data)
    if not user_info:
        return

    character_info = await bot.get_character_info(token, user_info['gameStatus']['uid'])

    from core.util import create_test_data
    create_test_data(character_info, 'log/test.js')

    return Chain(data, chain_builder=WaitALLRequestsDone()) \
        .html(f'{curr_dir}/template/userInfo.html', character_info, width=800, height=400, render_time=1000) \
        .text('博士，森空岛数据可能与游戏内数据存在一点延迟，请以游戏内实际数据为准。')


@bot.on_message(keywords=['我的干员信息'], level=5)
async def _(data: Message):
    user_info, token = await check_user_info(data)
    if not user_info:
        return

    await data.send(Chain(data).text('开始获取并生成干员信息，请稍后...'))

    character_info = await bot.get_character_info(token, user_info['gameStatus']['uid'])
    render_data = {
        'data': character_info,
        'minEvolvePhase': 2,
        'minRarity': 3
    }

    tips = '测试阶段仅筛选了精英二和四星以上干员，后续可开放查询。'

    return Chain(data, chain_builder=WaitALLRequestsDone()) \
        .html(f'{curr_dir}/template/chars.html', render_data, width=1580, render_time=1000) \
        .text(tips)


@bot.on_message(keywords='绑定', allow_direct=True)
async def _(data: Message):
    with open(f'{curr_dir}/README_TOKEN.md', mode='r', encoding='utf-8') as md:
        content = md.read()

    chain = Chain(data).text('博士，请阅读使用说明。').markdown(content)

    if not isinstance(data.instance, TencentBotInstance):
        chain.text('https://www.skland.com/\nhttps://web-api.skland.com/account/info/hg')

    return chain


@bot.on_message(verify=is_token_str, check_prefix=False, allow_direct=True)
async def _(data: Message):
    if not data.is_direct:
        await data.recall()
        await data.send(Chain(data).text('博士，请注意保护您的敏感信息！>.<'))

    UserToken.delete().where(UserToken.user_id == data.user_id).execute()
    UserToken.create(
        user_id=data.user_id,
        token=data.verify.keypoint
    )

    return Chain(data).text('Token 绑定成功！')
