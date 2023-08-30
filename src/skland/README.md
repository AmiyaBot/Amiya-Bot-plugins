## 说明

调用森空岛 API 查询玩家信息展示游戏数据，需要用户绑定 Token。

## 插件联动

- 展示用户助理信息时需要游戏资源，须安装[《明日方舟数据解析》](/#/shop)插件。
- 可与官方插件[《理智恢复提醒》](/#/shop)联动，若同时安装了此插件，将解锁游戏内的真实理智提醒功能。

## 安装 opencv 依赖优化插件

<span style="color: red">仅限代码部署！</span><br>
安装依赖后，部分功能将会对干员立绘位置进行优化。

```bash
pip install opencv-python
```

## 提供给第三方插件的 API

森空岛插件实例提供了可给第三方插件调用的 API，通过主实例获取插件，即可开始使用。

```python
from core import bot as main_bot


async def example():
    # 获取插件
    if 'amiyabot-skland' in main_bot.plugins:
        plugin = main_bot.plugins['amiyabot-skland']

        token: Optional[str] = await plugin.get_token(user_id)
        user_info: Optional[dict] = await plugin.get_user_info(token)
```

### get_token

获取绑定的 Token

| 参数名     | 类型  | 释义   | 默认值 |
|---------|-----|------|-----|
| user_id | str | 用户ID |     |

### get_user_info

获取玩家通用信息

| 参数名   | 类型  | 释义    | 默认值 |
|-------|-----|-------|-----|
| token | str | Token |     |

### get_character_info

获取游戏角色信息

| 参数名   | 类型  | 释义             | 默认值 |
|-------|-----|----------------|-----|
| token | str | Token          |     |
| uid   | str | 要获取数据的游戏内角色UID |     |
