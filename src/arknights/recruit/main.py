import os
import dhash
import jieba
import shutil
import asyncio

from io import BytesIO
from PIL import Image
from jieba import posseg
from typing import List
from itertools import combinations
from amiyabot import event_bus
from amiyabot.network.download import download_async
from amiyabot.adapters.cqhttp import CQHttpBotInstance

from core import log, Message, Chain, AmiyaBotPluginInstance, Requirement
from core.util import all_match, read_yaml, create_dir
from core.lib.baiduCloud import BaiduCloud
from core.resource.arknightsGameData import ArknightsGameData

curr_dir = os.path.dirname(__file__)
config_path = 'resource/plugins/baiduCloud.yaml'

if not os.path.exists(config_path):
    create_dir(config_path, is_file=True)
    shutil.copy(f'{curr_dir}/baiduCloud.yaml', config_path)

baidu = BaiduCloud(read_yaml(config_path))

recruit_config = read_yaml(f'{curr_dir}/recruit.yaml')
discern = recruit_config.autoDiscern


class Recruit:
    tags_list: List[str] = []

    @staticmethod
    async def init_tags_list():
        log.info('building operator tags keywords dict...')

        tags = ['资深', '高资', '高级资深']
        for name, item in ArknightsGameData.operators.items():
            for tag in item.tags:
                if tag not in tags:
                    tags.append(tag)

        with open(f'{curr_dir}/tags.txt', mode='w+', encoding='utf-8') as file:
            file.write('\n'.join([item + ' 500 n' for item in tags]))

        jieba.load_userdict(f'{curr_dir}/tags.txt')

        Recruit.tags_list = tags

    @classmethod
    async def action(cls, data: Message, text: str, ocr: bool = False):
        reply = Chain(data)

        if not text:
            if ocr:
                return reply.text('图片识别失败')
            return None

        words = posseg.lcut(text.replace('公招', ''))

        tags = []
        max_rarity = 5
        for item in words:
            if item.word in cls.tags_list:
                if item.word in ['资深', '资深干员'] and '资深干员' not in tags:
                    tags.append('资深干员')
                    continue
                if item.word in ['高资', '高级资深', '高级资深干员'] and '高级资深干员' not in tags:
                    tags.append('高级资深干员')
                    max_rarity = 6
                    continue
                if item.word not in tags:
                    tags.append(item.word)

        if tags:
            result = find_operator_tags_by_tags(tags, max_rarity=max_rarity)
            if result:
                operators = {}
                for item in result:
                    name = item['operator_name']
                    if name not in operators:
                        operators[name] = item
                    else:
                        operators[name]['operator_tags'] += item['operator_tags']

                groups = []

                for comb in [tags] if len(tags) == 1 else find_combinations(tags):
                    lst = []
                    max_r = 0
                    for name, item in operators.items():
                        rarity = item['operator_rarity']
                        if all_match(item['operator_tags'], comb):
                            if rarity == 6 and '高级资深干员' not in comb:
                                continue
                            if rarity >= 4 or rarity == 1:
                                if rarity > max_r:
                                    max_r = rarity
                                lst.append(item)
                            else:
                                break
                    else:
                        if lst:
                            groups.append({'tags': comb, 'max_rarity': max_r, 'operators': lst})

                if groups:
                    groups = sorted(groups, key=lambda n: (-len(n['tags']), -n['max_rarity']))
                    return reply.html(f'{curr_dir}/template/operatorRecruit.html', {'groups': groups, 'tags': tags})
                else:
                    return reply.text('博士，没有找到可以锁定稀有干员的组合')
            else:
                return reply.text('博士，无法查询到标签所拥有的稀有干员')

        if ocr:
            return reply.text('博士，没有在图内找到标签信息')


class RecruitPluginInstance(AmiyaBotPluginInstance):
    def install(self):
        asyncio.create_task(Recruit.init_tags_list())

    def uninstall(self):
        event_bus.unsubscribe('gameDataInitialized', update)


bot = RecruitPluginInstance(
    name='明日方舟公招查询',
    version='2.1',
    plugin_id='amiyabot-arknights-recruit',
    plugin_type='official',
    description='可通过指令或图像识别规划公招标签组合',
    document=f'{curr_dir}/README.md',
    instruction=f'{curr_dir}/README_USE.md',
    requirements=[Requirement('amiyabot-arknights-gamedata', official=True)],
)


@event_bus.subscribe('gameDataInitialized')
def update(_):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        bot.install()


def find_operator_tags_by_tags(tags, max_rarity):
    res = []
    for name, item in ArknightsGameData.operators.items():
        if not item.is_recruit or item.rarity > max_rarity:
            continue
        for tag in item.tags:
            if tag in tags:
                res.append(
                    {
                        'operator_id': item.id,
                        'operator_name': name,
                        'operator_rarity': item.rarity,
                        'operator_tags': tag,
                    }
                )

    return sorted(res, key=lambda n: -n['operator_rarity'])


def find_combinations(_list):
    result = []
    for i in range(3):
        for n in combinations(_list, i + 1):
            n = list(n)
            if n and not ('高级资深干员' in n and '资深干员' in n):
                result.append(n)
    result.reverse()
    return result


async def auto_discern(data: Message):
    for item in data.image:
        img = await download_async(item)
        if img:
            try:
                hash_value = dhash.dhash_int(Image.open(BytesIO(img)))
                diff = dhash.get_num_bits_different(hash_value, discern.templateHash)
            except OSError:
                return False

            if diff <= discern.maxDifferent:
                data.image = [img]
                return True
    return False


async def get_ocr_result(data: Message):
    result = ''

    if baidu.enable:
        res = await baidu.basic_accurate(data.image[0])
        if not res:
            res = await baidu.basic_general(data.image[0])

        if res and 'words_result' in res:
            result = ''.join([item['words'] for item in res['words_result']])

    # 如果百度 OCR 没有结果且实例是 go-cq，调用 go-cq OCR
    if not result and type(data.instance) is CQHttpBotInstance:
        instance: CQHttpBotInstance = data.instance
        async with log.catch():
            images_id = [item['data']['file'] for item in data.message['message'] if item['type'] == 'image']
            if images_id:
                cq_res = await instance.api.post('ocr_image', {'image': images_id[0]})
                result = ''.join([item['text'] for item in cq_res.data['data']['texts']])

    return result


@bot.on_message(keywords=['公招', '公开招募'], allow_direct=True, level=10)
async def _(data: Message):
    if data.image:
        # 直接 OCR 识别图片
        return await Recruit.action(data, await get_ocr_result(data), ocr=True)
    else:
        # 先验证文本内容
        recruit = await Recruit.action(data, data.text_original)
        if recruit:
            return recruit
        else:
            # 文本内容验证不出则询问截图
            if not baidu.enable and type(data.instance) is not CQHttpBotInstance:
                return None

            wait = await data.wait(Chain(data, at=True).text('博士，请发送您的公招界面截图~'), force=True)

            if wait and wait.image:
                return await Recruit.action(wait, await get_ocr_result(wait), ocr=True)
            else:
                return Chain(data, at=True).text('博士，您没有发送图片哦~')


@bot.on_message(verify=auto_discern, check_prefix=False, allow_direct=True)
async def _(data: Message):
    return await Recruit.action(data, await get_ocr_result(data), ocr=True)
