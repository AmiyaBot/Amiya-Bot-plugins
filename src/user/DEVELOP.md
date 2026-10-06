# user 插件开发说明

兔兔互动：日常交互层，含签到、好感度、问候、昵称与戳一戳。

## 使用指引

- [README.md](README.md) — 面向用户的功能说明，由 `pluginsDev/src/user/mainBot.py:35` 的 `document=` 参数加载。
- [README_USE.md](README_USE.md) — 详细使用指引，由 `pluginsDev/src/user/mainBot.py:36` 的 `instruction=` 参数加载。
- [README_USE-public.md](README_USE-public.md) — 公开机器人场景下的对应版本。

宿主的 `功能`/`帮助` 指令会把上述文档渲染给用户看。本文件是开发者文档，不面向用户。

## 触发方式与指令

| 指令/关键词 | 匹配方式 | level | 说明 |
|------------|---------|-------|------|
| `昵称` / `删除昵称` | `keywords=['昵称']`，`group_id='user'` | 10 | 设置自定义昵称，≤10 字，可走百度审核（`pluginsDev/src/user/main.py:43-87`） |
| 仅 @ 机器人或喊名字 | `verify=only_name` | 2 | 回随机抚摸语或表情图（`pluginsDev/src/user/main.py:90-97`；`only_name` 定义于 `pluginsDev/src/user/mainBot.py:131-135`） |
| 正面话语 | `verify=compose_talk_verify(talking.talk.positive, talking.call.positive, 'enable_positive')` | — | 好感 +5（`pluginsDev/src/user/main.py:100-114`） |
| 负面话语 | `verify=compose_talk_verify(talking.talk.inactive, talking.call.positive, 'enable_inactive')` | — | 好感 -5，显示怒气百分比（`pluginsDev/src/user/main.py:117-131`） |
| 辱骂称呼 | `verify=check_keywords(list(talking.call.inactive), 'enable_inactive')`，`check_prefix=False` | — | 好感 -5（`pluginsDev/src/user/main.py:134-146`） |
| `我错了`/`对不起`/`抱歉` | `verify=check_keywords([...], 'enable_inactive')` | — | 好感 +5 并解锁（`pluginsDev/src/user/main.py:149-163`） |
| 问候语（早上好/早安/中午好/午安/下午好/晚上好） | `verify=check_keywords([...], 'enable_greeting')` | — | 按时段问候，并顺带签到结算（`pluginsDev/src/user/main.py:166-182`） |
| `晚安` | `verify=check_keywords(['晚安'], 'enable_greeting')` | — | 晚安回复（`pluginsDev/src/user/main.py:185-190`） |
| `签到` | `keywords=['签到']` | 默认 | 显式签到 + 展示用户信息（`pluginsDev/src/user/main.py:193-199`） |
| `我的信息`/`个人信息` | `keywords=[...]` | 默认 | 渲染个人信息 HTML（`pluginsDev/src/user/main.py:202-204`） |
| `开启戳一戳`/`关闭戳一戳` | `keywords=[...]` | 默认 | 写/删 `PokeLock`（`pluginsDev/src/user/main.py:207-214`） |
| `NudgeEvent` | `@bot.on_event`（Mirai） | — | 被戳时按 `randint(0,10)>=6` 回戳，否则回图或文字（`pluginsDev/src/user/main.py:217-223`） |
| `notice.notify.poke` | `@bot.on_event`（CQHTTP） | — | 同上逻辑（`pluginsDev/src/user/main.py:226-232`） |

除昵称外全部处理器共用 `group_id='user'`。消息组配置为 `GroupConfig('user', allow_direct=True)`（`pluginsDev/src/user/mainBot.py:40`）。

## 文件结构

| 文件/目录 | 作用 |
|-----------|------|
| `__init__.py` | 一行 `from .main import bot`，插件包入口 |
| `main.py` | 11 个消息处理器 + 2 个事件处理器 + 3 个钩子 + `PokeLock`/`UserCustom` 表定义 |
| `mainBot.py` | `bot` 实例、`sign_in` 签到、`talk_time` 时段、配置开关与 verify 工厂、`user_info` 渲染 |
| `talking.yaml` | 互动词表：`call.positive`/`call.inactive` 称呼、`talk.positive`/`talk.inactive` 句式模板 |
| `baiduCloud.yaml` | 百度云审核凭据模板，首次运行复制到 `resource/plugins/baiduCloud.yaml` |
| `config_default.yaml` | 全局配置默认值：`enable_greeting`、`enable_positive`、`enable_inactive` |
| `config_schema.json` | 全局配置 JSON Schema |
| `face/` | 15 张阿米娅表情图，`install()` 时复制到 `resource/plugins/user/face` |
| `template/` | 个人信息卡 HTML/CSS、`avatar.webp`、`user_info.jpeg`、字体、`js/`（vue、echarts、JsBarcode） |
| `README*.md` | 对用户展示的使用指引 |
| `logo.png` | 插件图标 |

## 核心实现

- `@bot.message_created`（`pluginsDev/src/user/main.py:235-241`）：用 `UserCustom.get_nickname(user_id)` 覆盖 `data.nickname`。
- `@bot.message_before_handle`（`pluginsDev/src/user/main.py:244-256`）：两级拦截 —— ① `user.user_id.black == 1`（黑名单）直接 `False`；② `user.user_mood <= 0`（好感耗尽）且不在道歉词中时，若消息 @ 了机器人或喊「兔兔/阿米娅」则回「阿米娅生气了」，并一律返回 `False`。
- `@bot.message_after_send`（`pluginsDev/src/user/main.py:259-289`）是好感度结算点。默认 `feeling = 2`，处理器可用 `setattr(reply, 'feeling', N)` 覆盖（如 ±5）；`user_mood <= 0` 且未设 `unlock` 时置 0。最终 clamp 到 `[0, 15]`，更新 `User.nickname`、`User.message_num+1`、`UserInfo.user_mood` 与 `user_feeling`。
- **签到 `sign_in`**（`pluginsDev/src/user/mainBot.py:51-81`）：以 `time.strftime('%Y-%m-%d')` 为当日标记，若 `info.sign_date != today` 则发放 50 寻访凭证 + 50 好感，并将 `user_mood` 重置为 15、`sign_times+1`、`jade_point_max=0`；同时 `UserGachaInfo.coupon += 50`。重复签到返回「今天已经签到了」。
- **怒气百分比**：`int((1 - max(user_mood-5,0)/15) * 100)`（`pluginsDev/src/user/main.py:129`）。
- **时段判断 `talk_time`**（`pluginsDev/src/user/mainBot.py:84-96`）：0–5 点返回空串（表示深夜），5–11 早上、11–14 中午、14–18 下午、18–24 晚上。
- **配置开关**（`pluginsDev/src/user/mainBot.py:99-116`）：`check_config` 读全局配置；`check_keywords` 与 `compose_talk_verify` 是两个 verify 工厂，后者用 `check_sentence_by_re(data.text, words, names)` 做句式匹配（能识别 `%s乖` 这类模板）。
- **用户信息卡 `user_info`**（`pluginsDev/src/user/mainBot.py:119-128`）：下载 `data.avatar` 转 base64 data URL，与 `UserInfo.get_user_info(user_id)` 合并后渲染 `template/userInfo.html`（宽度 700、高度 300）。模板使用 `echarts.min.js` 与 `JsBarcode.all.min.js`。
- **戳一戳**：`PokeLock` 表实际是「关闭戳一戳」的频道黑名单 —— `开启` 时 `delete()`，`关闭` 时 `create()`（`pluginsDev/src/user/main.py:209-214`），事件处理器中 `PokeLock.get_or_none(...)` 存在才响应。
- **昵称审核**（`pluginsDev/src/user/main.py:63-76`）：`baidu.enable` 为真时先 `data.send` 提示审核中，再调 `baidu.text_censor(nickname)`；`conclusionType == 2` 表示不通过并列出违规项。
- **`UserCustom.get_nickname`**（`pluginsDev/src/user/main.py:33-40`）：返回 `自定义名#4位ID后缀` 形式，ID 不足 4 位左侧补 0。

## 依赖的 core 能力

`core.Event`（`pluginsDev/src/user/main.py:6`）；`core.util.any_match`（`pluginsDev/src/user/main.py:7`，`pluginsDev/src/user/mainBot.py:11`）；`core.lib.baiduCloud.BaiduCloud`（`pluginsDev/src/user/main.py:8`，用于昵称内容审核）；`core.database.user.*`（`pluginsDev/src/user/main.py:9`）；`core.util.read_yaml`、`check_sentence_by_re`（`pluginsDev/src/user/mainBot.py:11`）；`amiyabot.GroupConfig`（`pluginsDev/src/user/mainBot.py:4`）；`amiyabot.network.download.download_async`（`pluginsDev/src/user/mainBot.py:8`）；`amiyabot.adapters` 的 `MiraiBotInstance`、`CQHttpBotInstance`（`pluginsDev/src/user/main.py:3-4`）。

## 写入的表/目录

| 表 | 内容 |
|----|------|
| `PokeLock` | 关闭戳一戳的频道黑名单，字段 `group_id`（`pluginsDev/src/user/main.py:23-25`） |
| `UserCustom` | 用户自定义昵称，字段 `user_id`、`custom_nickname`（`pluginsDev/src/user/main.py:28-40`） |

并更新 core 的 `User`、`UserInfo`、`UserGachaInfo`。

目录：`install()` 复制 `face/` 到 `resource/plugins/user/face`（`pluginsDev/src/user/mainBot.py:21-23`），`uninstall()` 会 `shutil.rmtree` 该目录（`pluginsDev/src/user/mainBot.py:25-26`）；首次运行复制 `baiduCloud.yaml` 到 `resource/plugins/baiduCloud.yaml`（`pluginsDev/src/user/main.py:16-18`）。

## 与其他插件耦合

- 读取 `talking.yaml` 中的 `call` / `talk` 词表（`pluginsDev/src/user/mainBot.py:17`），并在 `pluginsDev/src/user/main.py:100-152` 中大量使用 `talking.talk.positive` 等。
- 与 `talking` 插件共用 face 目录（见上）。
- 签到的奖励发放到 `UserGachaInfo.coupon`，即直接给 `arknights/gacha` 的抽卡凭证充值（`pluginsDev/src/user/mainBot.py:68-71`）。
- 与 `game/guess`、`game/wordle2` 共享 `UserInfo` 的合成玉账户。

## 打包与发布

| 项 | 值 |
|----|----|
| plugin_id | `amiyabot-user` |
| version | `3.2` |
| 产物 | `amiyabot-user-3.2.zip` |

元数据定义于 `pluginsDev/src/user/mainBot.py:29-39`。打包用 `python run_build.py --type plugins`，产出到 `plugins/`。
