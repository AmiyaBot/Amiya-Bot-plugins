import os
import re
import json

from typing import List, Dict
from amiyabot import event_bus
from amiyabot.util import extract_zip
from collections import Counter
from core.resource.arknightsGameData import ArknightsGameData, ArknightsGameDataResource, STR_DICT_MAP, STR_DICT_LIST
from core.database.bot import OperatorIndex
from core.util import remove_xml_tag, remove_punctuation, sorted_dict
from core import AmiyaBotPluginInstance, GitAutomation, log

from .common import ArknightsConfig, JsonData, SkinsPathCache, gamedata_path
from .operatorBuilder import OperatorImpl, TokenImpl, Collection, parse_template
from .wiki import PRTS
from .sklandApi import *

curr_dir = os.path.dirname(__file__)
repo = 'https://gitee.com/amiya-bot/amiya-bot-assets.git'


class SkinIndexes:
    url_indexes: Dict[str, str] = {}


class ArknightsGameDataPluginInstance(AmiyaBotPluginInstance):
    def install(self):
        if bot.get_config('autoUpdate') or not os.path.exists(gamedata_path):
            download_gamedata()
        else:
            initialize_data()

    def uninstall(self):
        event_bus.unsubscribe('gameDataFetched', initialize_data)
        ArknightsGameData.initialize_methods.remove(gamedata_initialize)


bot = ArknightsGameDataPluginInstance(
    name='明日方舟数据解析',
    version='3.9',
    plugin_id='amiyabot-arknights-gamedata',
    plugin_type='official',
    description='明日方舟游戏数据解析，为内置的静态类提供数据。',
    document=f'{curr_dir}/../README.md',
    global_config_schema=f'{curr_dir}/../config_schema.json',
    global_config_default=f'{curr_dir}/../config_default.yaml',
    priority=999,
)


def initialize_data():
    with log.sync_catch():
        ArknightsConfig.initialize()
        ArknightsGameData.initialize()
        event_bus.publish('gameDataInitialized')


def download_gamedata():
    if os.path.exists(gamedata_path) and not os.path.exists(f'{gamedata_path}/version.txt'):
        log.warning(f'资源已不可用，请删除 {gamedata_path} 目录并发送“更新资源”或重启。')
        return

    GitAutomation(gamedata_path, repo).update(['--depth 1'])

    event_bus.publish('gameDataFetched')


def gamedata_initialize(cls: ArknightsGameData):
    with log.sync_catch():
        if not os.path.exists('resource/gamedata/version.txt'):
            return None

        extract_zip(f'{gamedata_path}/gamedata.zip', f'{gamedata_path}/gamedata', overwrite=True)

        with open('resource/gamedata/version.txt', mode='r', encoding='utf-8') as file:
            cls.version = file.read().strip('\n') or 'none'

        log.info(f'Initializing ArknightsGameData@{cls.version}...')

        with open('resource/gamedata/indexes/skinUrls.json', mode='r', encoding='utf-8') as file:
            skin_urls = json.load(file)

        for item in skin_urls.values():
            for skin_id, url in item.items():
                SkinIndexes.url_indexes[skin_id] = url

        cls.enemies = init_enemies()
        cls.stages, cls.stages_map, cls.side_story_map = init_stages()
        cls.operators, cls.tokens, cls.birthday = init_operators()
        cls.materials, cls.materials_map, cls.materials_made, cls.materials_source = init_materials()

        OperatorIndex.truncate_table()
        OperatorIndex.batch_insert([item.dict() for _, item in cls.operators.items()])
        JsonData.clear_cache()

        log.info(f'ArknightsGameData initialize completed.')


def init_operators():
    recruit_detail = remove_xml_tag(JsonData.get_json_data('gacha_table')['recruitDetail'])
    recruit_group: List[str] = re.findall(r'★\\n(.*)', recruit_detail)
    recruit_operators = []

    for item in recruit_group:
        recruit_operators += [n.strip().strip('\r') for n in item.split('/')]

    operators_list = JsonData.get_json_data('character_table')
    operators_patch_list = JsonData.get_json_data('char_patch_table')['patchChars']
    voice_data = JsonData.get_json_data('charword_table')
    skins_data = JsonData.get_json_data('skin_table')['charSkins']

    operators_list.update(operators_patch_list)

    Collection.clear_all()

    for n, item in voice_data['charWords'].items():
        char_id = item['wordKey']

        if char_id not in Collection.voice_map:
            Collection.voice_map[char_id] = []

        Collection.voice_map[char_id].append(item)

    for n, item in skins_data.items():
        char_id = item['charId']
        skin_id = item['skinId']

        if 'char_1001_amiya2' in skin_id:
            char_id = 'char_1001_amiya2'

        if 'char_1037_amiya3' in skin_id:
            char_id = 'char_1037_amiya3'

        if char_id not in Collection.skins_map:
            Collection.skins_map[char_id] = []

        Collection.skins_map[char_id].append(item)

    operators: List[OperatorImpl] = []
    birth = {}

    for code, item in operators_list.items():
        if item['profession'] not in ArknightsConfig.classes:
            token = TokenImpl(code, item)
            Collection.tokens_map[code] = token
            Collection.tokens_map[token.name] = token
            Collection.tokens_map[token.en_name] = token
            continue

        operator = OperatorImpl(code=code, data=item, is_recruit=item['name'] in recruit_operators)
        operators.append(operator)

    for item in operators:
        for story in item.stories():
            if story['story_title'] == '基础档案':
                r = re.search(r'\n【(生日|出厂日)】.*?(\d+)月(\d+)日\n', story['story_text'])
                if r:
                    month = int(r.group(2))
                    day = int(r.group(3))

                    if month not in birth:
                        birth[month] = {}
                    if day not in birth[month]:
                        birth[month][day] = []

                    item.birthday = f'{month}月{day}日'
                    birth[month][day].append(item)

                r = re.search(r'性别】(\S+)(\s+)?\n', story['story_text'])
                if r:
                    item.sex = r.group(1)

                break

    birthdays = {}
    for month, days in birth.items():
        birthdays[month] = sorted_dict(days)
    birthdays = sorted_dict(birthdays)

    return {item.name: item for item in operators}, Collection.tokens_map, birthdays


def init_materials():
    building_data = JsonData.get_json_data('building_data')
    item_data = JsonData.get_json_data('item_table')
    formulas = {'WORKSHOP': building_data['workshopFormulas'], 'MANUFACTURE': building_data['manufactFormulas']}

    materials = {}
    materials_map = {}
    materials_made = {}
    materials_source = {}
    for item_id, item in item_data['items'].items():
        if 'p_char' in item_id:
            continue

        material_name = item['name'].strip()
        icon_name = item['iconId']

        materials[item_id] = {
            'material_id': item_id,
            'material_name': material_name,
            'material_icon': icon_name,
            'material_desc': item['usage'],
            'meta_data': item,
        }
        materials_map[material_name] = item_id

        for drop in item['stageDropList']:
            if item_id not in materials_source:
                materials_source[item_id] = {}
            materials_source[item_id][drop['stageId']] = {
                'material_id': item_id,
                'source_place': drop['stageId'],
                'source_rate': drop['occPer'],
            }

        for build in item['buildingProductList']:
            if build['roomType'] in formulas and build['formulaId'] in formulas[build['roomType']]:
                build_cost = formulas[build['roomType']][build['formulaId']]['costs']
                for build_item in build_cost:
                    if item_id not in materials_made:
                        materials_made[item_id] = []
                    materials_made[item_id].append(
                        {
                            'material_id': item_id,
                            'use_material_id': build_item['id'],
                            'use_number': build_item['count'],
                            'made_type': build['roomType'],
                        }
                    )

    return materials, materials_map, materials_made, materials_source


def init_enemies():
    enemies_info = JsonData.get_json_data('enemy_handbook_table')
    enemies_data = JsonData.get_json_data('enemy_database', folder='levels/enemydata')

    enemies_data_map = {}
    for item in enemies_data['enemies']:
        if 'Key' in item:
            enemies_data_map[item['Key']] = item['Value']
        else:
            enemies_data_map[item['key']] = item['value']

    data = {}
    for e_id, info in enemies_info['enemyData'].items():
        name = info['name']

        if name == '-':
            continue

        counter = Counter(data.keys())
        if name in counter:
            name += f'（{counter[name]}）'

        item = {'info': info, 'data': enemies_data_map.get(e_id)}
        data[name] = data[info['enemyId']] = item

    return data


def init_stages():
    activity_table = JsonData.get_json_data('activity_table')['basicInfo']
    operators_list = JsonData.get_json_data('character_table')
    enemies_info = JsonData.get_json_data('enemy_handbook_table')
    stage_data = JsonData.get_json_data('stage_table')['stages']
    item_data = JsonData.get_json_data('item_table')['items']

    def is_ss(key, item):
        if item['isReplicate']:
            return False
        if item['type'] == 'MINISTORY':
            return True
        return item['type'].endswith('SIDE') or ('displayType' in item and item['displayType'] == 'SIDESTORY')

    side_story = [item for key, item in activity_table.items() if is_ss(key, item)]
    side_story.sort(key=lambda n: n['startTime'], reverse=True)

    stage_list: STR_DICT_MAP = {}
    stage_map: STR_DICT_LIST = {}
    side_story_map: STR_DICT_MAP = {n['name']: {} for n in side_story}

    for stage_id, item in stage_data.items():
        if not item['name']:
            continue

        try:
            level_data = JsonData.get_json_data((item['levelId'] or 'no_level').lower(), folder='levels')
        except Exception:
            continue

        level = ''
        if '#f#' in stage_id:
            level = '_hard'
        if 'easy' in stage_id:
            level = '_easy'
        if 'tough' in stage_id:
            level = '_tough'

        stage_key = item['code'] + level
        stage_key_name = remove_punctuation(item['name']) + level

        if level_data:
            enemies = {}
            for wave in level_data['waves']:
                for fragment in wave['fragments']:
                    for action in fragment['actions']:
                        if action['key'] not in enemies_info['enemyData'] or action['actionType'] != 'SPAWN':
                            continue

                        if action['key'] not in enemies:
                            enemies[action['key']] = {**enemies_info['enemyData'][action['key']], 'count': 0}

                        enemies[action['key']]['count'] += action['count']

            level_data['enemiesCount'] = enemies

        if item['stageDropInfo']:
            if item['stageDropInfo']['displayDetailRewards']:
                for info in item['stageDropInfo']['displayDetailRewards']:
                    if info['type'] == 'CHAR':
                        info['detail'] = operators_list[info['id']]
                    else:
                        if info['id'] in item_data:
                            info['detail'] = item_data[info['id']]

        stage_list[stage_id] = {**item, 'levelData': level_data, 'activity': ''}

        if item['code'].startswith('GT'):
            side_story_map['骑兵与猎人'][stage_id] = stage_list[stage_id]
        elif item['code'].startswith('OF'):
            side_story_map['火蓝之心'][stage_id] = stage_list[stage_id]
        else:
            for ss_item in side_story:
                ss_code = ss_item['id']
                ss_name = ss_item['name']

                if ss_code in stage_id:
                    side_story_map[ss_name][stage_id] = stage_list[stage_id]

        for key in [stage_key, stage_key_name]:
            if key not in stage_map:
                stage_map[key] = []

            if stage_id not in stage_map[key]:
                stage_map[key].append(stage_id)

    return stage_list, stage_map, side_story_map


async def get_skin_file(skin_data: dict, encode_url: bool = False):
    skin_id = skin_data['skin_id']

    if skin_id in SkinIndexes.url_indexes:
        quality = bot.get_config('quality')
        url = SkinIndexes.url_indexes[skin_id].replace('quality,Q_90', f'quality,Q_{quality}')
        skin_path = await SkinsPathCache.get_skin_file(skin_id, url, quality)

        if encode_url and skin_path:
            skin_path = skin_path.replace('#', '%23')

        return skin_path


async def get_voice_file(operator: OperatorImpl, voice_key: str, voice_type: str = '', skin_key: str = ''):
    file = PRTS.get_voice_path(PRTS.voices_source, operator, voice_key, voice_type, skin_key)

    if not os.path.exists(file):
        file = await PRTS.download_operator_voices(file, operator, voice_key, voice_type, skin_key)
        if not file:
            return None

    return file


async def get_real_name(operator: str = None):
    return await PRTS.get_real_name(operator)


ArknightsGameData.initialize_methods = [gamedata_initialize]
ArknightsGameData.get_real_name = get_real_name
ArknightsGameDataResource.get_skin_file = get_skin_file
ArknightsGameDataResource.get_voice_file = get_voice_file
ArknightsGameDataResource.parse_template = parse_template
