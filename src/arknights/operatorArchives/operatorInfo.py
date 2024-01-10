import os
import re
import jieba

from typing import Dict, List
from core import log
from core.util import chinese_to_digits, is_contain_digit, create_dir
from core.resource.arknightsGameData import ArknightsGameData, Operator

curr_dir = os.path.dirname(__file__)


class OperatorInfo:
    skins_map = {}
    stories_keywords = []

    operator_list = []
    operator_one_char_list = []
    operator_contain_digit_list = []
    operator_en_name_map = {}
    operator_group_map: Dict[str, List[Operator]] = {}

    voice_keywords = [
        '任命助理',
        '任命队长',
        '编入队伍',
        '问候',
        '闲置',
        '交谈1',
        '交谈2',
        '交谈3',
        '晋升后交谈1',
        '晋升后交谈2',
        '信赖提升后交谈1',
        '信赖提升后交谈2',
        '信赖提升后交谈3',
        '精英化晋升1',
        '精英化晋升2',
        '行动出发',
        '行动失败',
        '行动开始',
        '3星结束行动',
        '4星结束行动',
        '非3星结束行动',
        '选中干员1',
        '选中干员2',
        '部署1',
        '部署2',
        '作战中1',
        '作战中2',
        '作战中3',
        '作战中4',
        '戳一下',
        '信赖触摸',
        '干员报到',
        '进驻设施',
        '观看作战记录',
        '标题',
    ]

    @classmethod
    def reset(cls):
        cls.operator_list = []
        cls.operator_one_char_list = []
        cls.operator_contain_digit_list = []
        cls.operator_en_name_map = {}
        cls.operator_group_map = {}

    @classmethod
    def set_jieba_dict(cls):
        dict_file = 'resource/plugins/operators.txt'

        create_dir(dict_file, is_file=True)

        with open(dict_file, mode='w', encoding='utf-8') as file:
            words = []
            for name in cls.operator_list:
                words.append(f'{name} 1 n')
                if len(name) == 1:
                    jieba.del_word(f'兔兔{name}')

            file.write('\n'.join(words))

        jieba.load_userdict(dict_file)

    @classmethod
    async def init_operator(cls):
        log.info('building operator keywords...')

        cls.reset()

        for name, item in ArknightsGameData.operators.items():
            cls.operator_list.append(name)
            cls.operator_en_name_map[item.en_name] = name

            for n in [name, item.en_name]:
                n = chinese_to_digits(n)
                if is_contain_digit(n):
                    cls.operator_contain_digit_list.append(n)

            for group in [item.team, item.group]:
                if group and group != '未知':
                    if group not in cls.operator_group_map:
                        cls.operator_group_map[group] = []
                    cls.operator_group_map[group].append(item)

            if len(name) == 1:
                cls.operator_one_char_list.append(name)

        cls.set_jieba_dict()

    @classmethod
    async def init_stories_keywords(cls):
        log.info('building operator stories keywords...')
        stories_title = {}
        stories_keyword = []

        for name, item in ArknightsGameData.operators.items():
            stories = item.stories()
            stories_title.update({chinese_to_digits(item['story_title']): item['story_title'] for item in stories})

        for index, item in stories_title.items():
            item = re.compile(r'？+', re.S).sub('', item)
            if item:
                stories_keyword.append(item + ' 500 n')

        cls.stories_keywords = list(stories_title.keys()) + [i for k, i in stories_title.items()]

    @classmethod
    async def init_skins_keywords(cls):
        log.info('building operator skins keywords...')
        skins_map = {}

        for name, item in ArknightsGameData.operators.items():
            for n in item.skins():
                if n['skin_name'] in ['初始', '精英一', '精英二']:
                    continue
                skins_map[n['skin_name']] = n

        cls.skins_map = skins_map
