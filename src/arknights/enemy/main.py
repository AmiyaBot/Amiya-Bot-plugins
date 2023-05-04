import os
import re

from amiyabot import PluginInstance
from core import Message, Chain
from core.util import integer, any_match, find_most_similar, get_index_from_text, remove_punctuation
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
    @classmethod
    def find_enemies(cls, name: str):
        result = []
        for e_name, item in ArknightsGameData.enemies.items():
            if name.lower() == e_name or name.lower() in e_name:
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

        if enemies[name]['data']:
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


bot = PluginInstance(
    name='明日方舟敌方单位查询',
    version='2.0',
    plugin_id='amiyabot-arknights-enemy',
    plugin_type='official',
    description='查询明日方舟敌方单位资料',
    document=f'{curr_dir}/README.md'
)


async def verify(data: Message):
    name = find_most_similar(data.text.replace('敌人', '').replace('敌方', ''), list(ArknightsGameData.enemies.keys()))
    keyword = any_match(data.text, ['敌人', '敌方'])

    if name == '-':
        name = ''

    if not keyword and name and remove_punctuation(name) not in remove_punctuation(data.text):
        return False

    # W 触发频率过高
    if name in ['w'] and not keyword:
        return False

    if name or keyword:
        return True, (5 if keyword else 1), name

    return False


@bot.on_message(verify=verify, allow_direct=True)
async def _(data: Message):
    enemy_name = ''
    for reg in ['敌人(资料)?(.*)', '敌方(资料)?(.*)']:
        r = re.search(re.compile(reg), data.text)
        if r:
            enemy_name = r.group(2).strip()

    if not enemy_name:
        if data.verify.keypoint:
            return Chain(data).html(f'{curr_dir}/template/enemy.html', Enemy.get_enemy(data.verify.keypoint))

        wait = await data.wait(Chain(data).text('博士，请说明需要查询的敌方单位名称'))
        if not wait or not wait.text:
            return None

        enemy_name = find_most_similar(wait.text, list(ArknightsGameData.enemies.keys()))

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
                Chain(data)
                .html(f'{curr_dir}/template/enemyIndex.html', init_data)
                .text('回复【序号】查询对应的敌方单位资料')
            )

            if wait:
                index = get_index_from_text(wait.text_digits, result)
                if index is not None:
                    return Chain(data).html(f'{curr_dir}/template/enemy.html', Enemy.get_enemy(result[index][0]))
        else:
            return Chain(data).text(f'博士，没有找到敌方单位{enemy_name}的资料 >.<')
