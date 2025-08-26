import re
import os
import time

from dataclasses import dataclass, field
from amiyabot.network.download import download_async
from amiyabot.network.httpRequests import http_requests
from core.util import remove_xml_tag, char_seat, create_dir
from amiyabot.builtin.lib.browserService import basic_browser_service

ua = None
try:
    from fake_useragent import UserAgent

    ua = UserAgent()
except:
    pass


@dataclass
class WeiboContent:
    user_name: str
    html_text: str = ''
    detail_url: str = ''
    pics_list: list = field(default_factory=list)
    pics_urls: list = field(default_factory=list)


class WeiboUser:
    cookie = None  # 静态变量存储weibo cookie
    
    def __init__(self, weibo_id, setting):
        self.headers = {
            'User-Agent': (
                ua.random
                if ua
                else 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36'
            ),
            'Content-Type': 'application/json; charset=utf-8',
            'Referer': f'https://m.weibo.cn/u/{weibo_id}',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        self.url = 'https://m.weibo.cn/api/container/getIndex'
        self.weibo_id = weibo_id
        self.setting = setting
        self.user_name = ''

    async def get_result(self, url):
        if WeiboUser.cookie == None:
            await WeiboUser.generate_cookie()
        
        # 更新或向headers中加入cookie
        if WeiboUser.cookie:
            cookie_str = '; '.join([f"{cookie['name']}={cookie['value']}" for cookie in WeiboUser.cookie])
            self.headers['Cookie'] = cookie_str
        res = await http_requests.get(url, headers=self.headers)
        if res and res.response.status == 200:
            return res.json
        
        # 失败则重新获取cookie并更新headers
        await WeiboUser.generate_cookie()
        if WeiboUser.cookie:
            cookie_str = '; '.join([f"{cookie['name']}={cookie['value']}" for cookie in WeiboUser.cookie])
            self.headers['Cookie'] = cookie_str
            # 重新请求
            res = await http_requests.get(url, headers=self.headers)
            if res and res.response.status == 200:
                return res.json

    def __url(self, container_id=None):
        c_id = f'&containerid={container_id}' if container_id else ''
        return f'{self.url}?type=uid&uid={self.weibo_id}&value={self.weibo_id}{c_id}'

    async def get_user_name(self, result=None):
        if self.user_name:
            return self.user_name

        if not result:
            result = await self.get_result(self.__url())
            if not result:
                return self.user_name

        if 'userInfo' not in result['data']:
            return self.user_name

        self.user_name = result['data']['userInfo']['screen_name']

        return self.user_name

    async def get_cards_list(self):
        cards = []

        # 获取微博 container id
        result = await self.get_result(self.__url())
        if not result:
            return cards

        if 'tabsInfo' not in result['data']:
            return cards

        await self.get_user_name(result)

        tabs = result['data']['tabsInfo']['tabs']
        container_id = ''
        for tab in tabs:
            if tab['tabKey'] == 'weibo':
                container_id = tab['containerid']

        # 获取正文列表
        result = await self.get_result(self.__url(container_id))
        if not result:
            return cards

        for item in result['data']['cards']:
            if item['card_type'] == 9 and 'isTop' not in item['mblog'] and item['mblog']['mblogtype'] == 0:
                cards.append(item)

        return cards

    async def get_blog_list(self):
        cards = await self.get_cards_list()

        blog_list = []
        for index, item in enumerate(cards):
            detail = remove_xml_tag(item['mblog']['text']).replace('\n', ' ').strip()
            length = 0
            content = ''
            for char in detail:
                content += char
                length += char_seat(char)
                if length >= 32:
                    content += '...'
                    break

            date = item['mblog']['created_at']
            date = time.strptime(date, '%a %b %d %H:%M:%S +0800 %Y')
            date = time.strftime('%Y-%m-%d %H:%M:%S', date)

            blog_list.append({'index': index + 1, 'date': date, 'content': content})

        return blog_list

    async def get_weibo_id(self, index: int):
        cards = await self.get_cards_list()
        if cards:
            return cards[index]['itemid']

    async def get_weibo_content(self, index: int):
        cards = await self.get_cards_list()

        if index >= len(cards):
            index = len(cards) - 1

        target_blog = cards[index]
        blog = target_blog['mblog']

        # 获取完整正文
        result = await self.get_result('https://m.weibo.cn/statuses/extend?id=' + blog['id'])
        if not result:
            return None

        content = WeiboContent(self.user_name)

        text = result['data']['longTextContent']
        text = re.sub('<br />', '\n', text)
        text = remove_xml_tag(text)

        content.html_text = text.strip('\n')
        content.detail_url = target_blog['scheme']

        # 获取静态图片列表
        pics = blog['pics'] if 'pics' in blog else []

        for pic in pics:
            pic_url = pic['large']['url']
            name = pic_url.split('/')[-1]
            suffix = name.split('.')[-1]

            if suffix.lower() == 'gif' and not self.setting.sendGIF:
                continue

            path = f'{self.setting.imagesCache}/{name}'
            create_dir(path, is_file=True)

            if not os.path.exists(path):
                stream = await download_async(pic_url, headers=self.headers)
                if stream:
                    open(path, 'wb').write(stream)

            content.pics_list.append(path)
            content.pics_urls.append(pic_url)

        return content

    @staticmethod
    async def generate_cookie() -> None:
        browser = basic_browser_service.browser
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            await page.goto("https://weibo.com")
            # 等待页面加载5秒
            await page.wait_for_timeout(5000)
            
            # 获取所有cookie
            cookies = await context.cookies()
            
            # 过滤所有domain为weibo.com的cookie
            weibo_cookies = [cookie for cookie in cookies if cookie.get('domain') == '.weibo.com' or cookie.get('domain') == 'weibo.com']
            
            # 存储到静态变量
            WeiboUser.cookie = weibo_cookies
        except Exception as e:
            print(f"获取cookie时发生错误: {e}")
            return None
        finally:
            await page.close()
            await context.close()
