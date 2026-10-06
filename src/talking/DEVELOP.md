# talking 插件开发说明

自定义回复：纯配置驱动的「一问一答」引擎，回复文本支持一套变量模板语法。

## 使用指引

- [README.md](README.md) — 面向用户的功能说明，由 `pluginsDev/src/talking/main.py:475` 的 `document=` 参数加载。
- [README_USE.md](README_USE.md) — 详细使用指引，由 `pluginsDev/src/talking/main.py:476` 的 `instruction=` 参数加载。

宿主的 `功能`/`帮助` 指令会把上述文档渲染给用户看。本文件是开发者文档，不面向用户。

## 触发方式与指令

本插件没有固定指令词，完全由全局配置 `configs` 数组驱动。

| 配置项 | 取值 | 说明 |
|--------|------|------|
| `keyword_type` | `包含关键词` / `等于关键词` / `正则匹配` | 触发类型（`pluginsDev/src/talking/main.py:496-504`；枚举定义见 `pluginsDev/src/talking/config_schema.json`） |
| `direct` | `仅群聊` / `群聊和私聊` / `仅私聊` | 触发环境过滤（`pluginsDev/src/talking/main.py:489-494`） |
| `reply` | 字符串 | 回复内容，可为图片绝对路径或模板表达式 |
| `is_at` | 布尔 | 是否 @ 用户 |

处理器注册为 `@bot.on_message(verify=check_talk, check_prefix=False, allow_direct=True)`（`pluginsDev/src/talking/main.py:507`）：

- `check_prefix=False` → 群内无需 @ 机器人即可触发。
- `allow_direct=True` → 私聊可用。
- `verify` 返回值是 `(True, 1, [reply, is_at])`（`pluginsDev/src/talking/main.py:486`），即 `level=1`，`keypoint` 为二元组。
- 默认配置为空列表（`pluginsDev/src/talking/config_default.yaml:1` 的 `configs: [ ]`），开箱状态下不触发任何回复。

## 文件结构

| 文件/目录 | 作用 |
|-----------|------|
| `__init__.py` | 一行 `from .main import bot`，插件包入口 |
| `main.py` | 变量模板引擎（约 450 行）+ `bot` 实例 + 匹配与分派处理器 |
| `config_default.yaml` | 全局配置默认值，仅一行 `configs: [ ]` |
| `config_schema.json` | 全局配置 JSON Schema，定义 `configs` 数组各项字段 |
| `images/` | 插件自带图片素材（含 `.gitkeep`） |
| `README.md` / `README_USE.md` | 对用户展示的使用指引 |
| `logo.png` | 插件图标 |

## 核心实现

1. **匹配 `check_talk`**（`pluginsDev/src/talking/main.py:482-504`）：依次遍历 `configs`，先按 `direct` 过滤环境，再按 `keyword_type` 三分支判断；命中即返回 `(True, 1, [reply, is_at])`。
2. **回复分派**（`pluginsDev/src/talking/main.py:508-528`）：若 `reply` 本身是存在的文件路径则直接发图；否则调用 `parse_reply_content` 解析为元素序列，逐项追加 `text` / `image` / `html`（`page` 类型用 `chain.html(url, is_template=False, render_time, width, height)`）。
3. **变量模板引擎 `parse_reply_content`**（`pluginsDev/src/talking/main.py:404-460`），解析顺序为「先无网络变量，后有网络变量」：
   - **随机变量 `replace_random_keywords`**（`pluginsDev/src/talking/main.py:329-337`）：最多迭代 5 层（`_rand_nesting_limit = 5`，`pluginsDev/src/talking/main.py:272`）以支持嵌套，如 `{rand:{nickname} hello}`。
     - `_rand_variable`（`pluginsDev/src/talking/main.py:275-305`）：手工扫描花括号深度与引号状态，正确跳过引号/反引号内的 `}`，从而支持嵌套参数。
     - `_random_value`（`pluginsDev/src/talking/main.py:251-268`）：三种形态 —— `{rand}` 取 0~100；`{rand:max}` 取 0~max（单参数且非 0）；`{rand:min,max}` 取区间（保留最大小数位）；其余按逗号分隔随机取文本。
     - `_split_arguments`（`pluginsDev/src/talking/main.py:206-233`）：按逗号切分，但引号内、反引号内、花括号深度 > 0 的逗号不切分。
     - 反引号包裹的内容经 `_escape_braces` 替换为 `\x00`/`\x01` 占位，最后统一还原，实现「原样输出」。
   - **日期时间变量 `replace_datetime_keywords`**（`pluginsDev/src/talking/main.py:399-401`）：正则 `\{(date|time)(?::([^}]*))?\}`（`pluginsDev/src/talking/main.py:28`）。默认 `date` 为 `YYYY年MM月dd日`、`time` 为 `HH:mm:ss`（`pluginsDev/src/talking/main.py:393-396`）。`_format_datetime`（`pluginsDev/src/talking/main.py:373-386`）与 `_format_token`（`pluginsDev/src/talking/main.py:340-370`）实现 Windows 风格格式符：`y/Y` 年、`M` 月（长度 3 为「N月」、4 为中文月份名）、`d/D` 日（长度 3/4 为周几）、`H/h` 24/12 小时、`m` 分、`s` 秒、`t/T` 上午/下午。
   - **内容变量**（`pluginsDev/src/talking/main.py:418-452`），统一正则 `_content_pattern`（`pluginsDev/src/talking/main.py:32-38`）匹配四类：
     - `{url:...}` → `fetch_url_content` 抓取，按 magic bytes 判断是否为图片（`_is_image_by_content`，`pluginsDev/src/talking/main.py:75-95`），文本则 UTF-8 解码。
     - `{page:url[,render,width,height]}` → 渲染网页，尾部数字为渲染参数，默认 `(1000, 1280, 720)`（`pluginsDev/src/talking/main.py:41,236-248`）。
     - `{face}` → 从 `resource/plugins/user/face` 随机取一张表情图（`pluginsDev/src/talking/main.py:441-445`）。
     - 裸图片路径 → 正则直接识别 `.png/.jpg/.gif/.webp/.bmp/.ico` 结尾的路径，仅在文件真实存在时生效（`pluginsDev/src/talking/main.py:435-439`）。
   - **收尾**：替换 `{nickname}` 为 `data.nickname`，并还原转义花括号（`pluginsDev/src/talking/main.py:459-460`）。
4. **URL 抓取与缓存 `fetch_url_content`**（`pluginsDev/src/talking/main.py:108-155`）：进程内 dict `_url_cache`，key 为 url，value 为 `(text, image_path, timestamp)`，TTL 300 秒（`pluginsDev/src/talking/main.py:18-20`）；过期时删除缓存文件（仅限 temp 目录下的文件，`pluginsDev/src/talking/main.py:57-72`）。下载时 `ssl=False` 跳过证书校验，超时 10 秒。
5. **表情目录准备**（`pluginsDev/src/talking/main.py:463-467`）：`install()` 时若 `resource/plugins/user/face` 不存在则从插件目录 `face/` 复制。

## 依赖的 core 能力

仅 `core.AmiyaBotPluginInstance` 与 `amiyabot.Message/Chain`（`pluginsDev/src/talking/main.py:10-11`）；另有第三方 `aiohttp` 用于 URL 抓取。不依赖任何 `core.database.*` 或 `core.resource.*`。

## 写入的表/目录

无数据库表。目录：系统临时目录下写 `url_content_<hash>` 缓存文件（`pluginsDev/src/talking/main.py:119`）。插件目录内的 `images/` 仅存放素材。

## 与其他插件耦合

- 与 `user` 插件**共享 `resource/plugins/user/face` 表情目录**（`pluginsDev/src/talking/main.py:14` 与 `pluginsDev/src/user/mainBot.py:15` 指向同一路径），因此 `user` 插件 `uninstall()` 时 `shutil.rmtree(face_dir)`（`pluginsDev/src/user/mainBot.py:26`）会影响 `talking` 的 `{face}` 变量。
- `{nickname}` 变量依赖 `user` 插件在 `message_created` 中写入的自定义昵称（`pluginsDev/src/user/main.py:235-241`）。

## 打包与发布

| 项 | 值 |
|----|----|
| plugin_id | `amiyabot-talking` |
| version | `1.8` |
| 产物 | `amiyabot-talking-1.8.zip` |

元数据定义于 `pluginsDev/src/talking/main.py:469-479`。打包用 `python run_build.py --type plugins`，产出到 `plugins/`。
