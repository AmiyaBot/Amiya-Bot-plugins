import os
import re
import jieba
import asyncio

from amiyabot import PluginInstance
from core import log, Message, Chain
from core.util import integer, any_match, get_index_from_text
from core.resource.arknightsGameData import ArknightsGameData

curr_dir = os.path.dirname(__file__)

line_height = 16
side_padding = 10


def get_value(key, source):
    for item in key.split('.'):
        if item in source:
            source = source[item]
    return source['m_defined'], integer(source['m_value'])


class Enemy:
    @staticmethod
    async def init_enemies():
        log.info('building enemies names keywords dict...')

        enemies = list(ArknightsGameData.enemies.keys())

        with open(f'{curr_dir}/enemies.txt', mode='w', encoding='utf-8') as file:
            file.write('\n'.join([f'{name} 500 n' for name in enemies]))

        jieba.load_userdict(f'{curr_dir}/enemies.txt')

    @classmethod
    def find_enemies(cls, name: str):
        result = []
        for e_name, item in ArknightsGameData.enemies.items():
            if name.lower() == e_name:
                return [[e_name, item]]
            if name.lower() in e_name:
                result.append([e_name, item])

        return result

    @classmethod
    def get_enemy(cls, name: str):
        enemies = ArknightsGameData.enemies

        key_map = {
            'attributes.maxHp': {'title': 'maxHp', 'value': ''},
            'attributes.atk': {'title': 'atk', 'value': ''},
            'attributes.def': {'title': 'def', 'value': ''},
            'attributes.magicResistance': {'title': 'magicResistance', 'value': ''},
            'attributes.moveSpeed': {'title': 'moveSpeed', 'value': ''},
            'attributes.baseAttackTime': {'title': 'baseAttackTime', 'value': ''},
            'attributes.hpRecoveryPerSec': {'title': 'hpRecoveryPerSec', 'value': ''},
            'attributes.massLevel': {'title': 'massLevel', 'value': ''},
            'attributes.stunImmune': {'title': 'stunImmune', 'value': ''},
            'attributes.silenceImmune': {'title': 'silenceImmune', 'value': ''},
            'attributes.sleepImmune': {'title': 'sleepImmune', 'value': ''},
            'attributes.frozenImmune': {'title': 'frozenImmune', 'value': ''},
            'attributes.levitateImmune': {'title': 'levitateImmune', 'value': ''},
            'rangeRadius': {'title': 'rangeRadius', 'value': ''},
            'lifePointReduce': {'title': 'lifePointReduce', 'value': ''},
        }

        attrs = {}

        for item in enemies[name]['data']:
            attrs[item['level'] + 1] = {}

            detail_data = item['enemyData']
            for key in key_map:
                defined, value = get_value(key, detail_data)
                if defined:
                    key_map[key]['value'] = value
                else:
                    value = key_map[key]['value']

                attrs[item['level'] + 1][key_map[key]['title']] = value

        return {
            **enemies[name],
            'attrs': attrs
        }


class EnemyPluginInstance(PluginInstance):
    def install(self):
        asyncio.create_task(Enemy.init_enemies())


bot = EnemyPluginInstance(
    name='??????????????????????????????',
    version='1.5',
    plugin_id='amiyabot-arknights-enemy',
    plugin_type='official',
    description='????????????????????????????????????',
    document=f'{curr_dir}/README.md'
)


async def verify(data: Message):
    name = any_match(data.text_origin, list(ArknightsGameData.enemies.keys()))
    keyword = any_match(data.text, ['??????', '??????'])

    if name in ['w'] and not keyword:
        return False

    if name or keyword:
        return True, (5 if keyword else 1)
    return False


@bot.on_message(verify=verify, allow_direct=True)
async def _(data: Message):
    message = data.text_origin
    words = data.text_words

    for item in words:
        if item in ArknightsGameData.enemies:
            return Chain(data).html(f'{curr_dir}/template/enemy.html', Enemy.get_enemy(item))

    enemy_name = ''
    for reg in ['??????(??????)?(.*)', '??????(??????)?(.*)']:
        r = re.search(re.compile(reg), message)
        if r:
            enemy_name = r.group(2).strip()

    if not enemy_name:
        wait = await data.wait(Chain(data).text('???????????????????????????????????????????????????'))
        if not wait or not wait.text:
            return None
        enemy_name = wait.text

    if enemy_name:
        result = Enemy.find_enemies(enemy_name)
        if result:
            if len(result) == 1:
                return Chain(data).html(f'{curr_dir}/template/enemy.html', Enemy.get_enemy(result[0][0]))

            init_data = {
                'search': enemy_name,
                'result': {item[0]: item[1] for item in result}
            }

            wait = await data.wait(
                Chain(data).html(f'{curr_dir}/template/enemyIndex.html', init_data).text(
                    '???????????????????????????????????????????????????')
            )

            if wait:
                index = get_index_from_text(wait.text_digits, result)
                if index is not None:
                    return Chain(data).html(f'{curr_dir}/template/enemy.html', Enemy.get_enemy(result[index][0]))
        else:
            return Chain(data).text('?????????????????????????????????%s???????????? >.<' % enemy_name)
