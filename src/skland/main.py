import json

from typing import Iterable

from amiyabot import ChainBuilder, GroupConfig
from amiyabot.adapters.tencent.qqGuild import QQGuildBotInstance
from amiyabot.database import *

from core import Message, Chain, AmiyaBotPluginInstance, Requirement
from core.util import snake_case_to_pascal_case, integer
from core.database.user import UserBaseModel
from core.resource.arknightsGameData import ArknightsGameData, ArknightsGameDataResource, ArknightsConfig

from .api import SKLandAPI, log
from .tools import *
from .gacha import get_gacha_official, get_gacha_arkgacha_kwer_top

skland_api = SKLandAPI()


@table
class UserToken(UserBaseModel):
    user_id: str = CharField(primary_key=True)
    token: str = CharField(null=True)
    bilibili_token: str = TextField(null=True)  # B服Token特别长，CharField存不下


class SKLandPluginInstance(AmiyaBotPluginInstance):
    @staticmethod
    async def get_token(user_id: str):
        rec: UserToken = UserToken.get_or_none(user_id=user_id)
        if rec:
            return rec.token

    @staticmethod
    async def refresh_token(user_id: str):
        rec: UserToken = UserToken.get_or_none(user_id=user_id)
        if rec:
            user = await skland_api.user(rec.token)
            if not user:
                log.warning('森空岛用户获取失败。')
                return False

            new_token = await user.refresh_token()
            if new_token:
                rec.token = new_token
                rec.save()
                return True

        return False

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

    @staticmethod
    async def get_cultivate_player(token: str, uid: str):
        user = await skland_api.user(token)
        if not user:
            log.warning('森空岛用户获取失败。')
            return None

        return await user.cultivate_player(uid)

    @staticmethod
    async def get_cultivate_character(token: str, char_id: str):
        user = await skland_api.user(token)
        if not user:
            log.warning('森空岛用户获取失败。')
            return None

        return await user.cultivate_character(char_id)

    @staticmethod
    async def get_binding(token: str):
        user = await skland_api.user(token)
        if not user:
            log.warning('森空岛用户获取失败。')
            return None

        return await user.binding()

    @staticmethod
    async def get_server_type(token: str, uid: str = None):
        app_code = 'arknights'

        data = await SKLandPluginInstance.get_binding(token)
        for app in data['list']:
            if app['appCode'] == app_code:
                if uid is None:
                    uid = app['defaultUid']
                for binding in app['bindingList']:
                    if binding['uid'] == uid:
                        return binding['channelName'], binding['nickName']

        return None, None


class WaitALLRequestsDone(ChainBuilder):
    @classmethod
    async def on_page_rendered(cls, page):
        await page.wait_for_load_state('networkidle')


bot = SKLandPluginInstance(
    name='森空岛',
    version='5.0',
    plugin_id='amiyabot-skland',
    plugin_type='official',
    description='通过森空岛 API 查询玩家信息展示游戏数据',
    document=f'{curr_dir}/README.md',
    instruction=f'{curr_dir}/README_USE.md',
    requirements=[Requirement('amiyabot-arknights-gamedata', official=True)],
    global_config_default=f'{curr_dir}/config_templates/global_config_default.json',
    global_config_schema=f'{curr_dir}/config_templates/global_config_schema.json',
)
bot.set_group_config(GroupConfig('skland', allow_direct=True))


async def is_token_str(data: Message):
    try:
        res = json.loads(data.text_original)
        token = res['data']['content']

        assert isinstance(token, str) and '鹰角网络通行证账号' in res['msg']

        return True, 10, token
    except Exception:
        pass

    return False


async def check_user_info(data: Message, times: int = 1):
    token = await bot.get_token(data.user_id)
    if not token:
        await data.send(Chain(data).text('博士，您尚未绑定 Token，请发送 “兔兔绑定” 查看绑定说明。'))
        return None, None

    user_info = await bot.get_user_info(token)
    if not user_info:
        if times == 1 and await bot.refresh_token(data.user_id):
            return await check_user_info(data, times + 1)

        await data.send(
            Chain(data).text(
                'Token 无效，无法获取信息，请重新绑定 Token。>.<\n'
                '如遇到一直绑定不成功，请尝试退出森空岛APP重新登录后再获取 Token。'
            )
        )
        return None, token

    return user_info, token


@bot.on_message(group_id='skland', keywords=['我的游戏信息', '森空岛'], level=5)
async def _(data: Message):
    user_info, token = await check_user_info(data)
    if not user_info:
        return

    await data.send(Chain(data).text('开始获取并生成游戏信息，请稍后...'))

    character_info = await bot.get_character_info(token, user_info['gameStatus']['uid'])
    character_info['backgroundImage'] = await ArknightsGameDataResource.get_skin_file(
        {'skin_id': character_info['status']['secretary']['charId'] + '#1'}, encode_url=True
    )

    return (
        Chain(data, chain_builder=WaitALLRequestsDone())
        .html(f'{curr_dir}/template/userInfo.html', character_info, width=800, height=400, render_time=1000)
        .text('博士，森空岛数据可能与游戏内数据存在一点延迟，请以游戏内实际数据为准。')
    )


@bot.on_message(group_id='skland', keywords=['我的仓库'], level=5)
async def _(data: Message):
    user_info, token = await check_user_info(data)
    if not user_info:
        return

    await data.send(Chain(data).text('开始获取并生成仓库信息，请稍后...'))

    cultivate_data = await bot.get_cultivate_player(token, user_info['gameStatus']['uid'])

    result = []
    for item in cultivate_data['items']:
        if item['count'] != '0' and item['id'] in ArknightsGameData.materials:
            result.append({**item, **ArknightsGameData.materials[item['id']]})

    return (
        Chain(data, chain_builder=WaitALLRequestsDone())
        .html(f'{curr_dir}/template/warehouse.html', result, width=1140, render_time=1000)
        .text('博士，森空岛数据可能与游戏内数据存在一点延迟，请以游戏内实际数据为准。')
    )


@bot.on_message(group_id='skland', keywords=['我的干员', '练度'], level=5)
async def _(data: Message):
    user_info, token = await check_user_info(data)
    if not user_info:
        return

    await data.send(Chain(data).text('开始获取并生成干员练度信息，请稍后...'))

    character_info = await bot.get_character_info(token, user_info['gameStatus']['uid'])

    char_name = get_longest(data.text, ArknightsGameData.operators.keys())
    if char_name:
        amiya_promotion = {
            'char_1001_amiya2': '阿米娅近卫',
            'char_1037_amiya3': '阿米娅医疗',
        }
        char_list = {
            (
                character_info['charInfoMap'][item['charId']]['name']
                if item['charId'] not in amiya_promotion
                else amiya_promotion[item['charId']]
            ): item
            for item in character_info['chars']
        }
        if char_name in char_list:
            char = char_list[char_name]
            char_info = ArknightsGameData.operators[char_name]
            skins = {
                item['id']: character_info['skinInfoMap'][item['id']]
                for item in character_info['skins']
                if item['id'].startswith(char['charId'])
            }
            equips = {item['id']: {**character_info['equipmentInfoMap'][item['id']], **item} for item in char['equip']}
            skin_file = await ArknightsGameDataResource.get_skin_file({'skin_id': char['skinId']})
            result = {
                'user': character_info['status'],
                'char': char,
                'skins': skins,
                'equips': equips,
                'charData': char_info.data,
                'charSkins': char_info.skins(),
                'charModules': {},
                'charSkinFacePos': face_detect(os.path.abspath(skin_file)),
                'backgroundImage': skin_file.replace('#', '%23'),
            }

            for module in char_info.modules() or []:
                if module['uniEquipId'] not in result['charModules']:
                    result['charModules'][module['uniEquipId']] = {}

                if module['detail']:
                    for lv, attrs in enumerate(module['detail']['phases']):
                        module_attr = {}
                        for attr in attrs['attributeBlackboard']:
                            module_attr[snake_case_to_pascal_case(attr['key'])] = integer(attr['value'])

                        result['charModules'][module['uniEquipId']][lv] = module_attr

            return Chain(data, chain_builder=WaitALLRequestsDone()).html(
                f'{curr_dir}/template/charInfo.html', result, width=1200, height=600
            )
        else:
            return Chain(data).text(f'博士，您尚未招募干员【{char_name}】')

    character_info.update(
        {
            'limitChars': ArknightsConfig.limit,
        }
    )

    return Chain(data, chain_builder=WaitALLRequestsDone()).html(
        f'{curr_dir}/template/chars.html', character_info, width=1640, render_time=1000
    )


@bot.on_message(group_id='skland', keywords=['我的基建'], level=5)
async def _(data: Message):
    user_info, token = await check_user_info(data)
    if not user_info:
        return

    await data.send(Chain(data).text('开始获取并生成基建信息，请稍后...'))

    character_info = await bot.get_character_info(token, user_info['gameStatus']['uid'])

    return Chain(data, chain_builder=WaitALLRequestsDone()).html(
        f'{curr_dir}/template/building.html', character_info, width=1800, height=800, render_time=1000
    )


@bot.on_message(group_id='skland', keywords=['抽卡记录'], level=5)
async def _(data: Message):
    user_info, token = await check_user_info(data)
    if not user_info:
        return

    # map: dict = UserInfo.get_meta_value(data.user_id, 'amiyabot_query_gacha')
    if not token:
        return

    server_name, _ = await bot.get_server_type(token, user_info['gameStatus']['uid'])

    if server_name == 'bilibili服':
        rec: UserToken = UserToken.get_or_none(user_id=data.user_id)
        if rec.bilibili_token:
            token = rec.bilibili_token
        else:
            await data.send(
                Chain(data).text(
                    '您是BiliBili服玩家，还需要提供B服Token才能查询抽卡记录，请发送 “兔兔绑定” 并查看其中关于获取B服Token的相关说明。>.<'
                )
            )
            return

    try:
        info = {}

        kwer_config = bot.get_config('arkgacha_kwer_top')

        if kwer_config['enable']:
            appid = kwer_config['app_id']
            appsecret = kwer_config['app_secret']
            gacha_list, pool_list = await get_gacha_arkgacha_kwer_top(server_name, token, appid, appsecret)
            info['copyright'] = (
                '历史数据来自鹰角网络官网<br/>以及<span style="color: blue;">https://arkgacha.kwer.top/</span><br/>感谢Bilibili@呱行次比猫'
            )
        else:
            gacha_list, pool_list = await get_gacha_official(server_name, token)
            info['copyright'] = '历史数据来自鹰角网络官网'

        if not gacha_list:
            return Chain(data).text('呜呜……出错了……可能是因为Token失效，请重新绑定 Token。>.<')

        info['list'] = gacha_list
        log.info(f'info: {info}')
        return Chain(data).html(f'{curr_dir}/template/gacha.html', info, width=320)
    except Exception as e:
        log.error(e)
        return Chain(data).text('呜呜……出错了……可能是因为Token失效，请重新绑定 Token。>.<')


@bot.on_message(group_id='skland', keywords=['我的进度', '我的关卡'], level=5)
async def _(data: Message):
    user_info, token = await check_user_info(data)
    if not user_info:
        return

    await data.send(Chain(data).text('开始获取并生成关卡进度信息，请稍后...'))

    character_info = await bot.get_character_info(token, user_info['gameStatus']['uid'])

    return Chain(data, chain_builder=WaitALLRequestsDone()).html(
        f'{curr_dir}/template/progress.html', character_info, width=1200, render_time=1000
    )


@bot.on_message(group_id='skland', keywords='绑定', allow_direct=True)
async def _(data: Message):
    chain = (
        Chain(data)
        .text('登录森空岛APP扫描二维码，在帖子获取 Token。')
        .image(f'{curr_dir}/img/CBA81C37838652151932DF4C2077E3B7.jpg')
    )

    if not isinstance(data.instance, QQGuildBotInstance):
        chain.text(
            '森空岛绑定:\n'
            'https://www.skland.com/\n'
            'https://web-api.skland.com/account/info/hg\n'
            'B服Token获取:\n'
            'https://ak.hypergryph.com/user/login\n'
            'https://web-api.hypergryph.com/account/info/ak-b'
        )

    return chain


@bot.on_message(group_id='skland', verify=is_token_str, check_prefix=False, allow_direct=True)
async def _(data: Message):
    if not data.is_direct:
        await data.recall()
        await data.send(Chain(data).text('博士，请注意保护您的敏感信息！>.<'))

    token = data.verify.keypoint

    rec: UserToken = UserToken.get_or_none(user_id=data.user_id)
    if rec:
        if len(token) > 200:
            rec.bilibili_token = token
        else:
            rec.token = token
        rec.save()
    else:
        if len(token) > 200:
            UserToken.create(user_id=data.user_id, token=None, bilibili_token=token)
        else:
            UserToken.create(user_id=data.user_id, token=token, bilibili_token=None)

    if len(token) > 200:
        return Chain(data).text('B服Token 绑定成功！')
    else:
        return Chain(data).text('Token 绑定成功！')


def get_longest(text: str, items: Iterable):
    res = ''
    for item in items:
        if item in text and len(item) >= len(res):
            res = item

    return res
