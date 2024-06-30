import os
import copy
import time
import random

from typing import Optional
from amiyabot import InlineKeyboard
from amiyabot.adapters.tencent.qqGroup import QQGroupBotInstance
from amiyabot.adapters.tencent.qqGlobal import QQGlobalBotInstance
from core.util import any_match, random_pop, read_yaml
from core.resource.arknightsGameData import ArknightsGameData, ArknightsGameDataResource, Operator

from .guessTools import ImageCropper
from .guessBuilder import *

curr_dir = os.path.dirname(__file__)

game_config = read_yaml(f'{curr_dir}/guess.yaml')
guess_config = game_config.guess
guess_keyword = game_config.keyword


def can_send_buttons(data: Message, markdown_template_id: str):
    return (
        isinstance(data.instance, QQGroupBotInstance) or isinstance(data.instance, QQGlobalBotInstance)
    ) and markdown_template_id


async def guess_filter(data: Message):
    return data.text in ArknightsGameData.operators or data.text in [
        *guess_keyword.skip,
        *guess_keyword.tips,
        *guess_keyword.over,
    ]


async def guess_start(
    referee: GuessReferee,
    data: Message,
    operator: Operator,
    title: str,
    level: str,
    level_rate: int,
):
    ask = Chain(data, at=False)
    cropper: Optional[ImageCropper] = None

    if referee.round == 0:
        ask.text(f'博士，这是哪位干员的{title}呢，请发送干员名猜一猜吧！').text('\n')

    if level == '初级':
        skins = operator.skins()
        if not skins:
            return GuessResult(answer=data, state=GameState.systemSkip)

        skin = random.choice(skins)
        skin_path = await ArknightsGameDataResource.get_skin_file(skin)

        if not skin_path:
            return GuessResult(answer=data, state=GameState.systemSkip)
        else:
            cropper = ImageCropper(skin_path)
            ask.image(cropper.crop())

    if level == '中级':
        skills = operator.skills()[0]

        if not skills:
            return GuessResult(answer=data)

        skill = random.choice(skills)

        if any_match(skill['skill_name'], ['α', 'β', 'γ', '急救']):
            return GuessResult(answer=data)

        skill_icon = 'resource/gamedata/skill/%s.png' % skill['skill_icon']

        if not os.path.exists(skill_icon):
            return GuessResult(answer=data)

        ask.image(skill_icon)

    if level == '高级':
        voices = operator.voices()
        if not voices:
            return GuessResult(answer=data)

        voice_type = random.choice(list(operator.cv.keys()))
        type_v = ''
        type_d = {
            '中文-普通话': '_cn',
            '中文-方言': '_custom',
            '意大利语': '_ita',
            '英语': '_en',
            '韩语': '_kr',
            '俄语': '_custom',
            '德语': '_custom',
            '日语': '',
            '联动': '',
        }
        if voice_type in type_d:
            type_v = type_d[voice_type]

        voices = [n for n in voices if n['voice_title'] not in ['标题', '戳一下']]
        voice = random.choice(voices)
        voice_path = await ArknightsGameDataResource.get_voice_file(operator, voice['voice_title'], type_v)

        ask.text(f'{voice_type}语音：').text(voice['voice_text'].replace(operator.name, 'XXX'))

        if not voice_path:
            ask.text('\n\n语音文件下载失败')
        else:
            ask.voice(voice_path)

    if level == '资深':
        stories = operator.stories()
        if not stories:
            return GuessResult(answer=data)

        stories = [
            n
            for n in stories
            if n['story_title'] not in ['基础档案', '综合体检测试', '综合性能检测结果', '临床诊断分析']
        ]
        story = random.choice(stories)['story_text'].replace(operator.name, 'XXX')
        section = story.split('。')

        if len(section) >= 5:
            start = random.randint(0, len(section) - 5)
            story = '。'.join(section[start : start + 5])

        ask.text(story, auto_convert=False)

    tips = [f'TA的职业是{operator.classes}，分支职业是{operator.classes_sub}']

    for t, v in {'队伍': operator.team, '阵营': operator.group, '势力': operator.nation}.items():
        if v != '未知':
            tips.append(f'TA的所属{t}是{v}')

    if operator.sex != '未知':
        tips.append(f'TA是{operator.rarity}星{operator.sex}性干员')
    else:
        tips.append(f'TA是{operator.rarity}星干员')

    if len(operator.name) > 1:
        tips.append(f'TA的代号里有一个字是【{random.choice(operator.name)}】')

    if operator.limit:
        tips.append('TA是限定干员')

    result = GuessResult(answer=data)
    count = 0
    max_count = 10
    final_tips = False

    time_rec = time.time()
    alert_step = 0

    if can_send_buttons(data, referee.markdown_template_id):
        keyboard = InlineKeyboard(int(data.instance.appid))

        row = keyboard.add_row()
        row.add_button('1', '下一题➡️', action_data='下一题', action_enter=True)
        row.add_button('2', '提示💡', action_data='提示', action_enter=True)

        row2 = keyboard.add_row()
        row2.add_button('3', '结束🚫', action_data='结束')

        ask.markdown_template(
            referee.markdown_template_id,
            [
                {'key': 'content', 'values': ['点击按钮获取帮助']},
            ],
            keyboard=keyboard,
        )

    def refresh_time():
        nonlocal time_rec, alert_step
        time_rec = time.time()
        alert_step = 0

    # 开始竞猜
    while True:
        event = await data.wait_channel(ask, force=True, clean=bool(ask), max_time=5, data_filter=guess_filter)

        ask = None
        result.event = event

        # 超时没人回答，游戏结束
        if not event:
            over_time = time.time() - time_rec
            if over_time >= 60:
                await data.send(Chain(data, at=False).text(f'答案是{operator.name}，没有博士回答吗？那游戏结束咯~'))
                result.state = GameState.systemClose
                return result
            elif over_time >= 50 and alert_step == 1:
                alert_step = 2
                await data.send(Chain(data, at=False).text('还剩10秒...>.<'))
            elif over_time >= 30 and alert_step == 0:
                alert_step = 1
                await data.send(Chain(data, at=False).text('还剩30秒...'))
            continue

        result.answer = answer = event.message

        # 跳过问题
        if answer.text in guess_keyword.skip:
            await data.send(Chain(answer, at=False, reference=True).text(f'答案是{operator.name}，结算奖励-5%'))
            result.set_rate(answer.user_id, -5)
            result.state = GameState.userSkip
            return result

        # 获取提示
        if answer.text in guess_keyword.tips:
            reply = Chain(answer, at=False, reference=True)
            text = f'{answer.nickname} 使用了提示，结算奖励-2%'

            if level == '初级':
                res = cropper.expand(int(cropper.image.size[0] * 0.2))
                if res:
                    await data.send(reply.text(text))
                    await data.send(
                        Chain(answer, at=False).text('图片再放大一点了哦~').image(cropper.crop(check_transparent=False))
                    )
                    result.set_rate(answer.user_id, -2)
                else:
                    await data.send(reply.text('不能继续放大了 >.<'))
            else:
                if tips or not final_tips:
                    if tips:
                        reply.text(text).text('\n').text(random_pop(tips))
                        if not tips:
                            reply.text('\n提示用完啦！请注意，下一次就是终极提示了，博士，请加油哦！')

                        await data.send(reply)
                        result.set_rate(answer.user_id, -2)
                    else:
                        reply.text(f'{answer.nickname} 使用了终极提示，结算奖励-10% >.<')

                        operators = copy.deepcopy(list(ArknightsGameData.operators.keys()))
                        operators.remove(operator.name)

                        tips_opts = [*[random_pop(operators) for _ in range(3)], operator.name]
                        random.shuffle(tips_opts)

                        if can_send_buttons(data, referee.markdown_template_id):
                            keyboard = InlineKeyboard(int(data.instance.appid))

                            row = keyboard.add_row()
                            row.add_button('1', tips_opts[0], action_enter=True, action_click_limit=1)
                            row.add_button('2', tips_opts[1], action_enter=True, action_click_limit=1)

                            row2 = keyboard.add_row()
                            row2.add_button('3', tips_opts[2], action_enter=True, action_click_limit=1)
                            row2.add_button('4', tips_opts[3], action_enter=True, action_click_limit=1)

                            reply.markdown_template(
                                referee.markdown_template_id,
                                [
                                    {'key': 'content', 'values': ['TA是以下干员的其中一位（点击按钮选择干员）']},
                                ],
                                keyboard=keyboard,
                            )
                        else:
                            reply.text('\n').text('TA是以下干员的其中一位：\n' + '、'.join(tips_opts))

                        await data.send(reply)
                        result.set_rate(answer.user_id, -10)

                        final_tips = True
                else:
                    await data.send(reply.text('没有更多提示了 >.<'))

            refresh_time()
            continue

        # 手动结束游戏
        if answer.text in guess_keyword.over:
            await data.send(Chain(answer, at=False, reference=True).text(f'答案是{operator.name}，游戏结束~'))
            result.state = GameState.userClose
            return result

        # 回答问题
        if answer.text == operator.name:
            # 回答正确
            rewards = int(guess_config.rewards.bingo * level_rate * (100 + result.total_rate) / 100)
            point = 1

            combo_text = ''

            if referee.combo_user != answer.user_id:
                if referee.combo_count >= 3:
                    # 终结连击，+ 1 分
                    point += 1
                    combo_text = '终结连击！'

                # 开始记录连击
                referee.combo_user = answer.user_id
                referee.combo_count = 1
            else:
                # 连击 + 1
                referee.combo_count += 1
                if referee.combo_count > referee.user_ranking[answer.user_id].max_combo:
                    referee.user_ranking[answer.user_id].max_combo = referee.combo_count

            # 3 连击以上，每 3 个连击数 + 1 分、合成玉 + 10%
            if referee.combo_count > 1:
                point += int(referee.combo_count / 3)
                rewards = int(rewards * (1 + int(referee.combo_count / 3) * 0.1))

                combo_text = f'{referee.combo_count}连击！'

            reply = Chain(answer, at=False, reference=True).text(
                f'回答正确！{combo_text}分数+{point}，合成玉+{rewards}'
            )
            await data.send(reply)

            result.point = point
            result.answer = answer
            result.state = GameState.bingo
            result.rewards = rewards
            return result
        else:
            reply = Chain(answer, at=False, reference=True)
            reduce = 1

            # 连击中断
            if referee.combo_user == answer.user_id:
                if referee.combo_count:
                    reduce = referee.combo_count
                    if reduce > 1:
                        reply.text('连击中断！')
                referee.combo_count = 0

            # 答错扣分
            # referee.set_rank(answer, -reduce)

            count += 1
            if count >= max_count:
                await data.send(reply.text(f'机会耗尽，答案是{operator.name}，结算奖励-5%'))
                result.set_rate('0', -5)
                return result
            else:
                await data.send(reply.text(f'答案不正确。请再猜猜吧~（{count}/{max_count}）'))

        refresh_time()
