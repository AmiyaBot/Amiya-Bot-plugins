import asyncio

from amiyabot import PluginInstance, Message, Chain, TencentBotInstance

from .gameBuilder import OperatorPool
from .gameStart import game_begin, curr_dir

bot = PluginInstance(
    name='大帝的CYPHER挑战',
    version='1.3',
    plugin_id='amiyabot-game-wordle2',
    plugin_type='official',
    description='干员竞猜小游戏，可获得合成玉',
    document=f'{curr_dir}/README.md'
)


@bot.on_message(keywords=['大帝挑战', '大帝的挑战', '大帝CYPHER挑战', '大帝的CYPHER挑战'])
async def _(data: Message):
    if type(data.instance) is TencentBotInstance:
        if not data.is_admin and data.channel_id != '6901789':
            return Chain(data).text('抱歉博士，非【小游戏专区】只能由管理员发起游戏哦~')
    else:
        if not data.is_admin:
            return Chain(data).text('抱歉博士，只能由管理员发起游戏哦~')

    main_text = '承蒙大家的热情好意！感谢大帝的不胜酒意（？）！\n' \
                'WHATEVER，《大帝的CYPHER挑战》限量测试好评如潮，游戏版本迎来重大更新！\n' \
                '只用一条线索就能破解谜底，这样的强者是否真的存在？\n' \
                '更COOL的接力，更HOT的秘密，只为最懂这片大地的你！\n' \
                '所有群员均可参与游戏，游戏一旦开始，将暂停其他功能的使用哦！\n' \
                'PUT UR HANDS UP！'

    await data.send(Chain(data, at=False).text(main_text))

    pool = OperatorPool()

    while True:
        if pool.is_empty:
            await data.send(
                Chain(data, at=False).text('竟然把所有干员都猜完了...这可怕的毅力，不愧是巴别塔的恶灵！再来！'))
            pool = OperatorPool()
            await asyncio.sleep(2)

        await data.send(Chain(data, at=False).text('题目准备中...共有10次机会竞猜！'))
        await asyncio.sleep(2)

        operator = pool.pick_one()
        while not operator.nation or not operator.drawer or operator.race == '未知':
            operator = pool.pick_one()

        data = await game_begin(data, operator)
        if not data:
            break
