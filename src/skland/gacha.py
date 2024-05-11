import datetime
import json
from urllib import parse
from amiyabot.network.httpRequests import http_requests
import hashlib
from .api import SKLandAPI, log

async def get_gacha_official(server_name,token):
    url = ''
    list = []
    pool_list = []
    for page in range(1, 10):
        if server_name == "bilibili服":
            url = 'https://ak.hypergryph.com/user/api/inquiry/gacha?page=' + str(page) + '&channelId=2&token=' + parse.quote(token)
        else:
            url = 'https://ak.hypergryph.com/user/api/inquiry/gacha?page=' + str(page) + '&token=' + parse.quote(token)

        res = await http_requests.get(url)
        result = json.loads(res)

        if result['code'] != 0:
            return None,None

        for obj in result['data']['list']:
            pool_name = obj['pool']
            time_stamp = obj['ts']
            if pool_name not in pool_list:
                pool_list.append(pool_name)
            for o in range(len(obj['chars']) - 1, -1, -1):
                list.append({
                    'poolName': pool_name,
                    'timeStamp': time_stamp,
                    'isNew': str(obj['chars'][o]['isNew']),
                    'name': obj['chars'][o]['name'],
                    'star': obj['chars'][o]['rarity'] + 1
                })
    return list,pool_list

def arkgacha_kwer_top_sign_req_data(req_data,app_secret):
    sign_str = "&".join([f"{key}={value}" for key, value in sorted(req_data.items())])
    sign_str += f"&appsecret={app_secret}"
    req_data['sign'] = hashlib.sha256(sign_str.encode()).hexdigest()
    return req_data

async def get_gacha_arkgacha_kwer_top(server_name,token,appid,appsecret):
    url = 'https://arkgacha.kwer.top/api?appid=' + parse.quote(appid)

    payload = arkgacha_kwer_top_sign_req_data({'cmd': 'sync', 'token': token}, appsecret)

    res = await http_requests.post(url, payload=payload)
    result = json.loads(res)

    if result['code'] != 200:
        return None,None

    private_uid = result['privateUid']

    url = f'https://arkgacha.kwer.top/rawData?privateUid={private_uid}&fileType=gacha&rspType=json'

    res = await http_requests.get(url)
    result:dict = json.loads(res)

    if 'data' not in result.keys():
        return None,None
    
    list = []
    pool_list = []

    # 只接受60天内的数据
    current_timestamp = datetime.datetime.now().timestamp()

    log.info(f"current_timestamp:{current_timestamp}")

    for timestamp in result['data'].keys():
        if int(timestamp) < current_timestamp - 60*24*60*60:
            continue
        for obj in result['data'][timestamp]['c']:
            pool_name = result['data'][timestamp]['p']
            if pool_name == '常驻标准寻访':
                pool_name = '常驻标准寻访(60天内)'

            if pool_name not in [x['pool_name'] for x in pool_list]:
                pool_list.append(
                    {'pool_name':pool_name,'last_time':timestamp}
                )

            list.append({
                'poolName': pool_name,
                'timeStamp': timestamp,
                # 'isNew': obj[2]==1?'true':'false'
                'isNew': str(obj[2]==1),
                'name': obj[0],
                'star': obj[1]+1
            })
            # compare with the last time
            if pool_name in pool_list:
                if pool_list[pool_name]['last_time'] < timestamp:
                    pool_list[pool_name]['last_time'] = timestamp

    # pick last 4 pool
    pool_list = sorted(pool_list,key=lambda x:x['last_time'],reverse=True)[:4]

    # 从list中踹掉不在pool_list中的数据
    list = [x for x in list if x['poolName'] in [x['pool_name'] for x in pool_list]]

    pool_name_list = [x['pool_name'] for x in pool_list]

    # 临时输出list和pool_name_list
    log.info(f"list:{list}")
    log.info(f"pool_name_list:{pool_name_list}")

    return list,pool_name_list


