import asyncio
import random

from amiyabot import PluginInstance
from amiyabot.adapters.tencent import TencentBotInstance
from core.database.user import UserInfo

from .wordleBuilder import *


class WordlePluginInstance(PluginInstance):
    def install(self):
        pass


bot = WordlePluginInstance(
    name='兔兔猜字谜',
    version='1.2',
    plugin_id='amiyabot-game-wordle',
    plugin_type='official',
    description='干员竞猜小游戏，可获得合成玉',
    document=f'{curr_dir}/README.md'
)


@bot.on_message(keywords=['猜字谜', '字谜', '字谜猜猜乐'], level=1)
async def _(data: Message):
    if type(data.instance) is TencentBotInstance:
        if not data.is_admin and data.channel_id != '6901789':
            return Chain(data).text('抱歉博士，非【小游戏专区】只能由管理员发起游戏哦~')
    else:
        if not data.is_admin:
            return Chain(data).text('抱歉博士，只能由管理员发起游戏哦~')

    level = {
        '简单': '简单',
        '困难': '困难'
    }
    level_text = '\n'.join([f'【{lv}】{ct}猜字谜' for lv, ct in level.items()])

    select_level = f'博士，请选择难度：\n\n{level_text}\n\n' \
                   '请回复【难度等级】开始游戏。\n' \
                   '所有群员均可参与游戏，游戏一旦开始，将暂停其他功能的使用哦。如果取消请无视本条消息。\n' \
                   '请回复干员名称参与作答，正确将获得积分，错误将获得提示。\n' \
                   '输入“跳过”或“下一题”将公布答案并跳过本题，输入“提示”获取提示，输入“结束”或“不玩了”提前结束游戏。\n'

    choice = await data.wait(Chain(data).text(select_level))

    if not choice:
        return None

    if choice.text not in level.keys():
        return Chain(choice).text('博士，您没有选择难度哦，游戏取消。')

    operators = None
    referee = WordleReferee()
    curr = None
    level_rate = list(level.keys()).index(choice.text) + 1

    await data.send(Chain(choice).text(f'{choice.text}难度，奖励倍数 {level_rate}'))

    while True:
        if not operators:
            operators = copy.deepcopy(ArknightsGameData().operators)

        operator = operators.pop(random.choice(list(operators.keys())))

        while operator.race == '未知' or not operator.nation or not operator.drawer:
            operator = operators.pop(random.choice(list(operators.keys())))

        if curr != referee.count:
            curr = referee.count
            text = Chain(data, at=False).text(f'题目准备中...（{referee.count + 1}/{wordle_config.questions}）')

            if referee.user_ranking:
                text.text('\n').text(calc_rank(referee)[0], auto_convert=False)

            await data.send(text)
            await asyncio.sleep(2)

        result = await wordle_start(data, operator, choice.text, level_rate, referee.count + 1)
        end = False
        skip = False

        if result.status in [WordleStatus.userClose, WordleStatus.systemClose]:
            end = True

        if result.status in [WordleStatus.userSkip, WordleStatus.systemSkip]:
            skip = True

        if result.status == WordleStatus.bingo:
            rewards = int(wordle_config.rewards.bingo * level_rate * (100 + result.total_point) / 100)
            UserInfo.add_jade_point(result.answer.user_id, rewards, game_config.jade_point_max)
            set_rank(referee, result.answer, 1)

        if result.user_point:
            for user_id, point in result.user_point.items():
                set_point(referee, user_id, point)

        if not skip:
            referee.count += 1
            if referee.count >= wordle_config.questions:
                end = True

        if end:
            break

    if referee.count < wordle_config.finish_min:
        return Chain(data, at=False).text(
            f'游戏结束，本轮共进行了{referee.count}次游戏，不进行结算，最少需要进行{wordle_config.finish_min}次。')

    rewards_rate = (100 + (referee.total_point if referee.total_point > -90 else -90)) / 100
    text, reward_list = calc_rank(referee)
    text += '\n\n'

    for r, l in reward_list.items():
        if r == 0:
            rewards = int(wordle_config.rewards.golden * level_rate * rewards_rate)
            text += f'第一名获得{rewards}合成玉；\n'

        elif r == 1:
            rewards = int(wordle_config.rewards.silver * level_rate * rewards_rate)
            text += f'第二名获得{rewards}合成玉；\n'

        else:
            rewards = int(wordle_config.rewards.copper * level_rate * rewards_rate)
            text += f'第三名获得{rewards}合成玉；\n'

    return Chain(data, at=False).text('游戏结束').text('\n').text(text, auto_convert=False)