import os
import time

from typing import Optional, Tuple
from amiyabot import Message, Chain
from amiyabot.builtin.message import MessageStructure
from amiyabot.builtin.message.waitEvent import ChannelMessagesItem
from core.database.user import UserInfo
from core.resource.arknightsGameData import ArknightsGameData, Operator

from .gameBuilder import GuessProcess

curr_dir = os.path.dirname(__file__)
max_rewards = 30000


async def guess_filter(data: Message):
    return data.text in ArknightsGameData.operators or data.text in [
        *['不玩了', '结束'],
        *['下一个', '跳过'],
        *['线索', '提示'],
    ]


async def game_begin(
    data: Message,
    event: ChannelMessagesItem,
    operator: Operator,
    prev: Operator,
    hardcode: bool,
) -> Tuple[Optional[MessageStructure], Optional[ChannelMessagesItem]]:
    async def send(content: str):
        await data.send(Chain(data, at=False, reference=True).text(content))

    process = GuessProcess(operator, prev, hardcode)

    time_rec = time.time()
    count_rec = process.count
    alert_step = 0

    while not process.bingo and process.count < process.max_count:
        ask = None
        if process.display:
            ask = Chain(data, at=False).html(f'{curr_dir}/template/hardcode.html', process.view_data)
            process.display = False

        # if event:
        #     event.close_event()

        event = await data.wait_channel(ask, force=True, clean=True, max_time=5, data_filter=guess_filter)
        if process.count != count_rec:
            time_rec = time.time()
            count_rec = process.count
            alert_step = 0

        if not event:
            # 超时没人回答，游戏结束
            over_time = time.time() - time_rec
            if over_time >= 120:
                await data.send(Chain(data, at=False).text(f'答案是{operator.name}，没有博士回答吗？那游戏结束咯~'))
                return None, event
            elif over_time >= 110 and alert_step == 2:
                alert_step = 3
                await data.send(Chain(data, at=False).text('还剩10秒...>.<'))
            elif over_time >= 90 and alert_step == 1:
                alert_step = 2
                await data.send(Chain(data, at=False).text('还剩30秒...'))
            elif over_time >= 60 and alert_step == 0:
                alert_step = 1
                await data.send(Chain(data, at=False).text('还剩60秒...'))

            continue

        data = event.message

        # 揭示一条信息
        if data.text in ['线索', '提示']:
            tips = process.get_tips()
            if tips is False:
                await send('已经没有可揭示的线索了')
                continue

            if tips is None:
                await send('不能连续揭示两个线索哦，请猜一次后继续~')
                continue

            await send(f'揭示了一个线索：【{tips.title}】{tips.value}')
            process.tips_lock = True
            process.display = True
            continue

        # 跳过
        if data.text in ['下一个', '跳过']:
            await send(f'答案是{operator.name}')
            return data, event

        # 手动结束游戏
        if data.text in ['不玩了', '结束']:
            await send(f'答案是{operator.name}，游戏结束~')
            return None, event

        # 竞猜
        answer = ArknightsGameData.operators[data.text]
        if answer.id in process.wrongs:
            await send(f'干员【{answer.name}】已经猜过啦，换一个试试吧~')
            continue

        match, unlock = process.guess(answer)
        if match == -1:
            rewards = 300 * (len(process.closed_tags) + 1)
            UserInfo.add_jade_point(data.user_id, rewards, max_rewards)
            await send(f'回答正确！奖励合成玉{rewards}')
            return data, event
        else:
            if process.count >= process.max_count:
                await data.send(Chain(data, at=False).text(f'机会耗尽，答案是{operator.name}'))
                return data, event

            text = f'匹配了{match}个线索'
            if match >= 5:
                text += '，基本可以肯定是哪位干员了'
            elif match >= 3:
                text += '，离答案非常接近了'
            elif match >= 1:
                text += '，已经有一些头绪了'
            else:
                text = '所有的线索都对不上哦'

            if unlock:
                UserInfo.add_jade_point(data.user_id, unlock * 100, max_rewards)
                await send(f'解锁了{unlock}个线索，奖励{unlock * 100}合成玉')

            await send(f'{text}，请再猜猜吧~（{process.count}/{process.max_count}）')
            process.display = True
            continue

    return data, event
