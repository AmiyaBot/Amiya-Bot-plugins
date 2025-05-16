from core import AmiyaBotPluginInstance, Requirement
from core.util import TimeRecorder
from core.database.user import UserInfo

from .guessStart import *

bot = AmiyaBotPluginInstance(
    name='兔兔猜干员',
    version='3.4',
    plugin_id='amiyabot-game-guess',
    plugin_type='official',
    description='干员竞猜小游戏，可获得合成玉',
    document=f'{curr_dir}/README.md',
    global_config_schema=f'{curr_dir}/config_schema.json',
    global_config_default=f'{curr_dir}/config_default.yaml',
    requirements=[Requirement('amiyabot-arknights-gamedata', official=True)],
)


def get_markdown_template_id(data: Message):
    markdown_template_id: list = bot.get_config('markdown_template_id')
    for item in markdown_template_id:
        if item['bot_id'] == data.instance.appid:
            return item['template_id']
    return ''


@bot.on_message(keywords=['猜干员'])
async def _(data: Message):
    level = {
        '初级': '立绘',
        '中级': '技能',
        '高级': '语音',
        '资深': '档案',
    }
    level_text = '\n'.join([f'【{lv}】{ct}猜干员' for lv, ct in level.items()])
    select_level = f'博士，请选择难度：\n\n{level_text}\n\n请回复【难度等级】开始游戏。\n所有群员均可参与竞猜，游戏一旦开始，将暂停其他功能的使用哦。如果取消请无视本条消息。\n详细说明请查看功能菜单'

    choice_chain = Chain(data).text(select_level)
    markdown_template_id = get_markdown_template_id(data)

    if can_send_buttons(data, markdown_template_id):
        keyboard = InlineKeyboard(int(data.instance.appid))

        row = keyboard.add_row()
        row.add_button('1', '初级🌱', action_data='初级', action_enter=True)
        row.add_button('2', '中级🌟', action_data='中级', action_enter=True)

        row2 = keyboard.add_row()
        row2.add_button('3', '高级🏆', action_data='高级', action_enter=True)
        row2.add_button('4', '资深👑', action_data='资深', action_enter=True)

        choice_chain = Chain(data).markdown_template(
            markdown_template_id,
            [
                {'key': 'content', 'values': [select_level]},
            ],
            keyboard=keyboard,
        )
    event = await data.wait_channel(choice_chain, force=True)
    if not event:
        return None

    choice = event.message
    choice_level = any_match(choice.text, list(level.keys()))

    if not choice_level:
        event.close_event()
        return Chain(choice).text('博士，您没有选择难度哦，游戏取消。')

    operators = {}
    referee = GuessReferee(markdown_template_id=markdown_template_id)
    curr = None
    level_rate = list(level.keys()).index(choice_level) + 1

    await choice.send(Chain(choice).text(f'{choice_level}难度，难度结算倍率 {level_rate}'))

    target = choice
    time_rec = TimeRecorder()

    while True:
        if not operators:
            operators = copy.deepcopy(ArknightsGameData.operators)

        operator = operators.pop(random.choice(list(operators.keys())))

        if '预备干员' in operator.name:
            continue

        if curr != referee.round:
            curr = referee.round

            text = Chain(target, at=False).text(f'题目准备中...（{referee.round + 1}/{guess_config.questions}）')
            if referee.user_ranking:
                text.text('\n').text(referee.calc_rank()[0], auto_convert=False)

            await target.send(text)

        result, event = await guess_start(
            referee,
            target,
            event,
            operator,
            level[choice_level],
            choice_level,
            level_rate,
        )
        end = False
        skip = False

        target = result.answer

        if result.state in [GameState.userClose, GameState.systemClose]:
            end = True
        if result.state in [GameState.userSkip, GameState.systemSkip]:
            skip = True
        if result.state == GameState.bingo:
            UserInfo.add_jade_point(result.answer.user_id, result.rewards, game_config.jade_point_max)
            await referee.set_rank(result.answer, result.point)

        if result.user_rate:
            for user_id, rate in result.user_rate.items():
                referee.set_rate(user_id, rate)

        if not skip:
            referee.round += 1
            if referee.round >= guess_config.questions:
                end = True

        if end:
            break

    if event:
        event.close_event()

    if referee.round < guess_config.finish_min:
        if result.event:
            result.event.close_event()
        return Chain(target, at=False).text(f'游戏结束，本轮共进行了{referee.round}次竞猜，不进行结算')

    finish_rate = round(referee.round / guess_config.questions, 2)
    rewards_rate = (100 + (referee.total_rate if referee.total_rate > -50 else -50)) / 100
    text, reward_list = referee.calc_rank()

    text += (
        f'\n通关速度：{time_rec.total()}\n难度倍率：{level_rate}\n进度倍率：{finish_rate}\n结算倍率：{rewards_rate}\n\n'
    )

    for r, l in reward_list.items():
        if r == 0:
            bonus = guess_config.rewards.golden
            text += '🏅 第一名'
        elif r == 1:
            bonus = guess_config.rewards.silver
            text += '🥈 第二名'
        else:
            bonus = guess_config.rewards.copper
            text += '🥉 第三名'

        rewards = int(bonus * level_rate * finish_rate * rewards_rate)
        text += f'获得{rewards}合成玉\n'

        for uid in l:
            UserInfo.add_jade_point(uid, rewards, game_config.jade_point_max)

    if result.event:
        result.event.close_event()
    return Chain(target, at=False).text('游戏结束').text('\n').text(text, auto_convert=False)
