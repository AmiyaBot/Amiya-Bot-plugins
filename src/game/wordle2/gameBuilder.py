import copy
import random

from typing import Dict
from dataclasses import dataclass, asdict
from core.resource.arknightsGameData import ArknightsGameData, Operator


class OperatorPool:
    def __init__(self):
        self.operators = copy.deepcopy(ArknightsGameData().operators)

    @property
    def is_empty(self):
        return not len(self.operators.keys())

    def pick_one(self):
        operator = self.operators.pop(
            random.choice(
                list(
                    self.operators.keys()
                )
            )
        )
        if '预备干员' in operator.name:
            return self.pick_one()
        return operator


@dataclass
class TagElement:
    title: str
    value: str
    show_title: bool = True
    show_value: bool = False

    def show(self):
        self.show_title = True
        self.show_value = True


class GuessProcess:
    def __init__(self, operator: Operator, prev: Operator, hardcode: bool = False):
        self.wrongs = {}

        self.max_count = 10
        self.operator = operator
        self.hardcode = hardcode

        self.bingo = False
        self.display = True
        self.tips_lock = False

        if hardcode:
            self.tags = self.__build_hardcode()
        else:
            self.tags = self.__build_normal()

        for tag in self.tags.values():
            if tag.value == '未知':
                tag.show()

        if not hardcode and prev:
            self.guess(prev)

    def __build_normal(self, show_title: bool = True) -> Dict[str, TagElement]:
        return {
            'rarity': TagElement('稀有度', self.operator.rarity, show_title),
            'classes': TagElement('职业', self.operator.classes, show_title),
            'classes_sub': TagElement('子职业', self.operator.classes_sub, show_title),
            'race': TagElement('种族', self.operator.race if self.operator.race != '未公开' else '未知', show_title),
            'nation': TagElement('势力', self.operator.nation, show_title),
            'sex': TagElement('性别', self.operator.sex, show_title),
        }

    def __build_hardcode(self) -> Dict[str, TagElement]:
        tags = {
            **self.__build_normal(False),
            'team': TagElement('队伍', self.operator.team, False),
            'group': TagElement('阵营', self.operator.group, False),
            'drawer': TagElement('画师', self.operator.drawer, False),
        }
        res = {}

        while len(res.keys()) < 6:
            if not tags.keys():
                break

            field = random.choice(list(tags.keys()))
            item = tags.pop(field)

            if item.value == '未知':
                continue

            res[field] = item

        return res

    @property
    def count(self):
        return len(self.wrongs.keys())

    @property
    def closed_tags(self):
        return [item for _, item in self.tags.items() if item.show_value is False]

    @property
    def view_data(self):
        return {
            'tags': {field: asdict(item) for field, item in self.tags.items()},
            'wrongs': self.wrongs,
            'hardcode': self.hardcode
        }

    def get_tips(self):
        if self.tips_lock:
            return None

        disclosed: TagElement = random.choice(self.closed_tags)
        disclosed.show()

        return disclosed

    def guess(self, answer: Operator):
        self.tips_lock = False

        if answer.id == self.operator.id:
            self.bingo = True
            return -1, 0

        unlock = 0
        wrong = {}

        for field, item in self.tags.items():
            answer_value = getattr(answer, field)
            if answer_value == item.value:
                if item.show_value is False:
                    unlock += 1

                item.show()

                wrong[field] = 'ok'
            else:
                if field == 'rarity':
                    if answer_value > item.value:
                        wrong[field] = 'down'
                    if answer_value < item.value:
                        wrong[field] = 'up'
                else:
                    if answer_value in ['未知', '未公开']:
                        wrong[field] = 'unknown'
                    else:
                        wrong[field] = 'ng'

        self.wrongs[answer.id] = wrong

        return len([item for _, item in wrong.items() if item == 'ok']), unlock
