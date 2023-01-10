import os
import re
import jieba

from typing import Dict, List
from core import log
from core.util import chinese_to_digits, remove_punctuation
from core.resource.arknightsGameData import ArknightsGameData, Operator

from .initData import InitData

curr_dir = os.path.dirname(__file__)


class OperatorInfo:
    skins_table = {}
    skins_keywords = []

    stories_title = []

    skill_map = {}
    skill_operator = {}

    operator_map = {}
    operator_keywords = []
    operator_one_char_list = []

    operator_group_map: Dict[str, List[Operator]] = {}

    @classmethod
    async def init_operator(cls):
        log.info('building operator info and skills keywords dict...')

        keywords = ['%s 500 n' % key for key in InitData.voices]

        def append_word(text):
            cls.operator_keywords.append(text)
            dict_word = '%s 500 n' % text
            if dict_word not in keywords:
                keywords.append(dict_word)

        for key in InitData.skill_index_list:
            append_word(key)

        for key in InitData.skill_level_list:
            append_word(key)

        for name, item in ArknightsGameData.operators.items():
            e_name = remove_punctuation(item.en_name).lower()
            append_word(name)
            append_word(e_name)

            for group in [item.team, item.group]:
                if group and group != '未知':
                    if group not in cls.operator_group_map:
                        cls.operator_group_map[group] = []
                    cls.operator_group_map[group].append(item)

            cls.operator_map[name.lower()] = name
            cls.operator_map[e_name.replace(' ', '')] = name

            if len(name) == 1:
                cls.operator_one_char_list.append(name)

            skills = item.skills()[0]

            for skl in skills:
                skl_name = remove_punctuation(skl['skill_name'])
                append_word(skl_name)

                cls.skill_map[skl_name] = skl['skill_name']
                cls.skill_operator[skl['skill_name']] = name

        with open(f'{curr_dir}/operators.txt', mode='w', encoding='utf-8') as file:
            file.write('\n'.join(keywords + list(cls.operator_group_map.keys())))
        jieba.load_userdict(f'{curr_dir}/operators.txt')

    @classmethod
    async def init_stories_titles(cls):
        log.info('building operator stories keywords dict...')
        stories_title = {}
        stories_keyword = []

        for name, item in ArknightsGameData.operators.items():
            stories = item.stories()
            stories_title.update(
                {chinese_to_digits(item['story_title']): item['story_title'] for item in stories}
            )

        for index, item in stories_title.items():
            item = re.compile(r'？+', re.S).sub('', item)
            if item:
                stories_keyword.append(item + ' 500 n')

        cls.stories_title = list(stories_title.keys()) + [i for k, i in stories_title.items()]

        with open(f'{curr_dir}/stories.txt', mode='w', encoding='utf-8') as file:
            file.write('\n'.join(stories_keyword))
        jieba.load_userdict(f'{curr_dir}/stories.txt')

    @classmethod
    async def init_skins_table(cls):
        log.info('building operator skins keywords dict...')
        skins_table = {}
        skins_keywords = [] + InitData.skins

        for name, item in ArknightsGameData.operators.items():
            skins = item.skins()
            skins_table[item.name] = skins
            skins_keywords += [n['skin_name'] for n in skins]

        cls.skins_table = skins_table
        cls.skins_keywords = skins_keywords

        with open(f'{curr_dir}/skins.txt', mode='w', encoding='utf-8') as file:
            file.write('\n'.join([n + ' 500 n' for n in skins_keywords]))
        jieba.load_userdict(f'{curr_dir}/skins.txt')
