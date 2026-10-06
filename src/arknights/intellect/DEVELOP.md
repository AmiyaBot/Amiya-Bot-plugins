# intellect 开发说明

记录玩家当前理智并推算回满时间，到点主动推送提醒
（`pluginsDev/src/arknights/intellect/main.py:50-58`）。

## 使用指引

- 同目录 [README.md](README.md)：面向用户的使用指引，由 `document=f'{curr_dir}/README.md'` 加载
  （`intellect/main.py:56`），用户发送宿主 `功能` / `帮助` 指令时可见。**勿将其当作开发文档编辑。**
- 同目录 [README_USE.md](README_USE.md)：指令用法说明，由 `instruction=f'{curr_dir}/README_USE.md'`
  加载（`intellect/main.py:57`）。
- `README_USE-public.md`：对外发布版本的用法说明，源码中未见引用。

## 插件注册信息

| 项 | 值 |
| --- | --- |
| 类 | `IntellectPluginInstance`（`intellect/main.py:26`） |
| plugin_id | `amiyabot-arknights-intellect` |
| name / version | 理智恢复提醒 / `1.6` |
| plugin_type | `official` |
| priority | 未声明 |
| Requirement | 无 |
| 消息组 | 无 |

**无配置文件**（无 `config_default.yaml` / `config_schema.json`），也没有 `install()` / `uninstall()`
钩子，不订阅 `event_bus`。

## 触发方式与指令

| 指令 / 关键词 | 匹配方式 | level | 说明 |
| --- | --- | --- | --- |
| `理智N满M` / `多少理智` | `verify=verify` | 5 | 记录与查询（`intellect/main.py:61-62`、`intellect/main.py:65`） |
| `记录真实理智` | `keywords='记录真实理智'` | 10 | 从森空岛获取真实理智（`intellect/main.py:106`） |
| 满值扫描 | `@bot.timed_task(each=10)` | — | 每 10 秒检查并推送（`intellect/main.py:132`） |

`verify`（`intellect/main.py:61-62`）：仅当消息含「理智」且（含「满」或含「多少」）时返回 `(True, 5)`。

## 文件结构

| 文件 | 作用 |
| --- | --- |
| `main.py` | 全部实现：`Intellect` 表、`set_record`、`verify`、两个处理器、定时任务（143 行） |
| `logo.png` | 插件图标 |
| `README.md` / `README_USE.md` / `README_USE-public.md` | 用户可见文档，见上 |
| `__init__.py` | `from .main import bot` |

## 数据表

`@table class Intellect(UserBaseModel)`（`intellect/main.py:13-23`）：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `user_id` | `CharField(primary_key=True)` | 用户 ID |
| `belong_id` | `CharField` | 机器人实例 appid |
| `cur_num` | `IntegerField` | 记录时的当前理智 |
| `full_num` | `IntegerField` | 理智上限 |
| `full_time` | `IntegerField` | 预计回满时间戳 |
| `message_type` | `CharField` | 消息类型，缺省 `'channel'` |
| `group_id` | `CharField` | 推送目标频道 |
| `in_time` | `IntegerField` | 记录时间戳 |
| `status` | `IntegerField` | 状态位，0 待推送 / 1 已推送 |

`set_record`（`intellect/main.py:27-47`）：默认 `full_time = (full_num - cur_num) * 6 * 60 + now`，
即按每 6 分钟恢复 1 点推算；记录存在则 `update`，否则 `create`。

## 核心实现

1. **群聊限制**（`intellect/main.py:67-68`）：`QQGroupBotInstance` 下直接回「该功能在群聊暂不可用」。
2. **记录理智**（`intellect/main.py:72-84`）：正则 `理智(\d+)满(\d+)` 取当前值与上限；校验
   `cur_num < 0`、`full_num <= 0`、`cur_num >= full_num`，并限制 `full_num > 135` 为非法（理智上限
   校验）。
3. **查询理智**（`intellect/main.py:86-103`）：正则列表 `['多少理智', '理智.*多少']`；按
   `through = now - in_time` 与 `restored = int(through / 360) + cur_num` 推算已恢复量（每 360 秒
   1 点）。查询条件同时限定 `user_id` 与 `belong_id`（`intellect/main.py:90`）。
4. **从森空岛读取真实理智**（`intellect/main.py:106-129`）：检查 `'amiyabot-skland' in main_bot.plugins`，
   取 `skland.get_token(user_id)` 与 `skland.get_user_info(token)`，从 `gameStatus.ap` 读 `current`、
   `max`、`completeRecoveryTime`、`lastApAddTime`；若已过回满时间则直接提示已满，否则用真实上限调用
   `set_record`。
5. **满值推送**（`intellect/main.py:132-143`）：条件为 `status == 0` 且 `full_time <= now`；先把命中
   记录 `update(status=1)` 防重复推送（`intellect/main.py:137`），再逐条通过
   `main_bot[item.belong_id].send_message(...)` 用 `Chain().at(user_id)` 主动推送，`channel_id` 取记录
   的 `group_id`（`intellect/main.py:141-143`）。

## 依赖的 core 能力

- `core.bot as main_bot`、`Message`、`Chain`、`AmiyaBotPluginInstance`（`intellect/main.py:7`）。
- `core.database.user.UserBaseModel`（`intellect/main.py:8`）。
- `amiyabot.database.*`：`@table`、`CharField` 等（`intellect/main.py:4`）。
- `amiyabot.adapters.tencent.qqGroup.QQGroupBotInstance`（`intellect/main.py:5`）。
- 标准库 `time`。

`main_bot` 是宿主全局机器人注册表，本插件用它做两件事：查其他插件实例、按 appid 取实例主动发消息。

## 写入的表 / 目录 / 缓存

表 `Intellect`（用户理智记录，含 `status` 状态位）。**无目录写入、无配置文件。**

## 与其他插件耦合

- **反向依赖 `amiyabot-skland`**：`记录真实理智` 指令通过 `main_bot.plugins['amiyabot-skland']` 取得
  插件实例并调用其 `get_token` / `get_user_info`（`intellect/main.py:108-115`）。**未声明
  `Requirement`**，缺失时回「未检测到森空岛插件，无法使用功能。」（`intellect/main.py:129`）。
- 不消费 `ArknightsGameData`，不订阅 `gameDataInitialized`。
- 通过主机器人实例的 `send_message` 主动推送，依赖记录的 `belong_id` 定位具体机器人账号。

## 打包与发布

```bash
python run_build.py --type plugins
```

产物为 `amiyabot-arknights-intellect-1.6.zip`（`{plugin_id}-{version}.zip`）。
