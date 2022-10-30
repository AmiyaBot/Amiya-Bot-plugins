import copy
import random

from core.resource.arknightsGameData import ArknightsGameData, Operator

nations = {
    'laterano': '拉特兰',
    'kazimierz': '卡西米尔',
    'columbia': '哥伦比亚',
    'lungmen': '龙门',
    'higashi': '东国',
    'victoria': '维多利亚',
    'sargon': '萨尔贡',
    'rhodes': '罗德岛',
    'yan': '炎国',
    'iberia': '伊比利亚',
    'ursus': '乌萨斯',
    'siracusa': '叙拉古',
    'kjerag': '谢拉格',
    'egir': '阿戈尔',
    'rim': '雷姆必拓',
    'minos': '米诺斯',
    'bolivar': '玻利瓦尔',
    'sami': '萨米',
    'leithanien': '莱塔尼亚'
}


class OperatorPool:
    def __init__(self):
        self.operators = copy.deepcopy(ArknightsGameData().operators)

    @property
    def is_empty(self):
        return len(self.operators.keys())

    def pick_one(self):
        return self.operators.pop(
            random.choice(
                list(
                    self.operators.keys()
                )
            )
        )


class GuessProcess:
    def __init__(self, operator: Operator):
        self.tags = {
            'rarity': {'title': '稀有度', 'value': operator.rarity, 'show': False},
            'classes': {'title': '职业', 'value': operator.classes, 'show': False},
            'classes_sub': {'title': '子职业', 'value': operator.classes_sub, 'show': False},
            'race': {'title': '种族', 'value': operator.race, 'show': False},
            'drawer': {'title': '画师', 'value': operator.drawer, 'show': False},
            'nation': {'title': '势力', 'value': nations.get(operator.nation, '未知'), 'show': False},
        }
        self.wrongs = {}
        self.max_count = 10
        self.operator = operator

        self.bingo = False
        self.display = True
        self.tips_lock = False

    @property
    def count(self):
        return len(self.wrongs.keys())

    @property
    def view_data(self):
        return {
            'tags': self.tags,
            'wrongs': self.wrongs
        }

    def get_tips(self):
        if self.tips_lock:
            return None

        disclosed = random.choice([item for _, item in self.tags.items() if item['show'] is False])
        disclosed['show'] = True

        return disclosed

    def guess(self, answer: Operator):
        self.tips_lock = False

        if answer.id == self.operator.id:
            self.bingo = True
            return -1, 0

        unlock = 0
        for field, item in self.tags.items():
            if getattr(answer, field) == item['value']:
                if item['show'] is False:
                    unlock += 1
                item['show'] = True

        wrong = {
            'rarity': 'ok',
            'classes': 'ok' if answer.classes == self.operator.classes else 'ng',
            'classes_sub': 'ok' if answer.classes_sub == self.operator.classes_sub else 'ng',
            'race': 'ok' if answer.race == self.operator.race else 'ng',
            'drawer': 'ok' if answer.drawer == self.operator.drawer else 'ng',
            'nation': 'ok' if answer.nation == self.operator.nation else 'ng',
        }

        if answer.rarity > self.operator.rarity:
            wrong['rarity'] = 'down'
        if answer.rarity < self.operator.rarity:
            wrong['rarity'] = 'up'

        self.wrongs[answer.id] = wrong

        return len([item for _, item in wrong.items() if item == 'ok']), unlock
