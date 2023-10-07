import asyncio

from dataclasses import dataclass
from amiyabot import GroupConfig, event_bus

from core import Message, AmiyaBotPluginInstance, Requirement
from core.util import any_match, find_most_similar, get_index_from_text, remove_punctuation

from .operatorInfo import OperatorInfo, curr_dir

default_level = 3


class OperatorPluginInstance(AmiyaBotPluginInstance):
    def install(self):
        asyncio.create_task(OperatorInfo.init_operator())
        asyncio.create_task(OperatorInfo.init_skins_keywords())
        asyncio.create_task(OperatorInfo.init_stories_keywords())

    def uninstall(self):
        event_bus.unsubscribe('gameDataInitialized', update)


@event_bus.subscribe('gameDataInitialized')
def update(_):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        bot.install()


bot = OperatorPluginInstance(
    name='明日方舟干员资料',
    version='4.0',
    plugin_id='amiyabot-arknights-operator',
    plugin_type='official',
    description='查询明日方舟干员资料',
    document=f'{curr_dir}/README.md',
    instruction=f'{curr_dir}/README_USE.md',
    global_config_schema=f'{curr_dir}/config_schema.json',
    global_config_default=f'{curr_dir}/config_default.yaml',
    requirements=[Requirement('amiyabot-arknights-gamedata', official=True)],
)
bot.set_group_config(GroupConfig('operator', allow_direct=True))


@dataclass
class OperatorSearchInfo:
    name: str = ''
    skin_key: str = ''
    group_key: str = ''
    voice_key: str = ''
    story_key: str = ''


class FuncsVerify:
    @classmethod
    async def level_up(cls, data: Message):
        info = search_info(data, source_keys=['name'])

        condition = any_match(data.text, ['精英', '专精'])
        condition2 = info.name and '材料' in data.text

        return bool(condition or condition2), (6 if condition2 else 2), info

    @classmethod
    async def operator(cls, data: Message):
        info = search_info(data, source_keys=['name'])

        if len(info.name) == 1 and '查询' not in data.text:
            return False

        return bool(info.name), default_level if info.name != '阿米娅' else 0, info

    @classmethod
    async def group(cls, data: Message):
        info = search_info(data, source_keys=['group_key'])

        return bool(info.group_key), default_level + 1, info


def search_info(data: Message, source_keys: list = None):
    info_source = {
        'name': OperatorInfo.operator_list + list(OperatorInfo.operator_en_name_map.keys()),
        'skin_key': list(OperatorInfo.skins_map.keys()),
        'group_key': list(OperatorInfo.operator_group_map.keys()),
        'voice_key': OperatorInfo.voice_keywords,
        'story_key': OperatorInfo.stories_keywords,
    }

    info = OperatorSearchInfo()
    similar_mode = bot.get_config('searchSetting')['similarMode']
    limit_length = bot.get_config('searchSetting')['lengthLimit']

    if len(data.text_words) > int(limit_length):
        return info

    match_method = find_most_similar if similar_mode else get_longest

    for key_name in source_keys:
        res = match_method(data.text, info_source[key_name])
        if res and remove_punctuation(res) in remove_punctuation(data.text):
            setattr(info, key_name, res)

            if key_name == 'name':
                if info.name in OperatorInfo.operator_en_name_map:
                    info.name = OperatorInfo.operator_en_name_map[info.name]

                if info.name not in data.text_words:
                    continue

                if info.name == '阿米娅':
                    for item in ['阿米娅', 'amiya']:
                        t = data.text.lower()
                        if t.startswith(item) and t.count(item) == 1:
                            info.name = match_method(data.text.replace(item, ''), info_source[key_name])

    return info


def get_longest(text: str, items: list):
    res = ''
    for item in items:
        if item in text and len(item) >= len(res):
            res = item

    return res


def get_index(text: str, array: list):
    for item in OperatorInfo.operator_contain_digit_list:
        text = text.lower().replace(item, '')

    return get_index_from_text(text, array)
