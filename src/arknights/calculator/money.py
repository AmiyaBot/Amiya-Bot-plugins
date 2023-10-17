from typing import List, Dict, Tuple
from dataclasses import dataclass

# 招聘单价，第一个为 1小时0分钟，第二个为 1小时10分钟，以此类推到 9小时
recruit_prices = [
    140,
    143,
    147,
    150,
    154,
    157,
    161,
    164,
    168,
    171,
    175,
    178,
    182,
    185,
    189,
    192,
    196,
    199,
    203,
    245,
    252,
    259,
    266,
    273,
    280,
    287,
    294,
    301,
    308,
    315,
    322,
    329,
    336,
    343,
    350,
    357,
    364,
    371,
    378,
    385,
    490,
    504,
    518,
    532,
    546,
    560,
    574,
    588,
    602,
]


# 小时分钟选几个 tag 等于多少钱
@dataclass
class Recruit:
    hour: int
    minute: int
    tags: int
    price: int


def calc_money(money: int):
    mutable_list: List[Recruit] = []
    minute = 60
    # 把每个不同时间的招聘单价都丢进去
    for price in recruit_prices:
        mutable_list.append(Recruit(minute // 60, minute % 60, 0, price))
        minute += 10

    mutable_list2: List[Recruit] = []
    # 再把每个时间拼 1-3 个 tag 的招聘单价都丢进去
    for recruit in mutable_list:
        for tag in range(4):
            mutable_list2.append(Recruit(recruit.hour, recruit.minute, tag, recruit.price + tag * 70))

    # 得到了一个完整的招聘单价列表
    # for item in mutable_list2:
    #     print(f'公招{item.hour}小时{item.minute}分钟，选{item.tags}个tag需要{item.price}龙门币')

    # 把招聘单价列表转成 map，方便后面查找
    recruit_map: Dict[int, Recruit] = {item.price: item for item in mutable_list2}
    array: List[int] = [n.price for n in sorted(mutable_list2, key=lambda x: x.price)]

    # 初始化完成，下面是计算过程
    # 凑硬币算法，参考 https://leetcode-cn.com/problems/coin-change/solution/322-ling-qian-dui-huan-by-leetcode-solution/
    # 区别就是这里需要记录每个硬币的招聘配置
    result: Tuple[int, List[int]] = coin_change(array, money, [0] * money, [[] for _ in range(money)])
    if result[0] == -1:
        return f'博士，无法凑出花费 {money} 龙门币的计划'
    else:
        if result[0] > 10:
            return f'博士，花费这个数额的计划比较长，请分开计算吧'

        text = f'博士，把 {money} 龙门币刚好花完，推荐 {result[0]} 次公招，分别是以下配置：\n\n'
        for index in result[1]:
            item = recruit_map[index]
            text += f'{item.hour} 小时 {item.minute} 分钟，选 {item.tags} 个tag，花费 {item.price} 龙门币；\n'

        return text


def coin_change(coins: List[int], rem: int, count: List[int], money_list: List[List[int]]) -> Tuple[int, List[int]]:
    if rem < 0:
        return -1, []

    if rem == 0:
        return 0, []

    if count[rem - 1] != 0:
        return count[rem - 1], money_list[rem - 1]

    min_val = float('inf')
    min_list = []

    for coin in coins:
        res = coin_change(coins, rem - coin, count, money_list)
        if 0 <= res[0] <= min_val:
            min_val = 1 + res[0]
            min_list = res[1] + [coin]

    count[rem - 1] = -1 if min_val == float('inf') else min_val
    money_list[rem - 1] = [] if min_val == float('inf') else min_list

    return count[rem - 1], money_list[rem - 1]
