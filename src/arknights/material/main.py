import os
import json
import asyncio

from typing import Dict
from amiyabot import event_bus
from amiyabot.network.httpRequests import http_requests

from core import log, Message, Chain, AmiyaBotPluginInstance, Requirement
from core.util import any_match, find_most_similar, remove_punctuation
from core.database.bot import *
from core.resource.arknightsGameData import ArknightsGameData

from functools import cmp_to_key

curr_dir = os.path.dirname(__file__)

material_images_source = 'resource/gamedata/item/'
icon_size = 34
line_height = 16
side_padding = 10

yituliu_t3 = 'https://backend.yituliu.site/stage/t3?expCoefficient=0.625'
yituliu_t2 = 'https://backend.yituliu.site/stage/t2?expCoefficient=0.625'


@table
class YituliuData(BotBaseModel):
    materialId: str = CharField(null=True)
    stageId: str = CharField(null=True)
    stageEfficiency: int = FloatField(null=True)
    apExpect: float = FloatField(null=True)
    knockRating: float = FloatField(null=True)
    sampleConfidence: float = FloatField(null=True)


class MaterialData:
    materials: List[str] = []

    @staticmethod
    async def save_yituliu_data():
        async with log.catch('yituliu data save error:'):
            t3 = await http_requests.get(yituliu_t3)
            t3 = json.loads(t3)
            t2 = await http_requests.get(yituliu_t2)
            t2 = json.loads(t2)

            yituliu_data = []

            for i in t3['data']:
                material_id = i[0]['itemId']
                if material_id == '30012':
                    material_id = '30013'
                for j in i:
                    yituliu_data.append(
                        {
                            'materialId': material_id,
                            'stageId': j['stageCode'],
                            'sampleConfidence': j['sampleConfidence'],
                            'stageEfficiency': j['stageEfficiency'],
                            'apExpect': j['apExpect'],
                            'knockRating': j['knockRating'],
                        }
                    )

            for i in t2['data']:
                material_id = i[0]['itemId']
                for j in i:
                    yituliu_data.append(
                        {
                            'materialId': material_id,
                            'stageId': j['stageCode'],
                            'sampleConfidence': j['sampleConfidence'],
                            'stageEfficiency': j['stageEfficiency'],
                            'apExpect': j['apExpect'],
                            'knockRating': j['knockRating'],
                        }
                    )

            YituliuData.truncate_table()
            YituliuData.batch_insert(yituliu_data)

            log.info('yituliu data save successful.')

    @staticmethod
    async def init_materials():
        log.info('building materials names keywords...')

        for name in ArknightsGameData.materials_map.keys():
            MaterialData.materials.append(name)

    @classmethod
    def find_material_children(cls, material_id: str, parent_id: str = ''):
        game_data = ArknightsGameData
        children = []

        if material_id in game_data.materials_made:
            for item in game_data.materials_made[material_id]:
                children.append(
                    {
                        **item,
                        **game_data.materials[item['use_material_id']],
                        'children': cls.find_material_children(item['use_material_id'], material_id)
                        if item['use_material_id'] != parent_id
                        else [],
                    }
                )

        return children

    @classmethod
    def check_material(cls, name):
        game_data = ArknightsGameData

        if name not in game_data.materials_map:
            return None

        material = game_data.materials[game_data.materials_map[name]]
        material_id = material['material_id']

        result = {
            'name': name,
            'info': material,
            'children': cls.find_material_children(material_id),
            'source': {'main': [], 'act': []},
            'recommend': [],
        }

        yituliu_data = cls.find_yituliu_data([material, *cls.find_material_children(material_id)])
        if yituliu_data:
            for material_name, items in yituliu_data.items():
                sorted_list = sorted(list(items), key=cmp_to_key(cls.compare_efficiency), reverse=True)
                result['recommend'].append(
                    {
                        'name': material_name,
                        'stages': [
                            {
                                'stageId': j.stageId,
                                'stageEfficiency': f'{round(j.stageEfficiency)}%',
                                'apExpect': round(j.apExpect),
                                'knockRating': f'{round(j.knockRating * 100)}%',
                                'sampleConfidence': f'{round(j.sampleConfidence)}%',
                            }
                            for j in sorted_list
                        ],
                    }
                )

        if material_id in game_data.materials_source:
            source = game_data.materials_source[material_id]

            for code in source.keys():
                if code not in game_data.stages:
                    continue

                stage = game_data.stages[code]
                info = {'code': stage['code'], 'name': stage['name'], 'rate': source[code]['source_rate']}

                if 'main' in code:
                    result['source']['main'].append(info)
                else:
                    result['source']['act'].append(info)

        return result

    @classmethod
    def find_yituliu_data(cls, items: List[dict]):
        data: Dict[str, List[YituliuData]] = {}
        for item in items:
            stages = YituliuData.select().where(YituliuData.materialId == item['material_id'])
            if stages:
                data[item['material_name']] = stages
            if 'children' in item:
                data.update(cls.find_yituliu_data(item['children']))

        return data

    @classmethod
    def compare_knock_rating(cls, a, b):
        return a.knockRating - b.knockRating

    @classmethod
    def compare_ap_expect(cls, a, b):
        if a.apExpect <= b.apExpect:
            r = (b.apExpect - a.apExpect) / b.apExpect
            if r > 0.03:
                return 1
            return cls.compare_knock_rating(a, b)
        else:
            return -cls.compare_ap_expect(b, a)

    @classmethod
    def compare_efficiency(cls, a, b):
        if a.stageEfficiency >= b.stageEfficiency:
            r = (a.stageEfficiency - b.stageEfficiency) / a.stageEfficiency
            if r > 0.03:
                return 1
            return cls.compare_ap_expect(a, b)
        else:
            return -cls.compare_efficiency(b, a)


class MaterialPluginInstance(AmiyaBotPluginInstance):
    def install(self):
        asyncio.create_task(MaterialData.save_yituliu_data())
        asyncio.create_task(MaterialData.init_materials())

    def uninstall(self):
        event_bus.unsubscribe('gameDataInitialized', update)


bot = MaterialPluginInstance(
    name='明日方舟材料物品查询',
    version='2.3',
    plugin_id='amiyabot-arknights-material',
    plugin_type='official',
    description='查询明日方舟材料和物品资料',
    document=f'{curr_dir}/README.md',
    requirements=[Requirement('amiyabot-arknights-gamedata', official=True)],
)


@event_bus.subscribe('gameDataInitialized')
def update(_):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        asyncio.create_task(MaterialData.init_materials())


async def verify(data: Message):
    name = find_most_similar(data.text.replace('材料', '').replace('阿米娅', ''), MaterialData.materials)
    keyword = any_match(data.text, ['材料'])

    if not keyword and name and remove_punctuation(name) not in remove_punctuation(data.text):
        return False

    if name or keyword:
        return True, (5 if keyword else 1), name

    return False


@bot.on_message(verify=verify, allow_direct=True)
async def _(data: Message):
    name = data.verify.keypoint

    if not name:
        wait = await data.wait(Chain(data).text('博士，请说明需要查询的材料名称'))
        if not wait or not wait.text:
            return None
        name = find_most_similar(wait.text, MaterialData.materials)

        if not name:
            return Chain(data).text(f'博士，没有找到材料{wait.text}的资料 >.<')

    if name:
        result = MaterialData.check_material(name)
        if result:
            return Chain(data).html(f'{curr_dir}/template/material.html', result)


@bot.timed_task(each=3600)
async def _(instance):
    await MaterialData.save_yituliu_data()
