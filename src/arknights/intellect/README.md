## 插件联动

- 可与官方插件[《森空岛》](/#/shop)联动，若同时安装了此插件，将解锁游戏内的真实理智提醒功能。

## 提供给第三方插件的 API

理智恢复提醒插件实例提供了可给第三方插件调用的 API，用过主实例获取插件，即可开始使用。

```python
from core import bot as main_bot


async def example():
    # 获取插件
    if 'amiyabot-arknights-intellect' in main_bot.plugins:
        plugin = main_bot.plugins['amiyabot-arknights-intellect']

        plugin.set_record(data, cur_num, full_num)
```

### set_record

记录理智提醒

| 参数名       | 类型      | 释义         | 默认值 |
|-----------|---------|------------|-----|
| data      | Message | Message 对象 |     |
| cur_num   | int     | 当前理智量      |     |
| full_num  | int     | 满理智量       |     |
| full_time | int     | 预计恢复满需要的时间 |     |
