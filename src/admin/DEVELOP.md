# admin 插件开发说明

权限基础设施：维护管理员身份，控制机器人上下班与频道激活状态。

## 使用指引

- [README.md](README.md) — 面向用户的使用说明，由 `pluginsDev/src/admin/main.py:17` 的 `document=` 参数加载，宿主的 `功能`/`帮助` 指令会把它渲染给用户看。
- [README-public.md](README-public.md) — 公开机器人场景下的对应版本，由 `func` 插件按机器人是否为公开实例自动改选（`pluginsDev/src/func/main.py:207-213`）。

本文件是开发者文档，不面向用户。

## 触发方式与指令

| 指令/关键词 | 匹配方式 | 说明 |
|------------|---------|------|
| `工作`、`上班` | `keywords=['工作','上班']` | 群打卡上班（`pluginsDev/src/admin/main.py:34`） |
| `休息`、`下班` | `keywords=['休息','下班']` | 群打卡下班（`pluginsDev/src/admin/main.py:56`） |
| `频道信息` | `keywords=Equal('频道信息')` 精确匹配 | 回显用户/频道/子频道 ID（`pluginsDev/src/admin/main.py:81-88`） |

均未指定 `level`，使用默认等级。

## 文件结构

| 文件 | 作用 |
|------|------|
| `__init__.py` | 一行 `from .main import bot`，插件包入口 |
| `main.py` | 全部实现：`bot` 实例、3 个消息处理器、2 个钩子 |
| `README.md` / `README-public.md` | 对用户展示的使用指引 |
| `logo.png` | 插件图标，打包时 base64 写入 `plugins.json` |

## 核心实现

用框架的 `PluginInstance` 而非 `core.AmiyaBotPluginInstance`，因为不需要配置读写（`pluginsDev/src/admin/main.py:11-18`）。

- `@bot.message_created`（`pluginsDev/src/admin/main.py:21-24`）：若 `data.is_admin` 为假，用 `Admin.get_or_none(account=data.user_id)` 查询并回填。这是全项目 `data.is_admin` 的赋权点。
- `@bot.message_before_handle`（`pluginsDev/src/admin/main.py:27-31`）：频道未被激活（`check_group_active` 为假）时，只放行管理员发送的「工作/上班」消息，其余返回 `False` 阻断；频道已激活则一律返回 `True`。
- **上班**（`pluginsDev/src/admin/main.py:39-53`）：`GroupActive.get_or_create(group_id=data.channel_id)`。若 `active == 0`，计算休眠秒数 `now - sleep_time`，用 `TimeRecorder.calc_time_total` 格式化；秒数 `< 600` 用「才」否则「一共」；`< 21600`（6 小时）追加「博士真是太过分了！」否则追加关怀文案；随后 `GroupActive.update(active=1, sleep_time=0)`。已 `active == 1` 时回复「阿米娅没有偷懒哦博士」。
- **下班**（`pluginsDev/src/admin/main.py:63-78`）：`active == 1` 时置 `active=0, sleep_time=now` 并回复打卡成功；否则按已休息时长分支：`60 < seconds < 21600` 回「（阿米娅似乎已经睡着了...）」（`at=False`，避免打扰）；`< 60` 回已下班；其余回已休息 `total`。
- **频道信息**（`pluginsDev/src/admin/main.py:83-88`）：拼接 `user_id` / `guild_id` / `channel_id`，若 `data.at_target` 非空再追加被 @ 的用户 ID。

## 依赖的 core 能力

`core.util.TimeRecorder`、`core.util.any_match`（`pluginsDev/src/admin/main.py:6`）；`core.database.bot.Admin`（`pluginsDev/src/admin/main.py:7`）；`core.database.group.GroupActive`、`check_group_active`（`pluginsDev/src/admin/main.py:8`）。

## 写入的表/目录

表 `GroupActive`（更新 `active`、`sleep_time`，`pluginsDev/src/admin/main.py:50,64-66`）。无配置文件，无目录写入。

## 与其他插件耦合

`admin` 是被依赖方。它设置的 `data.is_admin` 被 `func`（`pluginsDev/src/func/main.py:125,165`）、`replace`（`pluginsDev/src/replace/main.py:120`）、`weibo`（`pluginsDev/src/weibo/main.py:433,459`）、`arknights/gacha`（`pluginsDev/src/arknights/gacha/main.py:356`）等读取。其 `message_before_handle` 同时管控所有插件在未激活频道的可用性。

## 打包与发布

| 项 | 值 |
|----|----|
| plugin_id | `amiyabot-admin` |
| version | `1.6` |
| 产物 | `amiyabot-admin-1.6.zip` |

元数据定义于 `pluginsDev/src/admin/main.py:11-18`。打包用 `python run_build.py --type plugins`，产出到 `plugins/`。
