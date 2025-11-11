import os
import json
import copy

from core.resource.arknightsGameData import ArknightsGameData, ArknightsGameDataResource
from core.util import integer, snake_case_to_pascal_case

from .operatorCore import OperatorSearchInfo


class OperatorData:
    @classmethod
    async def get_operator_detail(cls, info: OperatorSearchInfo):
        operators = ArknightsGameData.operators

        if not info.name or info.name not in operators:
            return None, None

        operator = operators[info.name]

        real_name = await ArknightsGameData.get_real_name(operator.origin_name)

        detail, trust = operator.detail()
        modules = operator.modules()

        module_attrs = []
        if modules:
            for module in modules:
                module_attr = {}
                if module['detail']:
                    attrs = module['detail']['phases'][-1]['attributeBlackboard']
                    for attr in attrs:
                        module_attr[snake_case_to_pascal_case(attr['key'])] = integer(attr['value'])

                module_attrs.append({**module, 'attrs': module_attr})

        skills, skills_id, skills_cost, skills_desc = operator.skills()
        skins = operator.skins()

        infos = [
            'id',
            'cv',
            'type',
            'tags',
            'range',
            'rarity',
            'number',
            'name',
            'en_name',
            'wiki_name',
            'index_name',
            'origin_name',
            'classes',
            'classes_sub',
            'classes_code',
            'race',
            'drawer',
            'team',
            'group',
            'nation',
            'birthday',
            'profile',
            'impression',
            'limit',
            'unavailable',
            'potential_item',
            'is_recruit',
            'is_sp',
        ]

        operator_info = {
            'info': {'real_name': real_name, **{n: getattr(operator, n) for n in infos}},
            'skin': (await ArknightsGameDataResource.get_skin_file(skins[0], encode_url=True)) if skins else '',
            'trust': trust,
            'detail': detail,
            'modules': module_attrs,
            'talents': operator.talents(),
            'potential': operator.potential(),
            'building_skills': operator.building_skills(),
            'skill_list': skills,
            'skills_cost': skills_cost,
            'skills_desc': skills_desc,
        }
        tokens = {'id': operator.id, 'name': operator.name, 'tokens': operator.tokens()}

        return operator_info, tokens

    @classmethod
    async def get_level_up_cost(cls, info: OperatorSearchInfo):
        operators = ArknightsGameData.operators
        materials = ArknightsGameData.materials

        if not info.name or info.name not in operators:
            return None

        operator = operators[info.name]
        evolve_costs = operator.evolve_costs()

        evolve_costs_list = {}
        for item in evolve_costs:
            material = materials[item['use_material_id']]

            if item['evolve_level'] not in evolve_costs_list:
                evolve_costs_list[item['evolve_level']] = []

            evolve_costs_list[item['evolve_level']].append(
                {
                    'material_name': material['material_name'],
                    'material_icon': material['material_icon'],
                    'use_number': item['use_number'],
                }
            )

        skills, skills_id, skills_cost, skills_desc = operator.skills()

        skills_cost_list = {}
        for item in skills_cost:
            material = materials[item['use_material_id']]
            skill_no = item['skill_no'] or 'common'

            if skill_no and skill_no not in skills_cost_list:
                skills_cost_list[skill_no] = {}

            if item['level'] not in skills_cost_list[skill_no]:
                skills_cost_list[skill_no][item['level']] = []

            skills_cost_list[skill_no][item['level']].append(
                {
                    'material_name': material['material_name'],
                    'material_icon': material['material_icon'],
                    'use_number': item['use_number'],
                }
            )

        skins = operator.skins()
        skin = ''
        if skins:
            skin = await ArknightsGameDataResource.get_skin_file(
                skins[1] if len(skins) > 1 else skins[0], encode_url=True
            )

        return {'skin': skin, 'evolve_costs': evolve_costs_list, 'skills': skills, 'skills_cost': skills_cost_list}

    @classmethod
    async def get_skills_detail(cls, info: OperatorSearchInfo):
        operators = ArknightsGameData.operators

        if not info.name or info.name not in operators:
            return None

        operator = operators[info.name]
        skills, skills_id, skills_cost, skills_desc = operator.skills()

        return {'skills': skills, 'skills_desc': skills_desc}

    @classmethod
    def find_operator_module(cls, info: OperatorSearchInfo, is_story: bool):
        operators = ArknightsGameData.operators
        materials = ArknightsGameData.materials

        operator = operators[info.name]
        modules = copy.deepcopy(operator.modules())

        if not modules:
            return None

        if is_story:
            return cls.find_operator_module_story(modules)

        def parse_trait_data(data):
            if data is None:
                return
            for candidate in data:
                blackboard = candidate['blackboard']
                if candidate['additionalDescription']:
                    candidate['additionalDescription'] = ArknightsGameDataResource.parse_template(
                        blackboard, candidate['additionalDescription']
                    )
                if candidate['overrideDescripton']:
                    candidate['overrideDescripton'] = ArknightsGameDataResource.parse_template(
                        blackboard, candidate['overrideDescripton']
                    )

        def parse_talent_data(data):
            if data is None:
                return
            for candidate in data:
                blackboard = candidate['blackboard']
                if candidate['upgradeDescription']:
                    candidate['upgradeDescription'] = ArknightsGameDataResource.parse_template(
                        blackboard, candidate['upgradeDescription']
                    )

        for item in modules:
            if item['itemCost']:
                for lvl, item_cost in item['itemCost'].items():
                    for i, cost in enumerate(item_cost):
                        material = materials[cost['id']]
                        item_cost[i] = {**cost, 'info': material}

            if item['detail']:
                for stage in item['detail']['phases']:
                    for part in stage['parts']:
                        parse_trait_data(part['overrideTraitDataBundle']['candidates'])
                        parse_talent_data(part['addOrOverrideTalentDataBundle']['candidates'])

        return modules

    @staticmethod
    def find_operator_module_story(modules):
        text = ''
        for item in modules:
            text += '\n\n## %s\n\n' % item['uniEquipName']
            text += item['uniEquipDesc'].replace('\n', '<br>')

        return text


class JsonData:
    cache = {}

    @classmethod
    def get_json_data(cls, name: str, folder: str = 'excel'):
        if name not in cls.cache:
            path = f'resource/gamedata/gamedata/{folder}/{name}.json'
            if os.path.exists(path):
                with open(path, mode='r', encoding='utf-8') as src:
                    cls.cache[name] = json.load(src)
            else:
                return {}

        return cls.cache[name]
