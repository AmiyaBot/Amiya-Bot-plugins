import os
import time

from amiyabot import PluginInstance, Message, Chain, Equal

from core.util import TimeRecorder, any_match
from core.database.bot import FunctionUsed, DisabledFunction
from core.database.group import GroupActive, check_group_active

curr_dir = os.path.dirname(__file__)
bot = PluginInstance(
    name='管理员模块',
    version='1.3',
    plugin_id='amiyabot-admin',
    plugin_type='official',
    description='可使用 BOT 的开关功能',
    document=f'{curr_dir}/README.md'
)


@bot.message_before_handle
async def _(data: Message, factory_name: str, _):
    disabled = DisabledFunction.get_or_none(
        function_id=factory_name,
        channel_id=data.channel_id
    )
    if disabled:
        return False

    if not check_group_active(data.channel_id):
        return data.is_admin and bool(any_match(data.text, ['工作', '上班']))

    return True


@bot.message_after_handle
async def _(data: Chain, factory_name: str, _):
    _, is_created = FunctionUsed.get_or_create(function_id=factory_name)
    if not is_created:
        FunctionUsed.update(use_num=FunctionUsed.use_num + 1).where(FunctionUsed.function_id == factory_name).execute()


@bot.on_message(keywords=['工作', '上班'])
async def _(data: Message):
    if not data.is_admin:
        return None

    group_active: GroupActive = GroupActive.get_or_create(group_id=data.channel_id)[0]

    if group_active.active == 0:
        seconds = int(time.time()) - int(group_active.sleep_time)
        total = TimeRecorder.calc_time_total(seconds)
        text = '打卡上班啦~阿米娅%s休息了%s……' % ('才' if seconds < 600 else '一共', total)
        if seconds < 21600:
            text += '\n博士真是太过分了！哼~ >.<'
        else:
            text += '\n充足的休息才能更好的工作，博士，不要忘记休息哦 ^_^'

        GroupActive.update(active=1, sleep_time=0).where(GroupActive.group_id == data.channel_id).execute()
        return Chain(data).text(text)
    else:
        return Chain(data).text('阿米娅没有偷懒哦博士，请您也不要偷懒~')


@bot.on_message(keywords=['休息', '下班'])
async def _(data: Message):
    if not data.is_admin:
        return None

    group_active: GroupActive = GroupActive.get_or_create(group_id=data.channel_id)[0]

    if group_active.active == 1:
        GroupActive.update(active=0,
                           sleep_time=int(time.time())).where(GroupActive.group_id == data.channel_id).execute()

        return Chain(data).text('打卡下班啦！博士需要的时候再让阿米娅工作吧。^_^')
    else:
        seconds = int(time.time()) - int(group_active.sleep_time)
        total = TimeRecorder.calc_time_total(seconds)
        if 60 < seconds < 21600:
            return Chain(data, at=False).text('（阿米娅似乎已经睡着了...）')
        else:
            if seconds < 60:
                return Chain(data).text('阿米娅已经下班啦，博士需要的时候请让阿米娅工作吧^_^')
            else:
                return Chain(data).text(f'阿米娅已经休息了{total}啦，博士需要的时候请让阿米娅工作吧\n^_^')


@bot.on_message(keywords=Equal('频道信息'))
async def _(data: Message):
    return Chain(data, at=False).text(
        f'用户ID：{data.user_id}\n'
        f'频道ID：{data.guild_id}\n'
        f'子频道ID：{data.channel_id}'
    )
