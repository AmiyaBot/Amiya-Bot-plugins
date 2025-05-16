import os
import random

from core import Message, Chain
from core.database.user import OperatorBox, UserGachaInfo, UserInfo
from core.database.bot import *
from core.util import insert_empty
from core.resource.arknightsGameData import ArknightsGameData
from .utils.create_gacha_image import create_gacha_image
from .utils.get_operators import get_operators
from .utils.pool_methods import get_pool_name,get_custom_pool,get_official_pool
from .utils.logger import debug_log

curr_dir = os.path.dirname(__file__)

line_height = 16
side_padding = 10
avatar_resource = 'resource/gamedata/avatar'
color = {6: 'FF4343', 5: 'FEA63A', 4: 'A288B5', 3: '7F7F7F', 2: '7F7F7F', 1: '7F7F7F'}

bot_caller = {'plugin_instance': None}


@table
class PoolSpOperator(BotBaseModel):
    pool_id: Union[ForeignKeyField, int] = ForeignKeyField(Pool, db_column='pool_id', on_delete='CASCADE')
    operator_name: str = CharField()
    rarity: int = IntegerField()
    classes: str = CharField()
    image: str = CharField()

class GachaBuilder:
    def __init__(self, data: Message):
        self.data = data
        self.user_gacha: UserGachaInfo = UserGachaInfo.get_or_create(user_id=data.user_id)[0]

        if self.user_gacha.use_custom_gacha_pool:
            debug_log(f'使用自定义寻访池' + str(self.user_gacha.custom_gacha_pool))
            pool : Pool = get_custom_pool(self.user_gacha.custom_gacha_pool)
        else:
            debug_log(f'使用官方寻访池' + str(self.user_gacha.gacha_pool))
            pool : Pool = get_official_pool(self.user_gacha.gacha_pool)

        self.pool = pool

        # 获取填充用干员
        all_operators = get_operators(self.__is_classic_only(pool))

        # 按稀有度拆分填充到 fillin_operators[raity]
        fillin_operators = {}
        fillin_operators[6] = []
        fillin_operators[5] = []
        fillin_operators[4] = []
        fillin_operators[3] = []
        fillin_operators[2] = []
        fillin_operators[1] = []

        for item in all_operators:
            rarity = item.rarity
            name = item.name
            fillin_operators[rarity].append(name)
        
        # 按顺序获取干员并计算weight

        gacha_operator_pool = {}
        gacha_operator_pool[6] = self.__get_gacha(self.__get_weight(pool.pickup_6),self.__get_weight(pool.pickup_s),self.__get_pickup_rate(pool,6),fillin_operators[6])
        gacha_operator_pool[5] = self.__get_gacha(self.__get_weight(pool.pickup_5),self.__get_weight(pool.pickup_s_5),self.__get_pickup_rate(pool,5),fillin_operators[5])
        gacha_operator_pool[4] = self.__get_gacha(self.__get_weight(pool.pickup_4),self.__get_weight(pool.pickup_s_4),self.__get_pickup_rate(pool,4),fillin_operators[4])
        gacha_operator_pool[3] = self.__get_gacha(self.__get_weight(pool.pickup_3),self.__get_weight(pool.pickup_s_3),self.__get_pickup_rate(pool,3),fillin_operators[3])
        gacha_operator_pool[2] = self.__get_gacha(self.__get_weight(pool.pickup_2),self.__get_weight(pool.pickup_s_2),self.__get_pickup_rate(pool,2),fillin_operators[2])
        gacha_operator_pool[1] = self.__get_gacha(self.__get_weight(pool.pickup_1),self.__get_weight(pool.pickup_s_1),self.__get_pickup_rate(pool,1),fillin_operators[1])
        
        self.gacha_operator_pool = gacha_operator_pool
        
        self.break_even = self.user_gacha.gacha_break_even
        self.rarity_range = {6: 2, 5: 8, 4: 50, 3: 40, 2: 0, 1: 0}
        '''
        概率：
        3 星 40% 区间为 1 ~ 40
        4 星 50% 区间为 41 ~ 90
        5 星 8% 区间为 91 ~ 98
        6 星 2% 区间为 99 ~ 100
        '''
        
    @staticmethod
    def __get_pickup_rate(pool:Pool, rarity:int):

        # 针对旧版本池子的特殊处理
        # limit_pool = 2 联合行动 的五星六星都只会出up干员
        # limit_pool = 3 前路回响 的六星都只会出up干员

        # 旧池子，rate没填，需要给默认值

        if rarity == 6:
            if pool.pickup_6_rate is None:
                if pool.is_official is None or pool.is_official is True:
                    debug_log(f'calc 6 rate with None: pool.limit_pool:{pool.limit_pool}')
                    if pool.limit_pool == 0:
                        return 0.5
                    if pool.limit_pool == 1:
                        return 0.7
                    if pool.limit_pool == 2:
                        return 1
                    if pool.limit_pool == 3:
                        return 1
                    if pool.limit_pool == 4:
                        return 1
                    if pool.limit_pool == 5:
                        return 1
                # 非官方卡池不写概率默认70% up
                debug_log(f'calc 6 rate with pool.is_official:{pool.is_official}, set to 0.7')
                return 0.7
            debug_log(f'calc 6 rate with:{pool.pickup_6_rate}')
            return pool.pickup_6_rate
        if rarity == 5:
            if pool.limit_pool == 2:
                return 1
            if pool.pickup_5_rate is None:
                return 0.5
            return pool.pickup_5_rate
        if rarity == 4:
            if pool.pickup_4_rate is None:
                return 0
            return pool.pickup_4_rate
        if rarity == 3:
            if pool.pickup_3_rate is None:
                return 0
            return pool.pickup_3_rate
        if rarity == 2:
            if pool.pickup_2_rate is None:
                return 0
            return pool.pickup_2_rate
        if rarity == 1:
            if pool.pickup_1_rate is None:
                return 0
            return pool.pickup_1_rate

    @staticmethod
    def __is_classic_only(pool:Pool):
        if pool.is_classicOnly is True:
            return True
        
        if pool.limit_pool == 4:
            return True
        
        return False

    @staticmethod
    def __get_gacha(weight_pickup,weight_special,up_rate,fillin):
        
        '''

        将两个weight集合加上fillin合并归一化
        
        '''

        debug_log(f'weight_pickups:{len(weight_pickup)}, weight_special:{len(weight_special)}, up_rate:{up_rate}, fillin:{len(fillin)}')

        final_weight = {}
        
        if up_rate > 1 :
            up_rate = 1
        
        if up_rate < 0 :
            up_rate = 0

        # 因为浮点数精度问题，这里把权重放大10000倍
        scale_up_factor = 10000

        # 写得这么复杂是为了应对负数weight，作用是减少权重
        # 某个池子可以抽出其他的六星，但是不能抽出能天使
        # 可以在pick_up_s里标记 能天使|-1
        # 他会和fillin里的 能天使|1 加在一起使得能天使权重为0

        # 首先填充up干员
        weight_pickup_dict = weight_pickup
        weight_pickup_total = 0
        for char_name in weight_pickup_dict:
            char_weight = weight_pickup_dict[char_name]
            if char_weight < 0:
                char_weight = 0
                
            weight_pickup_total += char_weight
        
        if weight_pickup_total == 0:
            for char_name in weight_pickup_dict:
                final_weight[char_name] = 0
        else:
            for char_name in weight_pickup_dict:
                char_weight = weight_pickup_dict[char_name]
                if char_weight < 0:
                    char_weight = 0
                
                final_weight[char_name] = up_rate * scale_up_factor * char_weight / weight_pickup_total

        # 然后填充special和fillin
        weight_special_shallow_copy = {}
        for char_name in weight_special:
            weight_special_shallow_copy[char_name] = weight_special[char_name]
        
        for char_name in fillin:
            if char_name in weight_special_shallow_copy:
                weight_special_shallow_copy[char_name] += 1
            else:
                weight_special_shallow_copy[char_name] = 1
            
        weight_fillin_total = 0
        for char_name in weight_special_shallow_copy:
            char_weight = weight_special_shallow_copy[char_name]
            if char_weight <0:
                char_weight = 0
                
            # 一个干员一旦已经Pickup，fillin的概率就完全失效
            if char_name not in final_weight:
                weight_fillin_total += char_weight
        
        if weight_fillin_total != 0:        
            for char_name in weight_special_shallow_copy:
                char_weight = weight_special_shallow_copy[char_name]
                if char_weight <0:
                    char_weight = 0
                
                weight_to_add = (1 - up_rate) * scale_up_factor * char_weight / weight_fillin_total
                
                # 一个干员一旦已经Pickup，fillin的概率就完全失效
                if char_name not in final_weight:
                    final_weight[char_name] = weight_to_add
        
        return final_weight


    @staticmethod
    def __get_weight(pickups:Union[CharField, str]):
        operator_weights = {}

        if pickups is None:
            return operator_weights

        for name in pickups.split(','):
            char_weight = 1
            char_name = name
            if '|' in name:
                char_weight = int(char_name.split("|")[1])
                char_name =char_name.split("|")[0]

            if char_name not in operator_weights:
                operator_weights[char_name] = char_weight
            else:
                operator_weights[char_name] += char_weight
        
        return operator_weights

    def continuous_mode(self, times, coupon, point):
        operators = self.start_gacha(times, coupon, point)

        rarity_sum = [0, 0, 0, 0]
        high_star = {5: {}, 6: {}}

        ten_gacha = []
        purple_pack = 0
        multiple_rainbow = {}

        result = f'阿米娅给博士扔来了{times}张简历，博士细细地检阅着...\n\n【{self.pool.pool_name}】\n'

        for item in operators:
            rarity = item['rarity']
            name = item['name']

            # 记录抽到的各星级干员的数量
            rarity_sum[rarity - 3] += 1

            # 记录抽中的高星干员
            if rarity >= 5:
                if name not in high_star[rarity]:
                    high_star[rarity][name] = 0
                high_star[rarity][name] += 1

            # 记录每十连的情况
            ten_gacha.append(rarity)
            if len(ten_gacha) >= 10:
                five = ten_gacha.count(5)
                six = ten_gacha.count(6)

                if five == 0 and six == 0:
                    purple_pack += 1

                if six > 1:
                    if six not in multiple_rainbow:
                        multiple_rainbow[six] = 0
                    multiple_rainbow[six] += 1
                ten_gacha = []
        for r in high_star:
            sd = high_star[r]
            if sd:
                result += f'\n[cl %s@#{color[r]} cle]\n' % ('★' * r)
                operator_num = {}
                for i in sorted(sd, key=sd.__getitem__, reverse=True):
                    num = high_star[r][i]
                    if num not in operator_num:
                        operator_num[num] = []
                    operator_num[num].append(i)
                for num in operator_num:
                    result += '%s X %d\n' % ('、'.join(operator_num[num]), num)

        if rarity_sum[2] == 0 and rarity_sum[3] == 0:
            result += '\n然而并没有高星干员...'

        result += '\n三星：%s四星：%d\n五星：%s六星：%d\n' % (
            insert_empty(rarity_sum[0], 4),
            rarity_sum[1],
            insert_empty(rarity_sum[2], 4),
            rarity_sum[3],
        )

        enter = True
        if purple_pack > 0:
            result += '\n'
            enter = False
            result += f'出现了 {purple_pack} 次十连紫气东来\n'
        for num in multiple_rainbow:
            if enter:
                result += '\n'
                enter = False
            result += f'出现了 {multiple_rainbow[num]} 次十连内 {num} 个六星\n'

        result += '\n%s' % self.check_break_even()

        return Chain(self.data).text_image(result)

    def detailed_mode(self, times, coupon, point, *args, **kwargs):
        '''
        抽卡次数小于等于10次时的逻辑
        '''
        operators = self.start_gacha(times, coupon, point)
        operators_info = {}

        game_data = ArknightsGameData
        reply = Chain(self.data)

        result = f'阿米娅给博士扔来了{times}张简历，博士细细地检阅着...\n\n【{get_pool_name(self.pool)}】\n\n'
        icons = []

        icon_size = 32
        offset = int((line_height * 3 - icon_size) / 2)
        top = side_padding + line_height * 2 + offset + 5

        for index, item in enumerate(operators):
            name = item['name']
            rarity = item['rarity']

            star = f'[cl %s@#{color[rarity]} cle]' % ('★' * rarity)

            result += '%s%s%s\n\n' % (' ' * 15, insert_empty(name, 6, True), star)

            operator_info = self.__get_operator(name)


            if operator_info is not None:
                
                # icon_file = f'{curr_dir}/gacha/question_mark.png'
                icon_file = None
                
                if "avatar" in operator_info:
                    if operator_info["avatar"] is not None:
                        debug_log(f"avatar icon for {name}:" + operator_info["avatar"])
                        icon_file = operator_info["avatar"]
                
                if icon_file is not None:
                    icons.append(
                        {
                            'path': icon_file,
                            'size': icon_size,
                            'pos': (side_padding, top + offset + icon_size * index),
                        }
                    )

                operators_info[name] = operator_info
                

        if times == 10:
            result_list = []

            operator_name_list = ''

            for item in operators:
                name = item['name']
                op_dt = None

                operator_name_list += f'【{name}】'

                if name in operators_info:
                    op_dt = operators_info[name]

                result_list.append(op_dt)

            reply.image(create_gacha_image(result_list))

            show_name = False
            if bot_caller is not None:
                if bot_caller['plugin_instance'] is not None:
                    show_name = bot_caller['plugin_instance'].get_config('display_operator_name')

            if show_name:
                return reply.text(f'【{get_pool_name(self.pool)}】\n{operator_name_list}\n{self.check_break_even()}')
            else:
                return reply.text(f'【{get_pool_name(self.pool)}】\n{self.check_break_even()}')
        else:
            return reply.text_image(f'{result}\n{self.check_break_even()}', icons)

    def check_break_even(self):
        break_even_rate = 98
        if self.break_even > 50:
            break_even_rate -= (self.break_even - 50) * 2

        gacha_info: UserGachaInfo = UserGachaInfo.get_or_none(user_id=self.data.user_id)

        return (
            f'当前已经抽取了 {self.break_even} 次而未获得六星干员\n'
            f'下次抽出六星干员的概率为 {100 - break_even_rate}%\n'
            f'剩余寻访凭证 {gacha_info.coupon}'
        )

    def get_rates(self):
        rates = self.rarity_range.copy()

        break_even_rate = rates[6]

        if self.break_even > 50:
            break_even_rate += (self.break_even - 50) * 2


        # 计算水位提升量
        shift_up_amount = break_even_rate - rates[6]        
        rates[6] = break_even_rate

        # 6星概率提高，其他星级概率降低，从低到高挨个扣除，直到break_even_rate扣完
        for i in range(1, 5):
            if shift_up_amount >= rates[i]:
                shift_up_amount -= rates[i]
                rates[i] = 0
            else:
                rates[i] -= shift_up_amount
                break

        return rates

    def start_gacha(self, times, coupon, point):

        '''
        抽卡核心函数，continuous_mode和detailed_mode的实际逻辑位置。
        '''

        operators = []

        for i in range(0, times):
            self.break_even += 1
            
            rates = self.get_rates()

            rates_keys = list(rates.keys())
            rates_weight = list(rates.values())

            rarity = random.choices(rates_keys, weights=rates_weight, k=1)[0]

            if rarity == 6:
                self.break_even = 0

            operator = self.choose_operator(rarity)

            operators.append({'rarity': rarity, 'name': operator})

        UserGachaInfo.update(gacha_break_even=self.break_even, coupon=UserGachaInfo.coupon - coupon).where(
            UserGachaInfo.user_id == self.data.user_id
        ).execute()

        UserInfo.update(jade_point=UserInfo.jade_point - point).where(UserInfo.user_id == self.data.user_id).execute()

        if self.pool.is_official:
            self.set_box(operators)

        return operators
    
    def choose_operator(self, rarity):
        char_pool = self.gacha_operator_pool[rarity]


        names = list(char_pool.keys())
        weights = list(char_pool.values())

        # 基于权重随机选择一个 name
        chosen_name = random.choices(names, weights=weights, k=1)[0]

        return chosen_name

    def __get_operator(self,name):
        use_official = True
        if self.pool.is_official == False:
            if hasattr(self.pool, "custom_operators"):
                if name in self.pool.custom_operators:
                    use_official = False
        
        if use_official:
            debug_log(f'使用官方干员数据{name}')
            operator_info = None
            game_data = ArknightsGameData
            if name in game_data.operators:
                    opt = game_data.operators[name]
                    operator_info = {
                        'portrait': None,
                        'rarity': opt.rarity,
                        'class': opt.classes_code.lower(),
                        'avatar': None
                    }
                    portrait_path = f'resource/gamedata/portrait/{opt.id}#1.png'
                    avatar_path = f'resource/gamedata/avatar/{opt.id}#1.png'
                    if os.path.exists(avatar_path):
                        debug_log(f'找到官方干员图标{avatar_path}')
                        operator_info["avatar"] = avatar_path
                    if os.path.exists(portrait_path):
                        debug_log(f'找到官方干员肖像{portrait_path}')
                        operator_info["portrait"] = portrait_path
            return operator_info
        else:
            debug_log(f'使用自定义干员数据{name}')
            oper_dict = self.pool.custom_operators
            if name in oper_dict:
                opt = oper_dict[name]
                operator_info = {
                    'portrait': None,
                    'rarity': opt.rarity,
                    'class': opt.classes_code.lower(),
                    'avatar': None
                }
                if opt.portrait is not None:
                    debug_log(f'找到自定义干员肖像{opt.portrait}')
                    operator_info["portrait"] = opt.portrait
                if opt.avatar is not None:
                    debug_log(f'找到自定义干员图标{opt.avatar}')
                    operator_info["avatar"] = opt.avatar
                return operator_info
            else:
                return None

    def set_box(self, result):
        user_box: OperatorBox = OperatorBox.get_or_create(user_id=self.data.user_id)[0]
        box_map = {}

        if user_box.operator:
            for n in user_box.operator.split('|'):
                n = n.split(':')
                box_map[n[0]] = [n[0], int(n[1]), int(n[2])]

        for item in result:
            name = item['name']

            if name in box_map:
                box_map[name][2] += 1
            else:
                box_map[name] = [name, item['rarity'], 1]

        box_res = '|'.join([':'.join([str(i) for i in item]) for n, item in box_map.items()])

        OperatorBox.update(operator=box_res).where(OperatorBox.user_id == self.data.user_id).execute()



