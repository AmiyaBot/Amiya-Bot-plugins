from dataclasses import dataclass

from core import Message
from core.util import any_match, find_most_similar, get_index_from_text, remove_punctuation

from .operatorInfo import OperatorInfo

default_level = 3


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

        return bool(condition or condition2), (3 if condition2 else 2), info

    @classmethod
    async def operator(cls, data: Message):
        info = search_info(data, source_keys=['name'])

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
        'story_key': OperatorInfo.stories_keywords
    }

    info = OperatorSearchInfo()

    for key_name in source_keys:
        res = find_most_similar(data.text, info_source[key_name])
        if res and remove_punctuation(res) in data.text:
            setattr(info, key_name, res)

            if key_name == 'name':
                if info.name in OperatorInfo.operator_en_name_map:
                    info.name = OperatorInfo.operator_en_name_map[info.name]

                if info.name == '阿米娅':
                    for item in ['阿米娅', 'amiya']:
                        t = data.text.lower()
                        if t.startswith(item) and t.count(item) == 1:
                            info.name = any_match(data.text.replace(item, ''), info_source[key_name])

    return info


def get_index(text: str, array: list):
    for item in OperatorInfo.operator_contain_digit_list:
        text = text.lower().replace(item, '')

    return get_index_from_text(text, array)
