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

    # { "data": {
    # "1712858630": { // timestamp
    #     "c": [
    #         [
    #             "维荻",
    #             3,
    #             0
    #         ]
    #     ],
    #     "p": "常驻标准寻访"
    # }
    # }}

    log.info(f'{result}')

    if result['code'] != 200:
        return None,None
    
    list = []
    pool_list = []
    for timestamp in result['data'].keys():
        for obj in result['data'][timestamp]['c']:
            pool_name = result['data'][timestamp]['p']
            if pool_name not in pool_list:
                pool_list.append(pool_name)
            list.append({
                'poolName': pool_name,
                'timeStamp': timestamp,
                # 'isNew': obj[2]==1?'true':'false'
                'isNew': str(obj[2]==1),
                'name': obj[0],
                'star': obj[1]+1
            })

    return list,pool_list


