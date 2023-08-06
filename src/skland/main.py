import os
import json

from amiyabot import TencentBotInstance
from amiyabot.database import *
from core import AmiyaBotPluginInstance, Message, Chain
from core.resource.arknightsGameData import ArknightsGameData
from core.database.user import UserBaseModel

from .api import SKLandAPI

curr_dir = os.path.dirname(__file__)


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
        return await SKLandAPI(token).get_user_info()
    
    @staticmethod
    async def get_character_info(token: str,uid: str):
        return await SKLandAPI(token).get_character_info(uid)


bot = SKLandPluginInstance(
    name='森空岛',
    version='1.4',
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


@bot.on_message(keywords=['我的游戏信息', '我的方舟信息', '我的游戏数据', '我的方舟数据'], level=5)
async def _(data: Message):
    token = await bot.get_token(data.user_id)
    if not token:
        return Chain(data).text('博士，您尚未绑定 Token，请发送 “兔兔绑定” 进行查看绑定说明。')

    user_info = await bot.get_user_info(token)
    if not user_info:
        return Chain(data).text('Token 无效，无法获取信息。>.<')

    return Chain(data).html(f'{curr_dir}/template/userInfo.html', user_info, width=650, height=300)


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
