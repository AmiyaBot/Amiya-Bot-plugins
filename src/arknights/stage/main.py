import os
import jieba
import asyncio

from amiyabot import PluginInstance, event_bus

from core import log, Message, Chain
from core.util import any_match, remove_punctuation, get_index_from_text
from core.resource.arknightsGameData import ArknightsGameData

curr_dir = os.path.dirname(__file__)

multiple_zone_stage = {
    'CF-9': 2
}


class Stage:
    @staticmethod
    async def init_stages():
        log.info('building stages keywords dict...')

        stages = list(ArknightsGameData.stages_map.keys()) + list(ArknightsGameData.side_story_map.keys())

        with open(f'{curr_dir}/stages.txt', mode='w', encoding='utf-8') as file:
            file.write('\n'.join([f'{name} 500 n' for name in stages]))

        jieba.load_userdict(f'{curr_dir}/stages.txt')


class StagePluginInstance(PluginInstance):
    def install(self):
        asyncio.create_task(Stage.init_stages())

    def uninstall(self):
        event_bus.unsubscribe('gameDataInitialized', update)


bot = StagePluginInstance(
    name='明日方舟关卡查询',
    version='2.1',
    plugin_id='amiyabot-arknights-stages',
    plugin_type='official',
    description='查询明日方舟关卡资料',
    document=f'{curr_dir}/README.md'
)


@event_bus.subscribe('gameDataInitialized')
def update(_):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        bot.install()


@bot.on_message(keywords=['地图', '关卡'], allow_direct=True, level=5)
async def _(data: Message):
    words = jieba.lcut(
        remove_punctuation(data.text, ['-']).upper().replace(' ', '')
    )

    level = ''
    level_str = ''
    if any_match(data.text, ['突袭']):
        level = '_hard'
        level_str = '（突袭）'
    if any_match(data.text, ['简单', '剧情']):
        level = '_easy'
        level_str = '（剧情）'
    if any_match(data.text, ['困难', '磨难']):
        level = '_tough'
        level_str = '（磨难）'

    stage_id = None
    stage_ids = []
    stages_map = ArknightsGameData.stages_map

    for item in words:
        stage_key = item + level
        if stage_key in stages_map:
            stage_ids = stages_map[stage_key]

    if stage_ids:
        if len(stage_ids) == 1:
            stage_id = stage_ids[0]
        else:
            text = '博士，找到以下同名或同代号关卡，请回复序号查询对应的关卡：\n\n'

            for index, item in enumerate(stage_ids):
                stage_data = ArknightsGameData.stages[item]

                text += f'[{index + 1}] ' + '{code} {name}\n'.format(**stage_data)

            wait = await data.wait(Chain(data).text(text))

            if not wait:
                return

            index = get_index_from_text(wait.text_digits, stage_ids)
            stage_id = stage_ids[index]

    if stage_id:
        stage_data = ArknightsGameData.stages[stage_id]
        res = {
            **stage_data,
            'name': stage_data['name'] + level_str,
            'zones': multiple_zone_stage[stage_data['code']] if stage_data['code'] in multiple_zone_stage else 0
        }

        if level == '_easy':
            main_level = ArknightsGameData.stages.get(stage_id.replace('easy', 'main'))
            if main_level:
                res['levelData'] = main_level['levelData']

        if not os.path.exists('resource/gamedata/map/%s.png' % res['stageId'].replace('#f#', '')):
            res['stageId'] = res['stageId'].replace('tough', 'main').replace('easy', 'main')

        from core.util import create_test_data
        create_test_data(res, 'log/test2.js')

        return Chain(data).html(f'{curr_dir}/template/stage.html', res)
    else:
        for key in words:
            if key in ArknightsGameData.side_story_map:
                ss = ArknightsGameData.side_story_map[key]

                text = f'博士，以下是活动【{key}】的关卡列表。\n发送“兔兔地图 + 关卡代号或关卡名”查看详情。\n|关卡代号|关卡名|关卡代号|关卡名|\n|----|----|----|----|\n'
                for index, item in enumerate(ss.values()):
                    text += '|%s|%s%s' % (
                        item['code'] + ('**突袭**' if item['difficulty'] == 'FOUR_STAR' else ''),
                        item['name'] + ('**（突袭）**' if item['difficulty'] == 'FOUR_STAR' else ''),
                        '|\n' if (index + 1) % 2 == 0 else ''
                    )
                return Chain(data).markdown(text)

        if '活动' in data.text:
            text = f'博士，以下是活动列表。\n发送“兔兔地图 + 活动名”查看详情。\n|活动名|活动名|活动名|活动名|\n|----|----|----|----|\n'
            for index, act_name in enumerate(reversed(ArknightsGameData.side_story_map.keys())):
                text += '|%s%s' % (
                    act_name,
                    '|\n' if (index + 1) % 4 == 0 else ''
                )
            return Chain(data).markdown(text)

        return Chain(data).text('抱歉博士，没有查询到相关地图信息')
