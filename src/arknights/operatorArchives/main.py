from typing import Optional
from amiyabot import ChainBuilder
from amiyabot.adapters.kook import KOOKBotInstance
from amiyabot.adapters.mirai import MiraiForwardMessage
from amiyabot.adapters.cqhttp import CQHttpBotInstance, CQHTTPForwardMessage
from amiyabot.adapters.tencent.qqGuild import QQGuildBotInstance
from amiyabot.adapters.tencent.qqGroup import QQGroupBotInstance
from amiyabot.adapters.tencent.qqGlobal import QQGlobalBotInstance

from core import Chain, Message
from core.resource.arknightsGameData import ArknightsGameData, ArknightsGameDataResource

from .operatorCore import bot, default_level, get_index, search_info, FuncsVerify, OperatorSearchInfo
from .operatorInfo import OperatorInfo, curr_dir
from .operatorData import OperatorData


class WaitALLRequestsDone(ChainBuilder):
    @classmethod
    async def on_page_rendered(cls, page):
        await page.wait_for_load_state('networkidle')


@bot.on_message(group_id='operator', keywords=['模组'], level=default_level)
async def operator_archives_module_func(data: Message):
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
        return Chain(data).markdown(result)
    else:
        return Chain(data, chain_builder=WaitALLRequestsDone()).html(f'{curr_dir}/template/operatorModule.html', result)


@bot.on_message(group_id='operator', keywords=['语音'], level=default_level)
async def operator_archives_voice_func(data: Message):
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
    if '俄' in data.text:
        voice_type = '_custom'
        voice_name = '俄语'
    if '德' in data.text:
        voice_type = '_custom'
        voice_name = '德语'
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
        text = f'博士，这是干员{opt.name}的语音列表\n回复【<span style="color: red">序号</span>】查询对应的语音资料\n\n'
        text += '|标题|标题|标题|\n|----|----|----|\n'

        for i, item in enumerate(voices):
            text += (
                f'|<span style="color: red; padding-right: 5px; font-weight: bold;">{i + 1}</span>'
                + item['voice_title']
            )
            if (i + 1) % 3 == 0:
                text += '|\n'

        wait = await data.wait(Chain(data).markdown(text))
        if wait:
            index = get_index(wait.text_digits, voices)

    if index is not None:
        info.voice_key = info.voice_key or voices[index]['voice_title']

    if not info.voice_key:
        return None

    if info.voice_key in voices_map:
        text = (
            f'博士，为您找到干员{info.name}的语音档案：\n\n【{info.voice_key}】\n\n'
            + voices_map[info.voice_key]['voice_text']
        )
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
async def operator_archives_story_func(data: Message):
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
        text = f'博士，这是干员{opt.name}的档案列表\n回复【<span style="color: red">序号</span>】查询对应的档案资料\n\n'
        text += '|标题|标题|标题|\n|----|----|----|\n'

        for i, item in enumerate(stories):
            text += (
                f'|<span style="color: red; padding-right: 5px; font-weight: bold;">{i + 1}</span>'
                + item['story_title']
            )
            if (i + 1) % 3 == 0:
                text += '|\n'

        wait = await data.wait(Chain(data).markdown(text))
        if wait:
            index = get_index(wait.text_digits, stories)

    if index is not None:
        info.story_key = info.story_key or stories[index]['story_title']

    if not info.story_key:
        return None

    if info.story_key in stories_map:
        return (
            Chain(data)
            .text(f'博士，这是干员{info.name}《{info.story_key}》的档案')
            .markdown(stories_map[info.story_key].replace('\n', '<br>'))
        )
    else:
        return Chain(data).text(f'博士，没有找到干员{info.name}《{info.story_key}》的档案')


@bot.on_message(group_id='operator', keywords=['皮肤', '立绘'], level=default_level)
async def operator_archives_skin_func(data: Message):
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
            'path': await ArknightsGameDataResource.get_skin_file(skin_item, encode_url=True),
        }

        reply = Chain(data).html(f'{curr_dir}/template/operatorSkin.html', skin_data)

        if bot.get_config('operatorSkin')['showImage']:
            reply.image(skin_data['path'].replace('%23', '#'))

        return reply


@bot.on_message(group_id='operator', verify=FuncsVerify.level_up)
async def operator_archives_skill_and_material_func(data: Message):
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
async def operator_func(data: Message, info: Optional[OperatorSearchInfo] = None):
    info = info or data.verify.keypoint

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
                if '召唤物' in data.text or bot.get_config('operatorInfo')['showToken']:
                    reply = reply.html(f'{curr_dir}/template/operatorToken.html', tokens)

            return reply

    return Chain(data).text('博士，请仔细描述想要查询的信息哦')


@bot.on_message(group_id='operator', verify=FuncsVerify.group)
async def operator_archives_group_query_1(data: Message):
    info: OperatorSearchInfo = data.verify.keypoint

    if not info.group_key:
        return

    source = type(data.instance)
    operator_group = OperatorInfo.operator_group_map[info.group_key]

    if source in [QQGuildBotInstance, QQGroupBotInstance, QQGlobalBotInstance, KOOKBotInstance]:
        text = f'## {info.group_key}\n'
        for item in operator_group:
            text += f'- {item.name}\n'

        return Chain(data).markdown(text)

    elif source is CQHttpBotInstance:
        reply = CQHTTPForwardMessage(data)

    else:
        reply = MiraiForwardMessage(data)

    await data.send(Chain(data).text('正在查询，博士请稍等...'))
    await reply.add_message(
        Chain().text(f'查询到【{info.group_key}】拥有以下干员'), user_id=data.instance.appid, nickname='AmiyaBot'
    )

    for item in operator_group:
        result, tokens = await OperatorData.get_operator_detail(OperatorSearchInfo(name=item.name))
        if result:
            node = Chain().html(f'{curr_dir}/template/operatorInfo.html', result, width=1600)
            if tokens['tokens']:
                node.html(f'{curr_dir}/template/operatorToken.html', tokens)

            await reply.add_message(node, user_id=data.instance.appid, nickname='AmiyaBot')

    await reply.send()


@bot.on_message(group_id='operator', keywords='阵营', level=default_level)
async def operator_archives_group_query_2(data: Message):
    operator_group = OperatorInfo.operator_group_map

    text = '|阵营名|干员|\n|----|----|\n'

    for item in sorted(operator_group.keys()):
        group = operator_group[item]
        text += f'|{item}|%s|\n' % ('、'.join([n.name for n in group]))

    return Chain(data).markdown(text)


@bot.on_message(group_id='operator', keywords='/干员查询', level=10)
async def operator_archives_operator_query(data: Message):
    res = await FuncsVerify.operator(data, False)
    if res[0]:
        return await operator_func(data, res[2])

    wait = await data.wait(Chain(data).text('博士，请输入需要查询的干员名称'), force=True)
    if wait:
        res = await FuncsVerify.operator(wait, False)
        if res[0]:
            return await operator_func(wait, res[2])
