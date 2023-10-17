import os
import json

from core.resource.arknightsGameData import ArknightsConfig
from core.database.bot import BotBaseModel, OperatorConfig
from amiyabot import log
from amiyabot.database import *
from amiyabot.network.download import download_async

config = {
    'classes': {
        'CASTER': '术师',
        'MEDIC': '医疗',
        'PIONEER': '先锋',
        'SNIPER': '狙击',
        'SPECIAL': '特种',
        'SUPPORT': '辅助',
        'TANK': '重装',
        'WARRIOR': '近卫',
    },
    'token_classes': {'TOKEN': '召唤物', 'TRAP': '装置'},
    'high_star': {'5': '资深干员', '6': '高级资深干员'},
    'types': {'ALL': '不限部署位', 'MELEE': '近战位', 'RANGED': '远程位'},
}

html_symbol = {'<替身>': '&lt;替身&gt;', '<支援装置>': '&lt;支援装置&gt;'}

gamedata_path = 'resource/gamedata'


@table
class SkinsPathCache(BotBaseModel):
    skin_id: str = CharField(unique=True)
    skin_path: str = CharField()
    quality: int = IntegerField()

    @classmethod
    async def get_skin_file(cls, skin_id: str, url: str, quality: int = 90):
        skin_path = f'{gamedata_path}/skin/{skin_id}.png'

        cache: SkinsPathCache = cls.get_or_none(skin_id=skin_id)
        need_download = True

        if os.path.exists(skin_path) and cache and cache.quality == quality:
            need_download = False

        if need_download:
            create_dir(skin_path, is_file=True)

            log.debug(f'downloading {skin_id}.png (Q{quality})...')

            content = await download_async(url)
            if content:
                with open(skin_path, mode='wb') as file:
                    file.write(content)

                if cache:
                    cls.update(quality=quality, skin_path=skin_path).where(cls.skin_id == skin_id).execute()
                else:
                    cls.create(skin_id=skin_id, skin_path=skin_path, quality=quality)
            else:
                return None

        return skin_path


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


ArknightsConfig.initialize_methods = [config_initialize]
