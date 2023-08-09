import os

from typing import List, Set
from amiyabot import PluginInstance, Message, Chain
from core.database.bot import DisabledFunction
from core.util import get_index_from_text, get_doc, check_file_content
from core import bot as main_bot, AmiyaBotPluginInstance

curr_dir = os.path.dirname(__file__)
bot = PluginInstance(
    name='功能管理',
    version='1.6',
    plugin_id='amiyabot-functions',
    plugin_type='official',
    description='管理已安装的插件功能',
    document=f'{curr_dir}/README.md'
)


@bot.on_message(keywords=['功能', '帮助', '说明', 'help'], allow_direct=True)
async def _(data: Message):
    disabled_funcs: List[DisabledFunction] = DisabledFunction.select().where(
        DisabledFunction.channel_id == data.channel_id
    )
    disabled = [n.function_id for n in disabled_funcs]

    with open(f'{curr_dir}/template.md', mode='r', encoding='utf-8') as template:
        content = template.read().strip('\n')

    index = 1
    funcs = []
    items = ''
    for _, item in main_bot.plugins.items():
        if item.plugin_id == bot.plugin_id:
            continue

        status = '<span style="color: #4caf50">开启</span>'
        if item.plugin_id in disabled:
            status = '<span style="color: #f44336">已关闭</span>'

        funcs.append(item)
        items += f'|{index}|{item.name}|{item.version}|{item.description}|{status}|\n'
        index += 1

    reply = await data.wait(Chain(data).markdown(content.format(items=items)))
    if reply:
        index = get_index_from_text(reply.text_digits, funcs)
        if index is not None:
            return Chain(reply).markdown(get_plugin_use_doc(funcs[index]))


@bot.on_message(keywords='开启功能', level=5)
async def _(data: Message):
    if not data.is_admin:
        return None

    disabled: List[DisabledFunction] = DisabledFunction.select().where(DisabledFunction.channel_id == data.channel_id)

    func_ids = get_plugins_set() & set([n.function_id for n in disabled])

    if func_ids:
        content, funcs = get_plugins_content(func_ids)

        reply = await data.wait(Chain(data).text('有以下可开启的功能，回复【序号】开启对应功能').markdown(content))
        if reply:
            index = get_index_from_text(reply.text_digits, funcs)
            if index is not None:
                func = funcs[index]

                DisabledFunction.delete().where(DisabledFunction.channel_id == data.channel_id,
                                                DisabledFunction.function_id == func.plugin_id).execute()

                return Chain(data).text(f'已开启功能【{func.name}】').markdown(get_plugin_use_doc(func))
    else:
        return Chain(data).text('未关闭任何功能，无需开启~')


@bot.on_message(keywords='关闭功能', level=5)
async def _(data: Message):
    if not data.is_admin:
        return None

    disabled: List[DisabledFunction] = DisabledFunction.select().where(DisabledFunction.channel_id == data.channel_id)

    func_ids = get_plugins_set() - set([n.function_id for n in disabled])

    if func_ids:
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


def get_plugin_use_doc(instance: AmiyaBotPluginInstance):
    if hasattr(instance, 'instruction'):
        content = check_file_content(instance.instruction)
        if content:
            return f'# {instance.name}\n\n{content}'

    return get_doc(instance)


def get_plugins_set():
    return set(
        [plugin_id for plugin_id in main_bot.plugins.keys() if plugin_id != bot.plugin_id]
    )


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
