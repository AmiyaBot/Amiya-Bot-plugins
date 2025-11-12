import time
import asyncio
import re
import json
from typing import Optional
from pathlib import Path

from amiyabot import QQGuildBotInstance
from amiyabot.factory import BotHandlerFactory
from amiyabot.adapters.tencent.qqGroup import QQGroupBotInstance
from amiyabot.network.download import download_async

from core.database.group import GroupSetting
from core.database.messages import *

from core.util import TimeRecorder, find_most_similar
from core import (
    send_to_console_channel,
    Message,
    Chain,
    AmiyaBotPluginInstance,
    bot as main_bot,
)

try:
    from core.util import attridict
except ImportError:
    from core.util import AttrDict as attridict

from .helper import WeiboWebSocketManager

curr_dir = Path(__file__).parent


class WeiboPluginInstance(AmiyaBotPluginInstance): ...


bot = WeiboPluginInstance(
    name='明日方舟微博推送',
    version='3.7',
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
    user_id: str = CharField()
    blog_id: str = CharField()
    record_time: int = IntegerField()
    user_name: str = CharField(null=True)
    content: str = TextField(null=True)
    images: str = TextField(null=True)  # JSON格式存储图片URL列表
    detail_url: str = CharField(null=True)
    created_at: str = CharField(null=True)

    @staticmethod
    def get_weibo_list(user_id: str, limit: Optional[int] = 10):
        query = (
            WeiboRecord.select()
            .where(WeiboRecord.user_id == user_id)
            .order_by(WeiboRecord.record_time.desc())
        )
        if limit:
            query = query.limit(limit)
        return list(query)  # 转换为列表


# 全局WebSocket管理器
ws_manager = WeiboWebSocketManager(config_provider=bot)


@ws_manager.register_message_handler("historical_weibos")
async def handle_weibo(data: dict):
    """处理订阅建立后返回的微博列表"""
    if not data:
        return

    recent_weibos: dict = data.get('recent_weibos') or {}
    if not recent_weibos:
        return

    # 查询开启微博推送的群（后面可能需要推送新增的历史微博）
    target_groups: List[GroupSetting] = list(
        GroupSetting.select().where(GroupSetting.send_weibo == 1)
    )

    setting = attridict(bot.get_config('setting'))
    push_async = bot.get_config('sendAsync')
    send_interval = bot.get_config('sendInterval')
    block_rules = bot.get_config('block') or []

    inserted_records = []  # 保存本次新增的微博（结构：dict）
    for uid, items in recent_weibos.items():
        if not items:
            continue
        for wb in items:
            blog_id = wb.get('id') or wb.get('bid')
            if not blog_id:
                continue
            if WeiboRecord.get_or_none(blog_id=blog_id):
                continue  # 已存在，跳过

            pics_files = []
            for p in wb.get('pics', []) or []:
                file = p.get('file')
                if file:
                    suffix = file.split('.')[-1]
                    if (
                        setting.get('sendGIF', False) is False
                        and suffix.lower() == 'gif'
                    ):
                        continue
                    try:
                        pic_index = p.get('index', '')
                        cdn_url = f"https://cdn.amiyabot.com/api/v1/weibo/pic/{pic_index}/{file}"

                        # 创建cache目录（使用运行路径）
                        cache_dir = Path.cwd() / setting.get(
                            'imagesCache', 'logs/weibo'
                        )
                        cache_dir.mkdir(parents=True, exist_ok=True)

                        # 判断文件是否已经存在
                        local_file_path = cache_dir / file
                        if local_file_path.exists():
                            pics_files.append(str(local_file_path))
                            continue
                        # 下载文件
                        file_content = await download_async(cdn_url)
                        if file_content:
                            # 保存文件到cache目录
                            local_file_path.write_bytes(file_content)
                            pics_files.append(str(local_file_path))
                    except Exception as _:
                        continue

            images_json = json.dumps(pics_files) if pics_files else ''

            record = WeiboRecord.create(
                user_id=uid,
                blog_id=blog_id,
                record_time=int(time.time()),
                user_name=wb.get('screen_name', ''),
                content=wb.get('text', ''),
                images=images_json,
                detail_url=f"https://weibo.com/{uid}/{blog_id}",
                created_at=wb.get('created_at', ''),
            )
            inserted_records.append((uid, wb, record))

    if not inserted_records:
        return

    if not target_groups:
        return  # 没有需要推送的群

    # 推送新增的历史微博（简单文本+详情+图片文件名列表）
    async_tasks = []
    time_rec = TimeRecorder()

    for uid, wb, record in inserted_records:
        # 屏蔽规则匹配正文
        skip = False
        text_content = wb.get('text', '')
        for regex in block_rules:
            try:
                if re.match(regex, text_content) or re.search(regex, text_content):
                    skip = True
                    break
            except re.error:
                continue
        if skip:
            await send_to_console_channel(
                Chain().text(f"微博触发屏蔽规则，跳过推送: {record.blog_id}")
            )
            continue

        # 构建消息内容（按需求格式）
        header = f"来自 {wb.get('screen_name','')} 的最新微博\n\n{text_content}"
        images = json.loads(record.images) if record.images else []
        url = record.detail_url

        await send_to_console_channel(
            Chain().text(
                f"开始推送微博\nUSER: {record.user_name}\nID: {record.blog_id}\n目标数: {len(target_groups)}"
            )
        )
        for group in target_groups:
            bot_instance = main_bot[group.bot_id]
            if not bot_instance:
                continue
            chain = Chain().text(header)

            if isinstance(bot_instance.instance, QQGuildBotInstance):
                chain.image(images)
            else:
                chain.image(images).text(f'\n\n{url}')

            if push_async:
                async_tasks.append(
                    bot_instance.send_message(chain, channel_id=group.group_id)
                )
            else:
                await bot_instance.send_message(chain, channel_id=group.group_id)
                await asyncio.sleep(send_interval)

    if async_tasks:
        await asyncio.wait(async_tasks)

    await send_to_console_channel(
        Chain().text(
            f"微博推送完成：{len(inserted_records)} 条 耗时 {time_rec.total()}"
        )
    )


async def send_by_index(index: int, weibo: str, data: Message, blog_list=None):
    """发送指定序号的历史微博"""
    try:
        if blog_list is None:
            blog_list = WeiboRecord.get_weibo_list(weibo, limit=10)

        if not blog_list:
            return Chain(data).text('博士...暂时没有找到历史微博呢...')

        # 验证索引
        if index < 1:
            index = 1
        elif index > len(blog_list):
            index = len(blog_list)

        # 获取指定序号的微博
        target_blog = blog_list[index - 1]
        blog_id = target_blog.blog_id  # 使用属性访问而不是字典访问

        # 从数据库获取微博内容
        result = WeiboRecord.get_or_none(blog_id=blog_id)

        if not result:
            return Chain(data).text('博士...暂时无法获取这条微博的内容呢...')

        # 构建回复
        chain = (
            Chain(data)
            .text(result.user_name + '\n')
            .text(result.content + '\n')
            .image(json.loads(result.images) if result.images else [])
        )

        if not isinstance(data.instance, QQGuildBotInstance):
            chain.text(f'\n\n{result.detail_url}')

        return chain

    except Exception as e:
        print(f"获取历史微博失败: {e}")
        return Chain(data).text('博士...获取历史微博时出错了，请稍后再试吧~')


@bot.on_message(group_id='weibo', keywords=['开启微博推送'])
async def _(data: Message):
    if isinstance(data.instance, QQGroupBotInstance):
        return Chain(data).text('抱歉博士，该功能在群聊暂不可用~')

    if not data.is_admin:
        return Chain(data).text('抱歉，微博推送只能由管理员设置')

    channel: GroupSetting = GroupSetting.get_or_none(
        group_id=data.channel_id, bot_id=data.instance.appid
    )
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
            GroupSetting.create(
                group_id=data.channel_id, bot_id=data.instance.appid, send_weibo=1
            )

    return Chain(data).text('已在本群开启微博推送')


@bot.on_message(group_id='weibo', keywords=['关闭微博推送'])
async def _(data: Message):
    if not data.is_admin:
        return Chain(data).text('抱歉，微博推送只能由管理员设置')

    GroupSetting.update(send_weibo=0).where(
        GroupSetting.group_id == data.channel_id,
        GroupSetting.bot_id == data.instance.appid,
    ).execute()

    return Chain(data).text('已在本群关闭微博推送')


@bot.on_message(group_id='weibo', keywords=['微博'])
async def _(data: Message):
    listens: list = bot.get_config('listen')
    text = data.text.replace('微博', '').replace('最新', '')
    for prefix in data.instance.bot.prefix_keywords:
        text = text.replace(prefix, '').strip()

    weibo = None
    # 如果指定了具体用户名
    if text:
        name_map = {item['name']: item for item in listens}
        name = find_most_similar(text, list(name_map.keys()))
        if name:
            weibo = name_map[name]['uid']

    # 如果只有一个用户，直接使用
    if not weibo:
        if len(listens) == 1:
            weibo = listens[0]['uid']
        else:
            # 多个用户时，让用户选择
            md = '回复序号选择已订阅的微博用户：\n\n|序号|微博ID|备注|\n|----|----|----|\n'
            for index, item in enumerate(listens):
                md += '|{index}|{uid}|{name}|\n'.format(index=index + 1, **item)

            wait = await data.wait(Chain(data).markdown(md))
            if not wait:
                return None

            try:
                index = int(wait.text_digits.strip()) - 1
                if 0 <= index < len(listens):
                    weibo = listens[index]['uid']
            except:
                return None

    if not weibo:
        return Chain(data).text('博士，没有找到可用的微博用户配置...')

    message = data.text_digits
    index = 0

    # 解析用户输入的序号
    r = re.search(r'(\d+)', message)
    if r:
        index = abs(int(r.group(1)))

    if '最新' in message:
        index = 1

    # 如果指定了序号，直接发送对应微博
    if index:
        return await send_by_index(index, weibo, data)
    else:
        # 显示历史微博列表
        blog_list = WeiboRecord.get_weibo_list(
            weibo, limit=10
        )  # user_id是字符串类型，无需转换为int

        if not blog_list:
            return Chain(data).text(
                '博士...暂时没有找到历史微博呢，请等待新微博推送吧~'
            )

        md = f'博士，这是【{blog_list[0].user_name}】的历史微博列表，回复【序号】来获取详情吧\n\n|序号|时间|内容|\n|----|----|----|\n'
        for idx, item in enumerate(blog_list, 1):  # 使用enumerate获取序号
            content = item.content.replace('\n', ' ').replace('|', '｜')
            content_preview = content[:20] + ('...' if len(content) > 20 else '')
            md += f'|{idx}|{item.created_at.replace("T", " ") or "未知时间"}|{content_preview}\n'  # 使用属性访问

        reply = Chain(data).markdown(md)

        wait = await data.wait(reply)
        if wait:
            r = re.search(r'(\d+)', wait.text_digits)
            if r:
                index = abs(int(r.group(1)))
                return await send_by_index(index, weibo, wait, blog_list)


@bot.timed_task(each=10)
async def _(_: BotHandlerFactory):
    await ws_manager.connect()
