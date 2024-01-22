import os
import re
import time
import base64
import shutil

from amiyabot import GroupConfig
from amiyabot.network.download import download_async

from core import Message, Chain, AmiyaBotPluginInstance
from core.util import read_yaml, check_sentence_by_re
from core.database.user import UserInfo, UserGachaInfo

curr_dir = os.path.dirname(__file__)
face_dir = 'resource/plugins/user/face'

talking = read_yaml(f'{curr_dir}/talking.yaml')


class UserPluginInstance(AmiyaBotPluginInstance):
    def install(self):
        if not os.path.exists(face_dir):
            shutil.copytree(f'{curr_dir}/face', face_dir)

    def uninstall(self):
        shutil.rmtree(face_dir)


bot = UserPluginInstance(
    name='兔兔互动',
    version='2.3',
    plugin_id='amiyabot-user',
    plugin_type='official',
    description='包含签到、问候、好感和戳一戳等日常互动',
    document=f'{curr_dir}/README.md',
    instruction=f'{curr_dir}/README_USE.md',
)
bot.set_group_config(GroupConfig('user', allow_direct=True))


def get_face():
    images = []
    for root, dirs, files in os.walk(face_dir):
        images += [os.path.join(root, file) for file in files if file != '.gitkeep']

    return images


def sign_in(data: Message, sign_type=0):
    info: UserInfo = UserInfo.get_user(data.user_id)

    today = time.strftime('%Y-%m-%d', time.localtime())

    if info.sign_date != today:
        coupon = 50
        feeling = 50

        UserInfo.update(
            sign_date=today,
            user_feeling=UserInfo.user_feeling + feeling,
            user_mood=15,
            sign_times=UserInfo.sign_times + 1,
            jade_point_max=0,
        ).where(UserInfo.user_id == data.user_id).execute()

        UserGachaInfo.get_or_create(user_id=data.user_id)
        UserGachaInfo.update(coupon=UserGachaInfo.coupon + coupon).where(
            UserGachaInfo.user_id == data.user_id
        ).execute()

        return {'text': f'{"签到成功，" if sign_type else ""}{coupon}张寻访凭证已经送到博士的办公室啦，请博士注意查收哦', 'status': True}

    if sign_type and info.sign_date == today:
        return {'text': '博士今天已经签到了哦', 'status': False}

    return {'text': '', 'status': False}


def talk_time():
    localtime = time.localtime(time.time())
    hours = localtime.tm_hour
    if 0 <= hours <= 5:
        return ''
    elif 5 < hours <= 11:
        return '早上'
    elif 11 < hours <= 14:
        return '中午'
    elif 14 < hours <= 18:
        return '下午'
    elif 18 < hours <= 24:
        return '晚上'


def compose_talk_verify(words, names):
    async def verify(data: Message):
        return check_sentence_by_re(data.text, words, names)

    return verify


async def user_info(data: Message):
    image = ''
    if data.avatar:
        avatar = await download_async(data.avatar)
        if avatar:
            image = 'data:image/jpg;base64,' + base64.b64encode(avatar).decode('ascii')

    info = {'avatar': image, 'nickname': data.nickname, **UserInfo.get_user_info(data.user_id)}

    return Chain(data).html(f'{curr_dir}/template/userInfo.html', info, width=700, height=300)


async def only_name(data: Message):
    if data.image:
        return False

    text = data.text

    for item in bot.prefix_keywords:
        if item != '阿米娅' or (item == '阿米娅' and text.startswith(item)):
            text = text.replace(item, '', 1)

    text = re.sub(r'\W', '', text).strip()

    return text == '', 2
