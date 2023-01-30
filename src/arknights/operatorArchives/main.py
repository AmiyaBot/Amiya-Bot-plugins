import asyncio

from amiyabot import GroupConfig, PluginInstance
from amiyabot.adapters.mirai import MiraiForwardMessage
from amiyabot.adapters.cqhttp import CQHttpBotInstance, CQHTTPForwardMessage
from amiyabot.adapters.tencent import TencentBotInstance

from core import Chain
from core.resource.arknightsGameData import ArknightsGameData, ArknightsGameDataResource

from .operatorSearch import *
from .operatorInfo import OperatorInfo, curr_dir
from .operatorData import OperatorData


class OperatorPluginInstance(PluginInstance):
    def install(self):
        asyncio.create_task(OperatorInfo.init_operator())
        asyncio.create_task(OperatorInfo.init_skins_keywords())
        asyncio.create_task(OperatorInfo.init_stories_keywords())


bot = OperatorPluginInstance(
    name='明日方舟干员资料',
    version='2.4',
    plugin_id='amiyabot-arknights-operator',
    plugin_type='official',
    description='查询明日方舟干员资料',
    document=f'{curr_dir}/README.md'
)
bot.set_group_config(GroupConfig('operator', allow_direct=True))


@bot.on_message(group_id='operator', keywords=['模组'], level=default_level)
async def _(data: Message):
    info = search_info(data, source_keys=['name'])

    if not info.name:
        wait = await data.wait(Chain(data).text('博士，请说明需要查询的干员名'))
        if not wait or not wait.text:
            return None
        info.name = wait.text

    if info.name not in ArknightsGameData.operators:
        return Chain(data).text(f'博士，没有找到干员"{info.name}"')

    is_story = '故事' in data.text
    result = OperatorData.find_operator_module(info, is_story)

    if not result:
        return Chain(data).text(f'博士，干员{info.name}尚未拥有模组')
    if is_story:
        return Chain(data).text_image(result)
    else:
        return Chain(data).html(f'{curr_dir}/template/operatorModule.html', result)


@bot.on_message(group_id='operator', keywords=['语音'], level=default_level)
async def _(data: Message):
    info = search_info(data, source_keys=['voice_key', 'name'])

    voice_type = ''
    voice_name = '日语'
    if '中文' in data.text:
        voice_type = '_cn'
        voice_name = '中文'
    if '英' in data.text:
        voice_type = '_en'
        voice_name = '英语'
    if '韩' in data.text:
        voice_type = '_kr'
        voice_name = '韩语'
    if '方言' in data.text:
        voice_type = '_custom'
        voice_name = '方言'
    if '意大利' in data.text:
        voice_type = '_ita'
        voice_name = '意大利语'

    if not info.name:
        wait = await data.wait(Chain(data).text('博士，请说明需要查询的干员名'))
        if not wait or not wait.text:
            return None
        info.name = wait.text

    operators = ArknightsGameData.operators

    if info.name not in operators:
        return Chain(data).text(f'博士，没有找到干员"{info.name}"')

    opt = operators[info.name]
    voices = opt.voices()
    voices_map = {item['voice_title']: item for item in voices}
    index = get_index(data.text_digits, voices)

    if not info.voice_key and index is None:
        text = f'博士，这是干员{opt.name}的语音列表\n\n'
        for i, item in enumerate(voices):
            text += f'[{i + 1}] %s\n' % item['voice_title']
        text += '\n回复【序号】查询对应的语音资料'

        wait = await data.wait(Chain(data).text(text))
        if wait:
            index = get_index(wait.text_digits, voices)

    if index is not None:
        info.voice_key = info.voice_key or voices[index]['voice_title']

    if not info.voice_key:
        return None

    if info.voice_key in voices_map:
        text = f'博士，为您找到干员{info.name}的语音档案：\n\n【{info.voice_key}】\n\n' \
               + voices_map[info.voice_key]['voice_text']
        text = text.replace('{@nickname}', data.nickname)

        reply = Chain(data).text(text)

        file = await ArknightsGameDataResource.get_voice_file(opt, info.voice_key, voice_type)
        if file:
            reply.voice(file)
        else:
            reply.text(f'\n\n{opt.wiki_name}《{info.voice_key}》{voice_name}语音文件下载失败...>.<')

        return reply
    else:
        return Chain(data).text(f'博士，没有找到干员{info.name}《{info.voice_key}》的语音档案')


@bot.on_message(group_id='operator', keywords=['档案', '资料'], level=default_level)
async def _(data: Message):
    info = search_info(data, source_keys=['story_key', 'name'])

    if not info.name:
        wait = await data.wait(Chain(data).text('博士，请说明需要查询的干员名'))
        if not wait or not wait.text:
            return None
        info.name = wait.text

    operators = ArknightsGameData.operators

    if info.name not in operators:
        return Chain(data).text(f'博士，没有找到干员"{info.name}"')

    opt = operators[info.name]
    stories = opt.stories()
    stories_map = {item['story_title']: item['story_text'] for item in stories}
    index = get_index(data.text_digits, stories)

    if not info.story_key and index is None:
        text = f'博士，这是干员{opt.name}的档案列表\n\n'
        for i, item in enumerate(stories):
            text += f'[{i + 1}] %s\n' % item['story_title']
        text += '\n回复【序号】查询对应的档案资料'

        wait = await data.wait(Chain(data).text(text))
        if wait:
            index = get_index(wait.text_digits, stories)

    if index is not None:
        info.story_key = info.story_key or stories[index]['story_title']

    if not info.story_key:
        return None

    if info.story_key in stories_map:
        return Chain(data).text(f'博士，这是干员{info.name}《{info.story_key}》的档案\n\n{stories_map[info.story_key]}')
    else:
        return Chain(data).text(f'博士，没有找到干员{info.name}《{info.story_key}》的档案')


@bot.on_message(group_id='operator', keywords=['皮肤', '服装', '衣服', '时装', '立绘'], level=default_level)
async def _(data: Message):
    info = search_info(data, source_keys=['skin_key', 'name'])

    skin_item = None
    if info.skin_key:
        skin_item = OperatorInfo.skins_map[info.skin_key]
    else:
        if not info.name:
            wait = await data.wait(Chain(data).text('博士，请说明需要查询的干员名'))
            if not wait or not wait.text:
                return None
            info.name = wait.text

        operators = ArknightsGameData.operators

        if info.name not in operators:
            return Chain(data).text(f'博士，没有找到干员"{info.name}"')

        opt = operators[info.name]
        skins = opt.skins()

        index = get_index(data.text_digits, skins)

        if index is None:
            text = f'博士，这是干员{info.name}的立绘列表\n\n'
            for i, item in enumerate(skins):
                text += f'[{i + 1}] %s\n' % item['skin_name']
            text += '\n回复【序号】查询对应的立绘资料'

            wait = await data.wait(Chain(data).text(text))
            if wait:
                index = get_index(wait.text_digits, skins)

        if index is not None:
            skin_item = skins[index]

    if skin_item:
        skin_data = {
            'name': info.name,
            'data': skin_item,
            'path': await ArknightsGameDataResource.get_skin_file(skin_item, encode_url=True)
        }

        reply = Chain(data).html(f'{curr_dir}/template/operatorSkin.html', skin_data)

        if type(data.instance) is not TencentBotInstance:
            reply.image(skin_data['path'].replace('%23', '#'))

        return reply


@bot.on_message(group_id='operator', verify=FuncsVerify.level_up)
async def _(data: Message):
    info: OperatorSearchInfo = data.verify.keypoint

    if not info.name:
        wait = await data.wait(Chain(data).text('博士，请说明需要查询的干员名'))
        if not wait or not wait.text:
            return None
        info.name = wait.text

    if '材料' in data.text:
        result = await OperatorData.get_level_up_cost(info)
        template = f'{curr_dir}/template/operatorCost.html'
    else:
        result = await OperatorData.get_skills_detail(info)
        template = f'{curr_dir}/template/skillsDetail.html'

    if not result:
        return Chain(data).text('博士，请仔细描述想要查询的信息哦')

    return Chain(data).html(template, result)


@bot.on_message(group_id='operator', verify=FuncsVerify.operator)
async def _(data: Message):
    info: OperatorSearchInfo = data.verify.keypoint

    reply = Chain(data)

    if '技能' in data.text:
        result = await OperatorData.get_skills_detail(info)
        if result:
            return reply.html(f'{curr_dir}/template/skillsDetail.html', result)
    else:
        result, tokens = await OperatorData.get_operator_detail(info)
        if result:
            if '召唤物' not in data.text:
                reply = reply.html(f'{curr_dir}/template/operatorInfo.html', result, width=1600)
            elif not tokens['tokens']:
                return Chain(data).text('博士，干员%s未拥有召唤物' % result['info']['name'])
            if tokens['tokens']:
                reply = reply.html(f'{curr_dir}/template/operatorToken.html', tokens)
            return reply

    return Chain(data).text('博士，请仔细描述想要查询的信息哦')


@bot.on_message(group_id='operator', verify=FuncsVerify.group)
async def _(data: Message):
    info: OperatorSearchInfo = data.verify.keypoint

    if not info.group_key:
        return

    source = type(data.instance)
    operator_group = OperatorInfo.operator_group_map[info.group_key]

    if source is TencentBotInstance:
        reply = Chain(data).text(f'查询到【{info.group_key}】拥有以下干员\n')

        for item in operator_group:
            reply.text(item.name + '\n')

        return reply
    elif source is CQHttpBotInstance:
        reply = CQHTTPForwardMessage(data)
    else:
        reply = MiraiForwardMessage(data)

    await data.send(Chain(data).text('正在查询，博士请稍等...'))
    await reply.add_message(Chain().text(f'查询到【{info.group_key}】拥有以下干员'),
                            user_id=data.instance.appid,
                            nickname='AmiyaBot')

    for item in operator_group:
        result, tokens = await OperatorData.get_operator_detail(OperatorSearchInfo(name=item.name))
        if result:
            node = Chain().html(f'{curr_dir}/template/operatorInfo.html', result, width=1600)
            if tokens['tokens']:
                node.html(f'{curr_dir}/template/operatorToken.html', tokens)

            await reply.add_message(node, user_id=data.instance.appid, nickname='AmiyaBot')

    await reply.send()
