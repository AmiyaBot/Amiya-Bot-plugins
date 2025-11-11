import json
import asyncio
import websockets

from typing import Dict, List
from amiyabot.log import LoggerManager

logger = LoggerManager('WeiBo')


class WeiboWebSocketManager:
    """WebSocket管理器，用于处理微博实时更新"""

    def __init__(self, config_provider=None):
        self.websocket = None
        self.config_provider = config_provider
        self.ws_url = 'wss://cdn.amiyabot.com/api/v1/weibo/ws'  # 默认URL
        self.token = ''
        self.connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5
        # 回调字典：key为消息type，value为对应回调函数列表；None表示接收所有类型
        self.message_callbacks = {}
        self.user_ids = []

        # 从配置中加载WebSocket设置
        self._load_config()

    def _load_config(self):
        """从配置中加载WebSocket设置"""
        if self.config_provider:
            try:
                websocket_config = self.config_provider.get_config('websocket') or {}
                self.ws_url = websocket_config.get('url', self.ws_url)
                self.token = websocket_config.get('token', '')
                self.max_reconnect_attempts = websocket_config.get(
                    'reconnectAttempts', self.max_reconnect_attempts
                )
                self.reconnect_delay = websocket_config.get(
                    'reconnectDelay', self.reconnect_delay
                )
                listen: List[Dict[str, str]] = self.config_provider.get_config(
                    'listen'
                ) or []
                self.user_ids = [item['uid'] for item in listen if 'uid' in item]

                if not self.token:
                    logger.warning("WebSocket token未配置，可能影响连接")
            except Exception as e:
                logger.error(f"加载WebSocket配置失败: {e}")

    async def connect(self):
        """连接到WebSocket服务器"""
        listen: List[Dict[str, str]] = (
                self.config_provider.get_config('listen') or []
            )
        user_ids = [item['uid'] for item in listen if 'uid' in item]
        if self.connected:
            if set(user_ids) == set(self.user_ids):
                return  # 已连接且订阅用户未变，无需重新连接
            else:
                self.user_ids = user_ids
                await self.subscribe_users(user_ids)
            return

        try:
            token = self.config_provider.get_config('websocket').get('token', '') if self.config_provider else ''
            if token:
                self.token = token
                # 使用token作为查询参数
                url = f"{self.ws_url}?token={self.token}"
            else:
                return  # 如果没有token，直接返回不连接

            self.websocket = await websockets.connect(url)
            self.connected = True
            self.reconnect_attempts = 0

            # 启动消息监听任务
            asyncio.create_task(self._listen_messages())
            if user_ids:
                await self.subscribe_users(user_ids)

        except Exception as e:
            await self._handle_reconnect()

    async def _listen_messages(self):
        """监听WebSocket消息，按type分发到对应回调"""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                msg_type = data.get('type') if isinstance(data, dict) else None

                # 获取特定type和全局(None)的回调
                callbacks_specific = self.message_callbacks.get(msg_type, [])
                callbacks_all = self.message_callbacks.get(None, [])

                # 先执行特定再执行全局
                for callback in callbacks_specific + callbacks_all:
                    await callback(data)

        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket连接关闭，尝试重连...")
            self.connected = False
            await self._handle_reconnect()
        except Exception as e:
            logger.error(f"WebSocket监听出错: {e}")
            self.connected = False
            await self._handle_reconnect()

    async def _handle_reconnect(self):
        """处理重连逻辑"""
        if self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            logger.info(f"尝试重连 {self.reconnect_attempts}/{self.max_reconnect_attempts}...")
            await asyncio.sleep(self.reconnect_delay)
            await self.connect()
        else:
            logger.error("重连次数已达上限，停止重连")

    async def subscribe_users(self, user_ids):
        """订阅特定用户"""
        if not self.connected:
            await self.connect(user_ids)
        else:
            # 发送订阅消息
            if self.websocket:
                subscribe_msg = {"type": "subscribe", "user_ids": user_ids}
                await self.websocket.send(json.dumps(subscribe_msg))

    def register_message_handler(self, type=None):
        """装饰器：注册消息回调函数，可指定type类型

        使用示例：

        @manager.register_message_handler()        # 收到所有消息
        async def handle_all(msg): ...

        @manager.register_message_handler('update') # 仅处理type为'update'
        async def handle_update(msg): ...
        """

        def decorator(func):
            callbacks = self.message_callbacks.setdefault(type, [])
            callbacks.append(func)
            return func

        return decorator

    async def close(self):
        """关闭WebSocket连接"""
        if self.websocket:
            await self.websocket.close()
        self.connected = False
