import os
import html
import time
import asyncio

from amiyabot import QQGuildBotInstance
from amiyabot.builtin.message import MessageStructure
from amiyabot.adapters.tencent.qqGroup import QQGroupBotInstance

from core.database.group import GroupSetting
from core.database.messages import *
from core.util import TimeRecorder, find_most_similar
from core import send_to_console_channel, Message, Chain, AmiyaBotPluginInstance, bot as main_bot

try:
    from core.util import attridict
except ImportError:
    from core.util import AttrDict as attridict

from .helper import WeiboUser

curr_dir = os.path.dirname(__file__)


class WeiboPluginInstance(AmiyaBotPluginInstance): ...


bot = WeiboPluginInstance(
    name='明日方舟微博推送',
    version='3.6',
    plugin_id='amiyabot-weibo',
    plugin_type='official',
    description='在明日方舟相关官微更新时自动推送到群',
    document=f'{curr_dir}/README.md',
    instruction=f'{curr_dir}/README_USE.md',
    global_config_schema=f'{curr_dir}/config_schema.json',
    global_config_default=f'{curr_dir}/config_default.yaml',
)


@table
class WeiboRecord(MessageBaseModel):
    user_id: int = IntegerField()
    blog_id: str = CharField()
    record_time: int = IntegerField()


async def send_by_index(index: int, weibo: WeiboUser, data: MessageStructure):
    result = await weibo.get_weibo_content(index - 1)

    if not result:
        return Chain(data).text('博士...暂时无法获取微博呢...请稍后再试吧~')
    else:
        chain = (
            Chain(data)
            .text(result.user_name + '\n')
            .text(html.unescape(result.html_text) + '\n')
            .image(result.pics_list)
        )

        if not isinstance(data.instance, QQGuildBotInstance):
            chain.text(f'\n\n{result.detail_url}')

        return chain


def get_index_from_text(text: str, array: list):
    r = re.search(r'(\d+)', text)
    if r:
        index = abs(int(r.group(1))) - 1
        if index >= len(array):
            index = len(array) - 1

        return index


@bot.on_message(group_id='weibo', keywords=['开启微博推送'])
async def _(data: Message):
    if isinstance(data.instance, QQGroupBotInstance):
        return Chain(data).text('抱歉博士，该功能在群聊暂不可用~')

    if not data.is_admin:
        return Chain(data).text('抱歉，微博推送只能由管理员设置')

    channel: GroupSetting = GroupSetting.get_or_none(group_id=data.channel_id, bot_id=data.instance.appid)
    if channel:
        GroupSetting.update(send_weibo=1).where(
            GroupSetting.group_id == data.channel_id,
            GroupSetting.bot_id == data.instance.appid,
        ).execute()
    else:
        if GroupSetting.get_or_none(group_id=data.channel_id):
            GroupSetting.update(bot_id=data.instance.appid, send_weibo=1).where(
                GroupSetting.group_id == data.channel_id
            ).execute()
        else:
            GroupSetting.create(group_id=data.channel_id, bot_id=data.instance.appid, send_weibo=1)

    return Chain(data).text('已在本群开启微博推送')


@bot.on_message(group_id='weibo', keywords=['关闭微博推送'])
async def _(data: Message):
    if not data.is_admin:
        return Chain(data).text('抱歉，微博推送只能由管理员设置')

    GroupSetting.update(send_weibo=0).where(
        GroupSetting.group_id == data.channel_id, GroupSetting.bot_id == data.instance.appid
    ).execute()

    return Chain(data).text('已在本群关闭微博推送')


@bot.on_message(group_id='weibo', keywords=['微博'])
async def _(data: Message):
    listens: list = bot.get_config('listen')
    setting = attridict(bot.get_config('setting'))

    weibo: Optional[WeiboUser] = None

    text = data.text.replace('微博', '').replace('最新', '')

    if text:
        name_map = {item['name']: item for item in listens}
        name = find_most_similar(text, list(name_map.keys()))
        if name:
            weibo = WeiboUser(name_map[name]['uid'], setting)

    if not weibo:
        if len(listens) == 1:
            weibo = WeiboUser(listens[0]['uid'], setting)
        else:
            md = '回复序号选择已关注的微博：\n\n|序号|微博ID|备注|\n|----|----|----|\n'
            for index, item in enumerate(listens):
                md += '|{index}|{uid}|{name}|\n'.format(index=index + 1, **item)

            wait = await data.wait(Chain(data).markdown(md))
            if not wait:
                return None

            index = get_index_from_text(wait.text_digits, listens)
            if index is None:
                return None

            weibo = WeiboUser(listens[index]['uid'], setting)

    message = data.text_digits
    index = 0

    r = re.search(r'(\d+)', message)
    if r:
        index = abs(int(r.group(1)))

    if '最新' in message:
        index = 1

    if index:
        return await send_by_index(index, weibo, data)
    else:
        blog_list = await weibo.get_blog_list()
        user_name = await weibo.get_user_name()

        if not blog_list:
            return Chain(data).text('博士...暂时无法获取微博列表呢...请稍后再试吧~')

        md = f'博士，这是【{user_name}】的微博列表，回复【序号】来获取详情吧\n\n|序号|日期|内容|\n|----|----|----|\n'
        for item in blog_list:
            md += '|{index}|{date}|{content}|\n'.format(**item)

        reply = Chain(data).markdown(md)

        wait = await data.wait(reply)
        if wait:
            r = re.search(r'(\d+)', wait.text_digits)
            if r:
                index = abs(int(r.group(1)))
                return await send_by_index(index, weibo, wait)


@bot.timed_task(each=30)
async def _(_):
    listens: list = bot.get_config('listen')
    for listen in listens:
        user = listen['uid']
        weibo = WeiboUser(user, attridict(bot.get_config('setting')))
        new_id = await weibo.get_weibo_id(0)
        if not new_id:
            continue

        record = WeiboRecord.get_or_none(blog_id=new_id)
        if record:
            continue

        WeiboRecord.create(user_id=user, blog_id=new_id, record_time=int(time.time()))

        target: List[GroupSetting] = GroupSetting.select().where(GroupSetting.send_weibo == 1)

        if not target:
            continue

        time_rec = TimeRecorder()
        async_send_tasks = []

        result = await weibo.get_weibo_content(0)

        if not result:
            await send_to_console_channel(Chain().text(f'微博获取失败\nUSER: {user}\nID: {new_id}'))
            return

        send = True
        for regex in bot.get_config("block"):
            if re.match(regex, html.unescape(result.html_text)):
                await send_to_console_channel(
                    Chain().text(f'微博正文触发正则屏蔽，跳过推送\nUSER: {user}\nID: {new_id}')
                )
                send = False
                break
            if re.search(regex, html.unescape(result.html_text)):
                await send_to_console_channel(
                    Chain().text(f'微博正文触发搜索屏蔽，跳过推送\nUSER: {user}\nID: {new_id}')
                )
                send = False
                break

        if not send:
            continue

        await send_to_console_channel(
            Chain().text(f'开始推送微博\nUSER: {result.user_name}\nID: {new_id}\n目标数: {len(target)}')
        )

        for item in target:
            data = Chain()

            instance = main_bot[item.bot_id]

            if not instance:
                continue

            data.text(f'来自 {result.user_name} 的最新微博\n\n{html.unescape(result.html_text)}')

            if isinstance(instance.instance, QQGuildBotInstance):
                if not instance.instance.private:
                    for url in result.pics_urls:
                        data.image(url=url)
                else:
                    data.image(result.pics_list)
            else:
                data.image(result.pics_list).text(f'\n\n{result.detail_url}')

            if bot.get_config('sendAsync'):
                async_send_tasks.append(instance.send_message(data, channel_id=item.group_id))
            else:
                await instance.send_message(data, channel_id=item.group_id)
                await asyncio.sleep(bot.get_config('sendInterval'))

        if async_send_tasks:
            await asyncio.wait(async_send_tasks)

        await send_to_console_channel(Chain().text(f'微博推送结束:\n{new_id}\n耗时{time_rec.total()}'))
