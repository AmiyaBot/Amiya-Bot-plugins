import os

from amiyabot import PluginInstance, Message, Chain

from .gameBuilder import OperatorPool, game_begin

curr_dir = os.path.dirname(__file__)

bot = PluginInstance(
    name='大帝的CYPHER挑战',
    version='1.0',
    plugin_id='amiyabot-game-wordle2',
    plugin_type='official',
    description='干员竞猜小游戏，可获得合成玉',
    document=f'{curr_dir}/README.md'
)


@bot.on_message(keywords=['大帝挑战', '大帝的挑战', '大帝CYPHER挑战', '大帝的CYPHER挑战'])
async def _(data: Message):
    main_text = '承蒙大家的热情好意！感谢大帝的不胜酒意（？）！\n' \
                'WHATEVER，《大帝的CYPHER挑战》限量测试好评如潮，游戏版本迎来重大更新！\n' \
                '只用一条线索就能破解谜底，这样的强者是否真的存在？\n' \
                '更COOL的接力，更HOT的秘密，只为最懂这片大地的你！\n' \
                '所有群员均可参与游戏，游戏一旦开始，将暂停其他功能的使用哦！\n' \
                'PUT UR HANDS UP！'

    await data.send(Chain(data).text(main_text))
    await data.send(Chain(data).text('准备看题！'))

    pool = OperatorPool()

    while pool.is_empty:
        operator = pool.pick_one()
        while not operator.nation or not operator.drawer or operator.race == '未知':
            operator = pool.pick_one()

        data = await game_begin(data, operator)
