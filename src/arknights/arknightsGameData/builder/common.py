import os
import sys
import json

from core.resource.arknightsGameData import ArknightsConfig
from core.database.bot import OperatorConfig
from amiyabot import log

config = {
    'classes': {
        'CASTER': '术师',
        'MEDIC': '医疗',
        'PIONEER': '先锋',
        'SNIPER': '狙击',
        'SPECIAL': '特种',
        'SUPPORT': '辅助',
        'TANK': '重装',
        'WARRIOR': '近卫'
    },
    'token_classes': {
        'TOKEN': '召唤物',
        'TRAP': '装置'
    },
    'high_star': {
        '5': '资深干员',
        '6': '高级资深干员'
    },
    'types': {
        'ALL': '不限部署位',
        'MELEE': '近战位',
        'RANGED': '远程位'
    }
}

html_symbol = {
    '<替身>': '&lt;替身&gt;',
    '<支援装置>': '&lt;支援装置&gt;'
}


def config_initialize(cls: ArknightsConfig):
    limit = []
    unavailable = []

    log.info(f'Initializing ArknightsConfig...')

    for item in OperatorConfig.select():
        item: OperatorConfig
        if item.operator_type in [0, 1]:
            limit.append(item.operator_name)
        else:
            unavailable.append(item.operator_name)

    cls.classes = config['classes']
    cls.token_classes = config['token_classes']
    cls.high_star = config['high_star']
    cls.types = config['types']
    cls.limit = limit
    cls.unavailable = unavailable

    log.info(f'ArknightsConfig initialize completed.')


def initialize_progress(_list, name: str = ''):
    count = len(_list)

    def print_bar():
        p = int(curr / count * 100)
        block = int(p / 4)
        progress_line = '=' * block + ' ' * (25 - block)

        msg = f'Initializing {name}...progress: [{progress_line}] {curr}/{count} ({p}%)'

        print('\r', end='')
        print(msg, end='')

        sys.stdout.flush()

    curr = 0

    print_bar()
    for item in _list:
        yield item
        curr += 1
        print_bar()

    print()


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

    @classmethod
    def clear_cache(cls, name: str = None):
        if name:
            del cls.cache[name]
        else:
            cls.cache = {}


ArknightsConfig.initialize_methods.append(config_initialize)
