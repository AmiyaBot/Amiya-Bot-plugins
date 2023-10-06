import os
import time

from amiyabot.database import *

from core import bot as main_bot, Message, Chain, AmiyaBotPluginInstance
from core.database.user import UserBaseModel

curr_dir = os.path.dirname(__file__)


@table
class Intellect(UserBaseModel):
    user_id: str = CharField(primary_key=True)
    belong_id: str = CharField(null=True)
    cur_num: int = IntegerField()
    full_num: int = IntegerField()
    full_time: int = IntegerField()
    message_type: str = CharField()
    group_id: str = CharField()
    in_time: int = IntegerField()
    status: int = IntegerField()


class IntellectPluginInstance(AmiyaBotPluginInstance):
    @staticmethod
    def set_record(data: Message, cur_num: int, full_num: int, full_time: int = None):
        full_time = full_time or (full_num - cur_num) * 6 * 60 + int(time.time())

        update = {
            'belong_id': data.instance.appid,
            'cur_num': cur_num,
            'full_num': full_num,
            'full_time': full_time,
            'message_type': data.message_type or 'channel',
            'group_id': data.channel_id,
            'in_time': int(time.time()),
            'status': 0,
        }

        if not Intellect.get_or_none(user_id=data.user_id):
            Intellect.create(**{'user_id': data.user_id, **update})
        else:
            Intellect.update(**update).where(Intellect.user_id == data.user_id).execute()

        return Chain(data).text(f'阿米娅已经帮博士记住了（{cur_num}/{full_num}），回复满的时候阿米娅会提醒博士的哦～')


bot = IntellectPluginInstance(
    name='理智恢复提醒',
    version='1.4',
    plugin_id='amiyabot-arknights-intellect',
    plugin_type='official',
    description='可以记录理智量并在回复满时发送提醒',
    document=f'{curr_dir}/README.md',
    instruction=f'{curr_dir}/README_USE.md',
)


async def verify(data: Message):
    return (True, 5) if '理智' in data.text and ('满' in data.text or '多少' in data.text) else False


@bot.on_message(verify=verify)
async def _(data: Message):
    message = data.text_digits

    r = re.search(re.compile(r'理智(\d+)满(\d+)'), message)
    if r:
        cur_num = int(r.group(1))
        full_num = int(r.group(2))

        if cur_num < 0 or full_num <= 0:
            return Chain(data).text('啊这…看来博士是真的没有理智了……回头问问可露希尔能不能多给点理智合剂……')
        if cur_num >= full_num:
            return Chain(data).text('阿米娅已经帮博士记…呜……阿米娅现在可以提醒博士了吗？')
        if full_num > 135:
            return Chain(data).text('博士的理智有这么高吗？')

        return bot.set_record(data, cur_num, full_num)

    r_list = ['多少理智', '理智.*多少']
    for item in r_list:
        r = re.search(re.compile(item), message)
        if r:
            info: Intellect = Intellect.get_or_none(user_id=data.user_id, belong_id=data.instance.appid)
            if info:
                full_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(info.full_time))
                through = int(time.time()) - info.in_time
                restored = int(through / 360) + info.cur_num

                text = f'博士，根据上一次记录，您的 {info.full_num} 理智会在 {full_time} 左右回复满\n' f'不计算上限的话，现在已经回复到 {restored} 理智了'

                return Chain(data).text(text)
            else:
                return Chain(data).text('阿米娅还没有帮博士记录理智提醒哦～')


@bot.on_message(keywords='记录真实理智', level=10)
async def _(data: Message):
    if 'amiyabot-skland' in main_bot.plugins:
        skland = main_bot.plugins['amiyabot-skland']

        token = await skland.get_token(data.user_id)
        if not token:
            return Chain(data).text('未在森空岛插件绑定 Token，请查看森空岛插件的说明。')

        user_info = await skland.get_user_info(token)
        if not user_info:
            return Chain(data).text('无法从森空岛获取用户信息。')

        ap_info = user_info['gameStatus']['ap']

        full_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(ap_info['completeRecoveryTime']))
        ap = (time.time() - ap_info['lastApAddTime']) / 360

        if time.time() >= ap_info['completeRecoveryTime']:
            return Chain(data).text(f'博士，理智在{full_time}就已经恢复满了！快点上线查看吧～')

        return bot.set_record(data, ap_info['current'] + int(ap), ap_info['max'], ap_info['completeRecoveryTime'])
    else:
        return Chain(data).text('未检测到森空岛插件，无法使用功能。')


@bot.timed_task(each=10)
async def _(_):
    conditions = (Intellect.status == 0, Intellect.full_time <= int(time.time()))
    results: List[Intellect] = Intellect.select().where(*conditions)
    if results:
        Intellect.update(status=1).where(*conditions).execute()
        for item in results:
            text = f'博士！博士！您的理智已经满 {item.full_num} 了，快点上线查看吧～'

            await main_bot[item.belong_id].send_message(
                Chain().at(item.user_id).text(text), user_id=item.user_id, channel_id=item.group_id
            )
