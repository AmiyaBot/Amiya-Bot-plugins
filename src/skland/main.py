import os

from core import AmiyaBotPluginInstance

curr_dir = os.path.dirname(__file__)

bot = AmiyaBotPluginInstance(
    name='森空岛',
    version='1.0',
    plugin_id='amiyabot-skland',
    plugin_type='official',
    description='通过森空岛查询玩家信',
    document=f'{curr_dir}/README.md',
)
