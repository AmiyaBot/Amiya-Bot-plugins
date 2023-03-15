import os

from typing import List
from amiyabot import PluginInstance, Message, Chain
from core.database.bot import DisabledFunction
from core.util import get_index_from_text, get_doc
from core import bot as main_bot

curr_dir = os.path.dirname(__file__)
bot = PluginInstance(
    name='功能管理',
    version='1.1',
    plugin_id='amiyabot-functions',
    plugin_type='official',
    description='管理已安装的功能',
    document=f'{curr_dir}/README.md'
)


@bot.on_message(keywords=['功能', '帮助', '说明', 'help'], allow_direct=True)
async def _(data: Message):
    disabled_funcs: List[DisabledFunction] = DisabledFunction.select().where(
        DisabledFunction.channel_id == data.channel_id
    )
    disabled = [n.function_id for n in disabled_funcs]

    content = "功能清单\n\n" \
              "频道/群管理员发送 `兔兔开启功能/关闭功能` 可开关单个功能\n\n"

    index = 1
    funcs = []
    for _, item in main_bot.plugins.items():
        if item.plugin_id == bot.plugin_id:
            continue

        funcs.append(item)
        content += f'[{index}]{item.name}%s\n' % ('（已关闭）' if item.plugin_id in disabled else '')
        index += 1

    content += '\n回复【序号】查询详细的功能描述'

    reply = await data.wait(Chain(data).text(content))
    if reply:
        index = get_index_from_text(reply.text_digits, funcs)
        if index is not None:
            return Chain(reply).markdown(get_doc(funcs[index]))


@bot.on_message(keywords='开启功能', level=5)
async def _(data: Message):
    if not data.is_admin:
        return None

    disabled: List[DisabledFunction] = DisabledFunction.select().where(DisabledFunction.channel_id == data.channel_id)

    func_ids = set(bot.plugins.keys()) & set([n.function_id for n in disabled])

    if func_ids:
        content = '有以下可开启的功能：\n\n'
        index = 1
        funcs = []
        for n in func_ids:
            item = bot.plugins[n]
            funcs.append(item)
            content += f'[{index}]{item.name}\n'
            index += 1

        content += '\n回复【序号】开启对应功能'

        reply = await data.wait(Chain(data).text(content))
        if reply:
            index = get_index_from_text(reply.text_digits, funcs)
            if index is not None:
                func = funcs[index]

                DisabledFunction.delete().where(DisabledFunction.channel_id == data.channel_id,
                                                DisabledFunction.function_id == func.plugin_id).execute()

                return Chain(data).text(f'已开启功能【{func.name}】').markdown(get_doc(func))
    else:
        return Chain(data).text('未关闭任何功能，无需开启~')


@bot.on_message(keywords='关闭功能', level=5)
async def _(data: Message):
    if not data.is_admin:
        return None

    disabled: List[DisabledFunction] = DisabledFunction.select().where(DisabledFunction.channel_id == data.channel_id)

    func_ids = set(bot.plugins.keys()) - set([n.function_id for n in disabled])

    if func_ids:
        content = '有以下可关闭的功能：\n\n'
        index = 1
        funcs = []
        for n in func_ids:
            item = bot.plugins[n]
            funcs.append(item)
            content += f'[{index}]{item.name}\n'
            index += 1

        content += '\n回复【序号】关闭对应功能'

        reply = await data.wait(Chain(data).text(content))
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
