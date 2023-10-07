import asyncio

from core import Message, Chain, AmiyaBotPluginInstance, Requirement
from core.util import any_match

from .gameBuilder import OperatorPool
from .gameStart import game_begin, curr_dir

bot = AmiyaBotPluginInstance(
    name='大帝的CYPHER挑战',
    version='2.1',
    plugin_id='amiyabot-game-wordle2',
    plugin_type='official',
    description='干员竞猜小游戏，可获得合成玉',
    document=f'{curr_dir}/README.md',
    requirements=[Requirement('amiyabot-arknights-gamedata')],
)


@bot.on_message(keywords=['大帝挑战', '大帝的挑战', '大帝CYPHER挑战', '大帝的CYPHER挑战'])
async def _(data: Message):
    main_text = (
        '承蒙大家的热情好意！感谢大帝的不胜酒意（？）！\n'
        'WHATEVER，《大帝的CYPHER挑战》限量测试好评如潮，游戏版本迎来重大更新！\n'
        '只用一条线索就能破解谜底，这样的强者是否真的存在？\n'
        '更COOL的接力，更HOT的秘密，只为最懂这片大地的你！\n'
        '所有群员均可参与游戏，游戏一旦开始，将暂停其他功能的使用哦！\n'
        'PUT UR HANDS UP！\n\n'
        '请选择难度：\n\n【普通】\n【硬核】'
    )

    choice = await data.wait(Chain(data).text(main_text), force=True)
    if not choice:
        return None
    choice_level = any_match(choice.text, ['普通', '硬核'])
    if not choice_level:
        return Chain(choice).text('博士，您没有选择难度哦，游戏取消。')

    pool = OperatorPool()
    prev = None
    hardcode = choice_level == '硬核'

    while True:
        if pool.is_empty:
            await data.send(Chain(data, at=False).text('竟然把所有干员都猜完了...这可怕的毅力，不愧是巴别塔的恶灵！再来！'))
            pool = OperatorPool()
            await asyncio.sleep(2)

        await data.send(Chain(data, at=False).text('题目准备中...共有10次机会竞猜！'))
        await asyncio.sleep(2)

        operator = pool.pick_one()
        if not hardcode:
            if not prev:
                prev = pool.pick_one()

            await data.send(Chain(data, at=False).text(f'{prev.name}为博士们提供了帮助！'))

        data = await game_begin(data, operator, prev, hardcode)
        prev = operator

        if not data:
            break
