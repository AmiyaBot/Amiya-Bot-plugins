import os
import shutil
import openai

from amiyabot import PluginInstance, Message, Chain
from core.util import create_dir, read_yaml, run_in_thread_pool
from core import log

curr_dir = os.path.dirname(__file__)
config_file = 'resource/plugins/chatGPT/config.yaml'


class ChatGPTPluginInstance(PluginInstance):
    def install(self):
        if not os.path.exists(config_file):
            create_dir(config_file, is_file=True)
            shutil.copy(f'{curr_dir}/config.yaml', config_file)


bot = ChatGPTPluginInstance(
    name='ChatGPT 智能回复',
    version='1.0',
    plugin_id='amiyabot-chatgpt',
    plugin_type='official',
    description='调用 OpenAI ChatGPT 智能回复普通对话',
    document=f'{curr_dir}/README.md'
)
user_lock = []


async def check_talk(data: Message):
    if 'chat' in data.text.lower():
        return True, 10
    return True, 0


@bot.on_message(verify=check_talk)
async def _(data: Message):
    if not data.text:
        return

    if data.user_id in user_lock:
        await data.send(Chain(data).text('博士，我还在想上一个问题...>.<'))
        return

    config = read_yaml(config_file, _dict=True)
    openai.api_key = config['api_key']

    user_lock.append(data.user_id)

    async with log.catch():
        await data.send(Chain(data).text('阿米娅思考中...').face(32))
        response = await run_in_thread_pool(
            openai.Completion.create,
            **{
                'prompt': data.text_origin,
                **config['options']
            }
        )

    user_lock.remove(data.user_id)

    text: str = response['choices'][0]['text'].strip('\n')

    if len(text) >= config['max_length']:
        return Chain(data, reference=True).markdown(text.replace('\n', '<br>'))
    else:
        return Chain(data, reference=True).text(text)
