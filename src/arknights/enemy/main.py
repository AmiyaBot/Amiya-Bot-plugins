import os
import re

from core import Message, Chain, AmiyaBotPluginInstance, Requirement
from core.util import integer, any_match, find_most_similar, get_index_from_text, remove_punctuation
from core.resource.arknightsGameData import ArknightsGameData

curr_dir = os.path.dirname(__file__)

line_height = 16
side_padding = 10


class Enemy:
    @classmethod
    def find_enemies(cls, name: str):
        result = []
        name = name.lower()
        for e_name, item in ArknightsGameData.enemies.items():
            if name == e_name.lower() or (len(name) > 1 and name in e_name.lower()):
                result.append([e_name, item])

        return result

    @classmethod
    def get_enemy(cls, name: str, get_links: bool = True):
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

        enemy = ArknightsGameData.enemies.get(name)
        attrs = {}
        link_items = []

        if not enemy:
            return None

        if enemy['data']:
            for item in enemy['data']:
                attrs[item['level']] = {}

                detail_data = item['enemyData']
                for key in key_map:
                    defined, value = cls.get_value(key, detail_data)
                    if defined:
                        key_map[key]['value'] = value
                    else:
                        value = key_map[key]['value']

                    attrs[item['level']][key_map[key]['title']] = value

        if get_links:
            for link_id in enemy['info']['linkEnemies']:
                res = cls.get_enemy(link_id, get_links=False)
                if res:
                    link_items.append(res)

        return {**enemy, 'attrs': attrs, 'link_items': link_items}

    @classmethod
    def get_value(cls, key, source):
        for item in key.split('.'):
            if item in source:
                source = source[item]
        return source['m_defined'], integer(source['m_value'])


class EnemiesPluginInstance(AmiyaBotPluginInstance):
    ...


bot = EnemiesPluginInstance(
    name='明日方舟敌方单位查询',
    version='3.0',
    plugin_id='amiyabot-arknights-enemy',
    plugin_type='official',
    description='查询明日方舟敌方单位资料',
    document=f'{curr_dir}/README.md',
    requirements=[Requirement('amiyabot-arknights-gamedata', official=True)],
)


async def verify(data: Message):
    name = find_most_similar(
        data.text.replace('敌人', '').replace('敌方', '').replace('单位', '').strip(), list(ArknightsGameData.enemies.keys())
    )
    keyword = any_match(data.text, ['敌人', '敌方'])
    level = (5 + int(bool(name))) if keyword else 1

    if name == '-':
        name = ''

    if not keyword and name and remove_punctuation(name) not in remove_punctuation(data.text):
        return False

    if name in ['w', '“阿米娅”'] and not keyword:
        return False

    if name or keyword:
        return True, level, name

    return False


@bot.on_message(group_id='operator', keywords='/敌方单位', level=5)
async def _(data: Message):
    return Chain(data).text('博士，请在指令后面输入需要查询的敌方单位名称')


@bot.on_message(verify=verify, allow_direct=True)
async def enemy_query(data: Message):
    enemy_name = ''
    for reg in ['敌人(资料)?(.*)', '敌方(资料)?(.*)']:
        r = re.search(re.compile(reg), data.text)
        if r:
            enemy_name = r.group(2).replace('单位', '').strip()

    if not enemy_name:
        if data.verify.keypoint:
            res = Enemy.get_enemy(data.verify.keypoint)
            if res:
                return Chain(data).html(f'{curr_dir}/template/enemy.html', res)

        wait = await data.wait(Chain(data).text('博士，请说明需要查询的敌方单位名称'))
        if not wait or not wait.text:
            return None

        enemy_name = find_most_similar(wait.text, list(ArknightsGameData.enemies.keys()))

    if enemy_name:
        result = Enemy.find_enemies(enemy_name)
        if result:
            if len(result) == 1:
                res = Enemy.get_enemy(result[0][0])
                if res:
                    return Chain(data).html(f'{curr_dir}/template/enemy.html', res)

            init_data = {'search': enemy_name, 'result': {item[0]: item[1] for item in result}}

            wait = await data.wait(
                Chain(data).html(f'{curr_dir}/template/enemyIndex.html', init_data).text('回复【序号】查询对应的敌方单位资料')
            )

            if wait:
                index = get_index_from_text(wait.text_digits, result)
                if index is not None:
                    res = Enemy.get_enemy(result[index][0])
                    if res:
                        return Chain(data).html(f'{curr_dir}/template/enemy.html', res)
        else:
            return Chain(data).text(f'博士，没有找到敌方单位{enemy_name}的资料 >.<')
