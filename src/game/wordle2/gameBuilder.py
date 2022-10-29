import copy
import random

from amiyabot import Message
from core.resource.arknightsGameData import ArknightsGameData, Operator


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
        self.operator = operator
        self.shadow = {

        }

        self.times = 0
        self.max_times = 10

        self.build_shadow_info()

    def build_shadow_info(self):
        info_map = [
            {'title': '稀有度', 'value': self.operator.rarity, 'show': False},
            {'title': '职业', 'value': self.operator.classes, 'show': False},
            {'title': '子职业', 'value': self.operator.classes_sub, 'show': False},
            {'title': '阵营', 'value': self.operator.nation, 'show': False},
            {'title': '种族', 'value': self.operator.race, 'show': False},
            {'title': '画师', 'value': self.operator.drawer, 'show': False},
        ]

        while info_map:
            index = random.randint(0, len(info_map) - 1)
            item = info_map.pop(index)

            self.shadow[item['title']] = item


async def game_begin(data: Message, operator: Operator):
    process = GuessProcess(operator)

    print(process)
