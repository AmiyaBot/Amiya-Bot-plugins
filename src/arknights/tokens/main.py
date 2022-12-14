import os
import jieba
import asyncio

from amiyabot import PluginInstance

from core import log, Message, Chain
from core.util import find_similar_list
from core.resource.arknightsGameData import ArknightsGameData

curr_dir = os.path.dirname(__file__)


class InitToken:
    @staticmethod
    async def init_token():
        log.info('building tokens keywords dict...')

        keywords = [f'{code} 500 n' for code in ArknightsGameData.tokens.keys()]

        with open(f'{curr_dir}/tokens.txt', mode='w', encoding='utf-8') as file:
            file.write('\n'.join(keywords))
        jieba.load_userdict(f'{curr_dir}/tokens.txt')


class TokenPluginInstance(PluginInstance):
    def install(self):
        asyncio.create_task(InitToken.init_token())


bot = TokenPluginInstance(
    name='明日方舟召唤物查询',
    version='1.1',
    plugin_id='amiyabot-arknights-tokens',
    plugin_type='official',
    description='查询明日方舟召唤物资料',
    document=f'{curr_dir}/README.md'
)


@bot.on_message(keywords=['召唤物'], allow_direct=True)
async def _(data: Message):
    text = data.text_origin.replace('召唤物', '', 1)
    result = find_similar_list(text, list(ArknightsGameData.tokens.keys()), _top_only=False)[0]

    if not result:
        return None

    tokens = []
    for r, l in result.items():
        if r < 1:
            continue
        tokens += [ArknightsGameData.tokens[item] for item in l]

    return Chain(data).html(f'{curr_dir}/template/token.html', {
        'tokens': [
            {
                'id': item.id,
                'type': item.type,
                'name': item.name,
                'en_name': item.en_name,
                'description': item.description,
                'attr': item.attr
            } for item in tokens
        ]
    })
