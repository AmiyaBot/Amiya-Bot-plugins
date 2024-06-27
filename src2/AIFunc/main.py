import os

from amiyabot import PluginInstance, Message
from amiyabot.adapters.tencent.qqGlobal import QQGlobalBotInstance

curr_dir = os.path.dirname(__file__)

bot = PluginInstance(
    name='AI 功能优化',
    version='1.0',
    plugin_id='amiyabot-ai',
    plugin_type='official',
    description='AI 优化插件，无实际响应',
    document=f'{curr_dir}/README.md',
)


@bot.message_before_handle
async def _(data: Message, factory_name: str, _):
    if factory_name == 'amiyabot-blm-library':
        if isinstance(data.instance, QQGlobalBotInstance) and data.instance.appid == '102005657':
            return True
        return False
