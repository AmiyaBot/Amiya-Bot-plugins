import os

from core import AmiyaBotPluginInstance


curr_dir = os.path.dirname(__file__)


class WeiboPluginInstance(AmiyaBotPluginInstance):
    ...


bot = WeiboPluginInstance(
    name='百度千帆AppBuilder',
    version='3.1',
    plugin_id='amiyabot-appbuilder',
    plugin_type='official',
    description='接入千帆AppBuilder进行对话',
    document=f'{curr_dir}/README.md',
    global_config_schema=f'{curr_dir}/config_schema.json',
    global_config_default=f'{curr_dir}/config_default.yaml',
)
