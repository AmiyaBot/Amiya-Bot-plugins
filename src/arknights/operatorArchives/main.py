import copy
import asyncio

from amiyabot import GroupConfig, PluginInstance
from amiyabot.adapters.mirai import MiraiBotInstance, MiraiForwardMessage
from amiyabot.adapters.cqhttp import CQHttpBotInstance, CQHTTPForwardMessage
from amiyabot.adapters.tencent import TencentBotInstance

from core import Message, Chain
from core.util import find_similar_list, any_match, get_index_from_text
from core.resource.arknightsGameData import ArknightsGameData, ArknightsGameDataResource

from .operatorInfo import OperatorInfo, curr_dir
from .operatorData import OperatorData
from .initData import OperatorSearchInfo, InitData


class OperatorPluginInstance(PluginInstance):
    def install(self):
        asyncio.create_task(OperatorInfo.init_operator())
        asyncio.create_task(OperatorInfo.init_skins_table())
        asyncio.create_task(OperatorInfo.init_stories_titles())


default_level = 3

bot = OperatorPluginInstance(
    name='明日方舟干员资料',
    version='2.3',
    plugin_id='amiyabot-arknights-operator',
    plugin_type='official',
    description='查询明日方舟干员资料',
    document=f'{curr_dir}/README.md'
)
bot.set_group_config(GroupConfig('operator', allow_direct=True))


class LoopBreak(Exception):
    def __init__(self, index, name='', value=''):
        self.index = index
        self.value = value
        self.name = name

    def __str__(self):
        return self.index, self.name


def search_info(words: list, source_keys: list = None, text: str = ''):
    info_source = {
        'name': [OperatorInfo.operator_map],
        'level': [InitData.skill_level_list],
        'skill': [OperatorInfo.skill_map],
        'skill_index': [InitData.skill_index_list],
        'skin_key': [OperatorInfo.skins_keywords],
        'voice_key': [InitData.voices],
        'story_key': [OperatorInfo.stories_title],
        'group_key': [OperatorInfo.operator_group_map.keys()],
    }

    info = OperatorSearchInfo()
    info_key = list(info_source.keys()) if not source_keys else source_keys

    words = [n.lower() for n in copy.deepcopy(words)]

    if 'name' in info_key and text:
        for name in OperatorInfo.operator_one_char_list:
            if name in text:
                info.name = name
        for index, item in enumerate(words):
            for source in info_source['name']:
                if item in source:
                    value = source[item] if type(source) is dict else item
                    setattr(info, 'name', value)

    # 如果找到了Name，则直接获取干员
    operators = ArknightsGameData().operators

    if info.name not in operators:
        info.name = ''
    else:
        opt = operators[info.name]
        info.skin_key = ''

        for index, item in enumerate(words):
            # 精确皮肤识别
            if 'skin_key' in source_keys:
                skins = map(lambda s: s['skin_name'], opt.skins())
                for skin_name in skins:
                    if item == skin_name:
                        info.skin_key = skin_name

    while True:
        try:
            if len(words) == 0:
                break
            for index, item in enumerate(words):
                for name in copy.deepcopy(info_key):
                    for source in info_source[name]:

                        if name == 'skill':
                            res, rate = find_similar_list(item, source.keys(), _random=True)
                            if res:
                                setattr(info, name, source[res])
                                raise LoopBreak(index, name, source[res])
                        elif name == 'name':
                            continue
                        elif name == 'skin_key':
                            continue
                        elif item in source:
                            value = source[item] if type(source) is dict else item
                            setattr(info, name, value)
                            raise LoopBreak(index, name, value)

                if index == len(words) - 1:
                    raise LoopBreak('done')
        except LoopBreak as e:
            if e.index == 'done':
                break

            words.pop(e.index)

            if e.name == 'name' and e.value == '阿米娅':
                continue
            else:
                info_key.remove(e.name)

    if info.name == '阿米娅':
        for item in ['阿米娅', 'amiya']:
            t = text.lower()
            if t.startswith(item) and t.count(item) == 1:
                info.name = ''

    if info.name and info.skill and OperatorInfo.skill_operator[info.skill] != info.name:
        info.skill = ''

    return info


async def level_up(data: Message):
    info = search_info(data.text_words, source_keys=['name', 'level', 'skill_index'], text=data.text)

    condition = any_match(data.text, ['精英', '专精'])
    condition2 = info.name and '材料' in data.text

    return bool(condition or condition2), (3 if condition2 else 2)


async def operator(data: Message):
    info = search_info(data.text_words, source_keys=['name'], text=data.text)
    return bool(info.name), default_level if info.name != '阿米娅' else 0


async def group(data: Message):
    info = search_info(data.text_words, source_keys=['group_key'], text=data.text)
    return bool(info.group_key), default_level


@bot.on_message(group_id='operator', keywords=['皮肤', '立绘'], level=default_level)
async def _(data: Message):
    info = search_info(data.text_words, source_keys=['skin_key', 'name'], text=data.text)

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
    skin_item = None

    if info.skin_key and info.skin_key != '':
        for skin in skins:
            if skin['skin_name'] == info.skin_key:
                skin_item = skin
                break

    if not skin_item:
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


@bot.on_message(group_id='operator', keywords=['模组'], level=default_level)
async def _(data: Message):
    info = search_info(data.text_words, source_keys=['name'], text=data.text)

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
    info = search_info(data.text_words, source_keys=['voice_key', 'name'], text=data.text)

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
    info = search_info(data.text_words, source_keys=['story_key', 'name'], text=data.text)

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


@bot.on_message(group_id='operator', verify=level_up)
async def _(data: Message):
    info = search_info(data.text_words, source_keys=['level', 'skill_index', 'name'], text=data.text)

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


@bot.on_message(group_id='operator', verify=operator)
async def _(data: Message):
    info = search_info(data.text_words, source_keys=['name'], text=data.text)

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


@bot.on_message(group_id='operator', verify=group)
async def _(data: Message):
    info = search_info(data.text_words, source_keys=['group_key'], text=data.text)

    if not info.group_key:
        return

    source = type(data.instance)
    operator_group = OperatorInfo.operator_group_map[info.group_key]

    if source is TencentBotInstance:
        reply = Chain(data).text(f'查询到【{info.group_key}】拥有以下干员\n')

        for item in operator_group:
            reply.image(f'resource/gamedata/avatar/{item.id}.png').text(item.name + '\n')

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


def get_index(text: str, array: list):
    filter_text = [
        'lancet2',
        'castle3',
        '4月'
    ]
    for item in filter_text:
        text = text.lower().replace(item, '')

    return get_index_from_text(text, array)
