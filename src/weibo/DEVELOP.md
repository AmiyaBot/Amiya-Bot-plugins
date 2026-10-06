# weibo 插件开发说明

微博推送：通过官方 WebSocket 长连接接收明日方舟官微更新，推送到已订阅的群/频道。

## 使用指引

- [README.md](README.md) — 面向用户的功能说明，由 `pluginsDev/src/weibo/main.py:46` 的 `document=` 参数加载。
- [README_USE.md](README_USE.md) — 详细使用指引，由 `pluginsDev/src/weibo/main.py:47` 的 `instruction=` 参数加载。
- [README_USE-public.md](README_USE-public.md) — 公开机器人场景下的对应版本。

宿主的 `功能`/`帮助` 指令会把上述文档渲染给用户看。本文件是开发者文档，不面向用户。

## 触发方式与指令

| 指令/关键词 | 匹配方式 | 说明 |
|------------|---------|------|
| `开启微博推送` | `group_id='weibo'`，`keywords=[...]` | 需管理员；QQ 群聊不支持（`pluginsDev/src/weibo/main.py:428-454`） |
| `关闭微博推送` | `group_id='weibo'` | 需管理员（`pluginsDev/src/weibo/main.py:457-467`） |
| `微博` | `group_id='weibo'` | 查询历史微博，可按用户名/序号筛选（`pluginsDev/src/weibo/main.py:470-547`） |
| 连接保活 | `@bot.timed_task(each=10)` | 维持 WebSocket 连接（`pluginsDev/src/weibo/main.py:550-552`） |
| 缓存清理 | `@bot.timed_task(trigger='cron', hour=0)` | 每天 0 点清理 `cacheRetentionDays` 天前的图片（`pluginsDev/src/weibo/main.py:555-567`） |

## 文件结构

| 文件 | 作用 |
|------|------|
| `__init__.py` | 一行 `from .main import bot`，插件包入口 |
| `main.py` | `bot` 实例、`WeiboRecord` 表、图片拼接工具、推送流程、3 个处理器与 2 个定时任务 |
| `helper.py` | `WeiboWebSocketManager`：连接、订阅、消息分发、重连 |
| `config_default.yaml` | 全局配置默认值：`setting`、`websocket`、`sendInterval`、`sendAsync`、`listen`、`block` |
| `config_schema.json` | 全局配置 JSON Schema |
| `README*.md` | 对用户展示的使用指引 |
| `logo.png` | 插件图标 |

## 核心实现

1. **WebSocket 管理器 `WeiboWebSocketManager`**（`pluginsDev/src/weibo/helper.py:12-255`）：
   - 默认 URL `wss://cdn.amiyabot.com/api/v1/weibo/ws`（`pluginsDev/src/weibo/helper.py:18`），实际从配置 `websocket.url` 读取（`pluginsDev/src/weibo/helper.py:42`）。
   - 无 token 时直接不连接（`pluginsDev/src/weibo/helper.py:129-136`），仅记录 warning。
   - `connect(skip=True)` 支持非阻塞连接：用 `asyncio.wait_for(lock.acquire(), timeout=0.01)` 实现「拿不到锁就跳过」（`pluginsDev/src/weibo/helper.py:90-95`），避免定时任务堆积；连接前先比对订阅用户集合是否变化，未变则直接返回（`pluginsDev/src/weibo/helper.py:72-81`）。
   - 连接成功后 `asyncio.create_task(self._listen_messages())` 并发送 `{"type":"subscribe","user_ids":[...]}`（`pluginsDev/src/weibo/helper.py:144,229-230`）。
   - 消息按 `type` 分发到回调：`message_callbacks.get(msg_type, [])` 与全局 `None` 两个列表（`pluginsDev/src/weibo/helper.py:174-179`）。
   - 重连 `_handle_reconnect`：最多 `max_reconnect_attempts`（默认 5）次，每次间隔 `reconnect_delay`（默认 5 秒）（`pluginsDev/src/weibo/helper.py:188-212`）。
2. **回调注册**（`pluginsDev/src/weibo/main.py:210-223`）：`@ws_manager.register_message_handler("historical_weibos")`，把处理丢进 `asyncio.create_task(process_weibo_data(...))`，避免阻塞 WebSocket 收包循环。通过 `'task_id' not in data` 判断是否为订阅建立时的历史微博（`pluginsDev/src/weibo/main.py:220`）。
3. **推送流程 `process_weibo_data`**（`pluginsDev/src/weibo/main.py:226-372`）：
   - 查询 `GroupSetting.send_weibo == 1` 的目标群（`pluginsDev/src/weibo/main.py:230-232`）。
   - 遍历 `recent_weibos`，用 `WeiboRecord.get_or_none(blog_id=...)` 去重（`pluginsDev/src/weibo/main.py:248-249`）。
   - 图片下载到 `Path.cwd() / setting['imagesCache']`（默认 `logs/weibo`），URL 模板 `https://cdn.amiyabot.com/api/v1/weibo/pic/{index}/{file}`，已存在则跳过下载（`pluginsDev/src/weibo/main.py:266-278`）；`sendGIF=false` 时跳过 gif（`pluginsDev/src/weibo/main.py:259-263`）。
   - 写入 `WeiboRecord`（`pluginsDev/src/weibo/main.py:284-293`）。
   - 推送前用配置 `block` 正则列表匹配正文，命中则跳过并上报控制台（`pluginsDev/src/weibo/main.py:310-324`）。
   - 推送时按实例类型分支：`QQGuildBotInstance` 只发图，其他平台追加详情 URL（`pluginsDev/src/weibo/main.py:349-352`）。
   - `sendAsync` 控制并发发送（`asyncio.wait`）还是串行发送（每群间隔 `sendInterval`，默认 0.2 秒）（`pluginsDev/src/weibo/main.py:354-363`）。
4. **图片拼接**（`pluginsDev/src/weibo/main.py:98-207`）：
   - `_read_image_sizes` 读取前 N 张图尺寸；`_select_uniform_count` 从 9/6/3 中选出「前 N 张尺寸完全一致」的最大 N（`pluginsDev/src/weibo/main.py:112-120`）。
   - `build_square_uniform_grid`：仅当该 N 张图都是正方形且同尺寸时，合并为 3 列网格图，输出 `{blog_id}_grid_{count}.jpg`（`pluginsDev/src/weibo/main.py:170-207`）。
   - `build_three_strips_for_prefix`：把 3n 张图合并成多个 1×3 横条，输出 `{blog_id}_strip_{n}.jpg`（`pluginsDev/src/weibo/main.py:140-167`）。
   - 实际推送路径只调用了 `build_square_uniform_grid`（`pluginsDev/src/weibo/main.py:332,406`）。
5. **历史查询**（`pluginsDev/src/weibo/main.py:470-547`）：`listen` 配置项按名字 `find_most_similar` 匹配 uid；只有一个订阅用户时直接使用；消息含「最新」则 `index=1`；带数字则 `send_by_index`，否则列出最近 10 条（`get_weibo_list`，`pluginsDev/src/weibo/main.py:64-73`）并等待序号回复。
6. **订阅开关**（`pluginsDev/src/weibo/main.py:428-467`）：写 `GroupSetting.send_weibo`，开启时对已有记录做 `update`，无记录则 `create`（含 `bot_id`）。
7. **缓存清理**（`pluginsDev/src/weibo/main.py:80-95,555-567`）：`clean_image_cache` 按 `st_mtime` 删除早于 `cacheRetentionDays` 的文件；`retention <= 0` 时直接返回不清理。

## 依赖的 core 能力

`core.database.group.GroupSetting`（`pluginsDev/src/weibo/main.py:15`）；`core.database.messages.*`（`MessageBaseModel`，`pluginsDev/src/weibo/main.py:16`）；`core.util.TimeRecorder`、`find_most_similar`（`pluginsDev/src/weibo/main.py:18`）；`core.send_to_console_channel`、`core.bot as main_bot`（`pluginsDev/src/weibo/main.py:19-25`）；`amiyabot.QQGuildBotInstance`、`QQGroupBotInstance`、`download_async`（`pluginsDev/src/weibo/main.py:10-13`）；第三方 `websockets`、`PIL`。

## 写入的表/目录

表 `WeiboRecord`（字段 `user_id`、`blog_id`、`record_time`、`user_name`、`content`、`images`(JSON)、`detail_url`、`created_at`，`pluginsDev/src/weibo/main.py:53-62`），并更新 `GroupSetting.send_weibo`。

目录：图片缓存 `logs/weibo`（由 `setting.imagesCache` 配置，默认值见 `pluginsDev/src/weibo/config_default.yaml`），拼接图写在同一目录。

## 与其他插件耦合

耦合较低。不依赖 `ArknightsGameData`，也不声明 `Requirement`。通过 `main_bot[group.bot_id]` 跨实例发送消息（`pluginsDev/src/weibo/main.py:344`），直接复用 `GroupSetting` 作为订阅开关。`data.is_admin` 用于权限校验（`pluginsDev/src/weibo/main.py:433,459`）。

## 打包与发布

| 项 | 值 |
|----|----|
| plugin_id | `amiyabot-weibo` |
| version | `4.2` |
| 产物 | `amiyabot-weibo-4.2.zip` |

元数据定义于 `pluginsDev/src/weibo/main.py:40-50`。打包用 `python run_build.py --type plugins`，产出到 `plugins/`。
