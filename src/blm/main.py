import json
import os

from typing import Optional
from amiyabot import Message, Chain, log
from .src.common.blm_plugin_instance import BLMLibraryPluginInstance

curr_dir = os.path.dirname(__file__)

bot: Optional[BLMLibraryPluginInstance] = None


def dynamic_get_global_config_schema_data():
    filepath = f'{curr_dir}/config_templates/global_config_schema.json'
    if bot:
        try:
            with open(filepath, 'r') as file:
                data = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            log.info(f'Failed to load JSON from {filepath}.')
            return None

        model_list = bot.model_list()

        new_values = ['...']
        new_values.extend([model['model_name'] for model in model_list])

        try:
            data['properties']['default_model']['enum'] = new_values
        except KeyError as e:
            log.info(f'Expected keys not found in the JSON structure: {e}')

        return data
    else:
        return f'{curr_dir}/accessories/global_config_default.json'


bot = BLMLibraryPluginInstance(
    name='大语言模型调用库',
    version='1.0',
    plugin_id='amiyabot-blm-library',
    plugin_type='official',
    description='为其他插件提供大语音模型调用库',
    document=f'{curr_dir}/README.md',
    global_config_default=f'{curr_dir}/config_templates/global_config_default.json',
    global_config_schema=dynamic_get_global_config_schema_data,
)


@bot.on_message(keywords=['测试调用库'], level=5)
async def test_call_lib(data: Message):
    ret = await bot.chat_flow('测试调用库', 'ERNIE-Bot')
    log.info(ret)
    return Chain(data).text(ret)
