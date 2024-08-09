import os
import re
import datetime

from typing import List, Set
from amiyabot import Message, Chain
from amiyabot.adapters.tencent.qqGuild import QQGuildBotInstance
from amiyabot.adapters.tencent.qqGroup import QQGroupBotInstance
from core import bot as main_bot, log, AmiyaBotPluginInstance
from core.database.bot import DisabledFunction, FunctionUsed
from core.util import get_index_from_text, check_file_content

from .database import ChannelRecord

curr_dir = os.path.dirname(__file__)
bot = AmiyaBotPluginInstance(
    name='功能管理',
    version='2.6',
    plugin_id='amiyabot-functions',
    plugin_type='official',
    description='管理已安装的插件功能',
    document=f'{curr_dir}/README.md',
    instruction=f'{curr_dir}/README_USE.md',
    global_config_default=f'{curr_dir}/configs/global_config_default.json',
    global_config_schema=f'{curr_dir}/configs/global_config_schema.json',
)
disabled_remind = {}


@bot.message_before_handle
async def _(data: Message, factory_name: str, _):
    # 检查该 channel 是否已有禁用的功能
    disabled_functions_for_channel = DisabledFunction.select().where(DisabledFunction.channel_id == data.channel_id)

    # 检查是否已存在与当前 channel_id 相关的记录
    channel_record = ChannelRecord.get_or_none(channel_id=data.channel_id)

    # 如果记录不存在，创建一个新的记录并写入当前消息时间
    if not channel_record:
        ChannelRecord.create(channel_id=data.channel_id, last_message=datetime.datetime.now())

        # 如果该 channel 中已有禁用的功能，不更改当前状态
        if not disabled_functions_for_channel.exists():
            if bot.get_config('newChannelDisableAll'):
                log.info(f'关闭全部功能： {data.channel_id}')

                # 禁用所有功能
                disabled_all(data.channel_id)
                return False
    else:
        channel_record.last_message = datetime.datetime.now()
        channel_record.save()

    # 检查功能是否已被禁用
    disabled = DisabledFunction.get_or_none(function_id=factory_name, channel_id=data.channel_id)

    if disabled:
        if data.channel_id not in disabled_remind:
            disabled_remind[data.channel_id] = {}

        if factory_name not in disabled_remind[data.channel_id]:
            disabled_remind[data.channel_id][factory_name] = 1
        else:
            disabled_remind[data.channel_id][factory_name] += 1

        if disabled_remind[data.channel_id][factory_name] >= bot.get_config('disabledRemindRate'):
            disabled_remind[data.channel_id][factory_name] = 0
            plugin = main_bot.plugins[factory_name]

            await data.send(Chain(data).text(f'【{plugin.name}】功能已关闭，请管理员开启后再使用~'))

    return not bool(disabled)


@bot.message_after_handle
async def _(data: Chain, factory_name: str, _):
    _, is_created = FunctionUsed.get_or_create(function_id=factory_name)
    if not is_created:
        FunctionUsed.update(use_num=FunctionUsed.use_num + 1).where(FunctionUsed.function_id == factory_name).execute()


@bot.on_message(keywords=['功能', '帮助', '说明', 'help'], allow_direct=True)
async def _(data: Message):
    disabled_funcs: List[DisabledFunction] = DisabledFunction.select().where(
        DisabledFunction.channel_id == data.channel_id
    )
    disabled = [n.function_id for n in disabled_funcs]

    with open(f'{curr_dir}/template.md', mode='r', encoding='utf-8') as template:
        content = template.read().strip('\n')

    sorted_plugins = sorted(main_bot.plugins.items(), key=lambda n: n[1].name)

    funcs = []
    items = ''
    for i, n in enumerate(sorted_plugins):
        index = i + 1
        item = n[1]

        # if item.plugin_id == bot.plugin_id:
        #     continue

        status = '<span style="color: #4caf50">开启</span>'
        if item.plugin_id in disabled:
            status = '<span style="color: #f44336">已关闭</span>'

        funcs.append(item)
        items += f'|{index}|{item.name}|{item.version}|{item.description}|{status}|\n'

    reply = await data.wait(Chain(data).markdown(content.format(items=items)))
    if reply:
        index = get_index_from_text(reply.text_digits, funcs)
        if index is not None:
            return Chain(reply).markdown(
                get_plugin_use_doc(
                    data.instance,
                    funcs[index],
                )
            )


@bot.on_message(keywords=re.compile(r'开启(全部|所有)?功能'), level=5)
async def _(data: Message):
    if not data.is_admin:
        return None

    disabled: List[DisabledFunction] = DisabledFunction.select().where(DisabledFunction.channel_id == data.channel_id)

    func_ids = get_plugins_set() & set([n.function_id for n in disabled])

    if func_ids:
        if data.verify.keypoint[0]:
            DisabledFunction.delete().where(DisabledFunction.channel_id == data.channel_id).execute()
            return Chain(data).text('已开启所有功能！')

        content, funcs = get_plugins_content(func_ids)

        reply = await data.wait(Chain(data).text('有以下可开启的功能，回复【序号】开启对应功能').markdown(content))
        if reply:
            index = get_index_from_text(reply.text_digits, funcs)
            if index is not None:
                func = funcs[index]

                DisabledFunction.delete().where(
                    DisabledFunction.channel_id == data.channel_id, DisabledFunction.function_id == func.plugin_id
                ).execute()

                return (
                    Chain(data)
                    .text(f'已开启功能【{func.name}】')
                    .markdown(
                        get_plugin_use_doc(
                            data.instance,
                            func,
                        )
                    )
                )
    else:
        return Chain(data).text('未关闭任何功能，无需开启~')


@bot.on_message(keywords=re.compile(r'关闭(全部|所有)?功能'), level=5)
async def _(data: Message):
    if not data.is_admin:
        return None

    disabled: List[DisabledFunction] = DisabledFunction.select().where(DisabledFunction.channel_id == data.channel_id)

    func_ids = get_plugins_set() - set([n.function_id for n in disabled])

    if func_ids:
        if data.verify.keypoint[0]:
            disabled_all(data.channel_id)
            return Chain(data).text('已关闭所有功能！')

        content, funcs = get_plugins_content(func_ids)

        reply = await data.wait(Chain(data).text('有以下可关闭的功能，回复【序号】关闭对应功能').markdown(content))
        if reply:
            index = get_index_from_text(reply.text_digits, funcs)
            if index is not None:
                func = funcs[index]

                DisabledFunction.create(
                    function_id=func.plugin_id,
                    channel_id=data.channel_id,
                )

                return Chain(data).text(f'已关闭功能【{func.name}】')
    else:
        return Chain(data).text('已经没有可以关闭的功能了~')


def disabled_all(channel_id):
    funcs = [{'function_id': func, 'channel_id': channel_id} for func in get_plugins_set()]
    DisabledFunction.batch_insert(funcs)


def get_plugin_use_doc(instance, plugin: AmiyaBotPluginInstance):
    public_bot = isinstance(instance, (QQGroupBotInstance, QQGuildBotInstance))

    doc = plugin.document
    if hasattr(plugin, 'instruction') and plugin.instruction:
        doc = plugin.instruction

    if public_bot and doc and os.path.isfile(doc):
        if not instance.private:
            doc_file = os.path.splitext(os.path.basename(doc))
            doc_public = os.path.join(os.path.dirname(doc), f'{doc_file[0]}-public{doc_file[1]}')

            if os.path.exists(doc_public):
                doc = doc_public

    content = check_file_content(doc)
    if content:
        if public_bot:
            bot_name = '@%s ' % (instance.bot_name if hasattr(instance, 'bot_name') else '机器人')
            content = content.replace('{bot_name}', bot_name)

        return f'# {plugin.name}\n\n{content}'


def get_plugins_set():
    return set([plugin_id for plugin_id in main_bot.plugins.keys() if plugin_id != bot.plugin_id])


def get_plugins_content(func_ids: Set[str]):
    content = '|序号|插件名|版本|描述|\n|----|----|----|----|\n'
    index = 1
    funcs = []
    for n in func_ids:
        item = main_bot.plugins[n]
        if item.plugin_id == bot.plugin_id:
            continue

        funcs.append(item)
        content += f'|{index}|{item.name}|{item.version}|{item.description}|\n'
        index += 1

    return content, funcs
