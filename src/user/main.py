import random

from amiyabot.adapters.mirai import MiraiBotInstance
from amiyabot.adapters.cqhttp import CQHttpBotInstance

from core import Event
from core.util import any_match
from core.database.user import *

from .mainBot import *


@table
class PokeLock(UserBaseModel):
    group_id: str = CharField()


@bot.on_message(group_id='user', verify=only_name)
async def echo(data: Message = None):
    actions = [
        lambda dt: Chain(dt).text(random.choice(talking.touch)),
        lambda dt: Chain(dt, at=False).image(random.choice(get_face())),
    ]

    return random.choice(actions)(data)


@bot.on_message(group_id='user', verify=compose_talk_verify(talking.talk.positive, talking.call.positive))
async def _(data: Message):
    user: UserInfo = UserInfo.get_user(data.user_id)
    reply = Chain(data)

    if user.user_mood == 0:
        text = '阿米娅这次就原谅博士吧，博士要好好对阿米娅哦[face:21]'
    else:
        text = random.choice(talking.touch)

    setattr(reply, 'feeling', 5)
    return reply.text(text, auto_convert=False)


@bot.on_message(group_id='user', verify=compose_talk_verify(talking.talk.inactive, talking.call.positive))
async def _(data: Message):
    user: UserInfo = UserInfo.get_user(data.user_id)
    reply = Chain(data)
    setattr(reply, 'feeling', -5)

    if user.user_mood - 5 <= 0:
        return reply.text('(阿米娅没有应答...似乎已经生气了...)')

    anger = int((1 - (user.user_mood - 5 if user.user_mood - 5 >= 0 else 0) / 15) * 100)

    return reply.text(f'博士为什么要说这种话，阿米娅要生气了！[face:67]（怒气值：{anger}%）')


@bot.on_message(group_id='user', keywords=list(talking.call.inactive), check_prefix=False)
async def _(data: Message):
    bad_word = any_match(data.text, list(talking.call.inactive))
    text = f'哼！Dr. {data.nickname}不许叫人家{bad_word}，不然人家要生气了！'

    reply = Chain(data).text(text)
    setattr(reply, 'feeling', -5)

    return reply


@bot.on_message(group_id='user', keywords=['早上好', '早安', '中午好', '午安', '下午好', '晚上好'])
async def _(data: Message):
    hour = talk_time()
    text = ''
    if hour:
        text += f'Dr. {data.nickname}，{hour}好～'
    else:
        text += f'Dr. {data.nickname}，这么晚还不睡吗？要注意休息哦～'

    status = sign_in(data)
    if status['status']:
        text += status['text']

    return Chain(data).text(text)


@bot.on_message(group_id='user', keywords=['晚安'])
async def _(data: Message):
    return Chain(data).text(f'Dr. {data.nickname}，晚安～')


@bot.on_message(group_id='user', keywords=['我错了', '对不起', '抱歉'])
async def _(data: Message):
    info: UserInfo = UserInfo.get_user(data.user_id)

    reply = Chain(data)
    setattr(reply, 'feeling', 5)
    setattr(reply, 'unlock', True)

    if not info or info.user_mood >= 15:
        return reply.text('博士为什么要这么说呢，嗯……博士是不是偷偷做了对不起阿米娅的事[face:181]')
    else:
        return reply.text('好吧，阿米娅就当博士刚刚是在开玩笑吧，博士要好好对阿米娅哦[face:21]')


@bot.on_message(group_id='user', keywords=['签到'])
async def _(data: Message):
    status = sign_in(data, 1)

    reply = await user_info(data)

    return reply.text(status['text'])


@bot.on_message(group_id='user', keywords=['信赖', '关系', '好感', '我的信息', '个人信息'])
async def _(data: Message):
    return await user_info(data)


@bot.on_message(group_id='user', keywords=['开启戳一戳', '关闭戳一戳'])
async def _(data: Message):
    if '开启' in data.text:
        PokeLock.delete().where(PokeLock.group_id == data.channel_id).execute()
        return '已开启戳一戳'
    else:
        PokeLock.create(group_id=data.channel_id)
        return '已关闭戳一戳'


@bot.on_event('NudgeEvent')
async def _(event: Event, instance: MiraiBotInstance):
    if str(event.data['target']) == instance.appid and PokeLock.get_or_none(group_id=event.data['target']):
        if random.randint(0, 10) >= 6:
            await instance.api.send_nudge(event.data['fromId'], event.data['subject']['id'])
        else:
            await instance.send_message(await echo(), event.data['fromId'], event.data['subject']['id'])


@bot.on_event('notice.notify.poke')
async def _(event: Event, instance: CQHttpBotInstance):
    if str(event.data['target_id']) == instance.appid and PokeLock.get_or_none(group_id=event.data['target_id']):
        if random.randint(0, 10) >= 6:
            await instance.api.send_nudge(event.data['user_id'], event.data['group_id'])
        else:
            await instance.send_message(await echo(), event.data['user_id'], event.data['group_id'])


@bot.message_before_handle
async def _(data: Message, factory_name: str, _):
    user: UserInfo = UserInfo.get_user(data.user_id)

    if user.user_id.black == 1:
        return False

    if user.user_mood <= 0 and not any_match(data.text, ['我错了', '对不起', '抱歉']):
        await data.send(Chain(data).text('哼~阿米娅生气了！不理博士！[face:38]'))
        return False

    return True


@bot.message_after_send
async def _(data: Chain, factory_name: str, _):
    if not data.data:
        return

    user_id = data.data.user_id

    if not User.get_or_none(user_id=user_id):
        return None

    user: UserInfo = UserInfo.get_user(user_id)

    feeling = 2
    if hasattr(data, 'feeling'):
        feeling = getattr(data, 'feeling')

    if user.user_mood <= 0 and not hasattr(data, 'unlock'):
        feeling = 0

    user_mood = user.user_mood + feeling
    if user_mood <= 0:
        user_mood = 0
    if user_mood >= 15:
        user_mood = 15

    User.update(nickname=data.data.nickname, message_num=User.message_num + 1).where(User.user_id == user_id).execute()

    UserInfo.update(
        user_mood=user_mood,
        user_feeling=UserInfo.user_feeling + feeling,
    ).where(UserInfo.user_id == user_id).execute()
