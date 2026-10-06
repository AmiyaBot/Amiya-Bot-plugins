# replace 插件开发说明

词语替换：在消息进入匹配流程之前改写文本，把用户自定义别名还原为正式指令词。

## 使用指引

- [README.md](README.md) — 面向用户的功能说明，由 `pluginsDev/src/replace/main.py:82` 的 `document=` 参数加载。
- [README_USE.md](README_USE.md) — 详细使用指引，由 `pluginsDev/src/replace/main.py:83` 的 `instruction=` 参数加载。
- [README_USE-public.md](README_USE-public.md) — 公开机器人场景下的对应版本。

宿主的 `功能`/`帮助` 指令会把上述文档渲染给用户看。本文件是开发者文档，不面向用户。

## 触发方式与指令

| 指令/关键词 | 匹配方式 | level | 说明 |
|------------|---------|-------|------|
| `X别名Y` | `keywords=['别名']` | 5 | 创建/查看/删除别名（`pluginsDev/src/replace/main.py:117`）；正则 `(\S+)别名(\S+)` 解析（`pluginsDev/src/replace/main.py:132`） |
| `同步词语替换` | `keywords=Equal('同步词语替换')` 精确匹配 | 默认 | 管理员从远端同步全局替换表（`pluginsDev/src/replace/main.py:196`） |

## 文件结构

| 文件 | 作用 |
|------|------|
| `__init__.py` | 一行 `from .main import bot`，插件包入口 |
| `main.py` | `bot` 实例、`RealNameDict` 真名缓存、2 个消息处理器、审核与保存函数 |
| `baiduCloud.yaml` | 百度云审核凭据模板，首次运行复制到 `resource/plugins/baiduCloud.yaml` |
| `config_default.yaml` | 全局配置默认值（`update_time`、`use_real_name`、`is_check`） |
| `config_schema.json` | 全局配置 JSON Schema |
| `README*.md` | 对用户展示的使用指引 |
| `logo.png` | 插件图标 |

## 核心实现

- `@bot.message_created`（`pluginsDev/src/replace/main.py:89-114`）是替换链路的核心：
  1. 查询 `TextReplace`：条件为「本 `guild_id` 且 `is_active==1`」或「`is_global==1`」（`pluginsDev/src/replace/main.py:91-95`）。
  2. **倒序遍历**（`reversed(list(replace))`，`pluginsDev/src/replace/main.py:100`）以适配后插入的规则优先。对每条规则：若原文 `origin` 已出现在文本中则跳过（防止把已是正确写法的词再改）；否则把 `item.replace` 替换为 `item.origin`（`pluginsDev/src/replace/main.py:101-105`）。
  3. 若配置 `use_real_name` 开启：抓取 PRTS 角色真名表，把真名替换为角色名（`pluginsDev/src/replace/main.py:107-111`）。
  4. `data.set_text(text, set_original=False)` — 只改匹配用文本，保留 `text_original` 原文（`pluginsDev/src/replace/main.py:113`）。
- **PRTS 真名表 `RealNameDict.get_real_name`**（`pluginsDev/src/replace/main.py:26-52`）：类变量 `data`/`update_time` 做进程内缓存，过期条件为 `time.time() - update_time > 60 * bot.get_config('update_time')`。用 `requests_html.HTMLSession` 同步请求 `https://prts.wiki/w/角色真名`，经 `run_in_thread_pool` 包装为异步；解析 `.wikitable` 的第 2 个 `td` 为角色名、第 3 个 `td` 按行拆为真名，产出 `(真名, 角色名)` 列表。
- **别名写入与审核**（`pluginsDev/src/replace/main.py:132-193`）：
  - 先剥离机器人前缀 `bot.prefix_keywords`（`pluginsDev/src/replace/main.py:127-130`）。
  - `删除` 开头则 `TextReplace.delete()`（`pluginsDev/src/replace/main.py:140-142`）。
  - 冲突检查：全局同名 `replace` 或本频道同名 `replace` 已存在则拒绝（`pluginsDev/src/replace/main.py:144-158`）。
  - 若配置 `is_check`：超管（`Admin.get_or_none`）直接以 `is_global=1` 保存；否则依次执行 `check_forbidden` → `check_permissible` → 百度审核，最后 `save_replace`（`pluginsDev/src/replace/main.py:160-193`）。
- `check_forbidden`（`pluginsDev/src/replace/main.py:222-233`）：纯数字替换词禁止；`TextReplaceSetting` 中 `status==1` 的词禁止；字面「别名」禁止；机器人前缀词禁止。
- `check_permissible`（`pluginsDev/src/replace/main.py:236-238`）：`TextReplaceSetting` 中 `status==0` 为白名单，可直接通过。
- `save_replace`（`pluginsDev/src/replace/main.py:241-252`）：`TextReplace.create(user_id, group_id=guild_id or channel_id, origin, replace, in_time, is_global)`。
- `sync_replace`（`pluginsDev/src/replace/main.py:56-73`）：从 `remote_config.remote.console + '/replace/getGlobalReplace'` 拉取全局替换表，`truncate_table()` + `batch_insert`；`install()` 中以 `asyncio.create_task` 异步发起。

## 依赖的 core 能力

`core.database.bot.*`（`TextReplace`、`TextReplaceSetting`、`Admin`，`pluginsDev/src/replace/main.py:10`）；`core.lib.baiduCloud.BaiduCloud`（`pluginsDev/src/replace/main.py:11,23`）；`core.resource.remote_config`（`pluginsDev/src/replace/main.py:12`）；`core.util.read_yaml`、`run_in_thread_pool`（`pluginsDev/src/replace/main.py:13`）；`core.log`、`Message`、`Chain`、`Equal`、`AmiyaBotPluginInstance`（`pluginsDev/src/replace/main.py:14`）；第三方 `requests_html`。

## 写入的表/目录

| 表 | 内容 |
|----|------|
| `TextReplace` | 别名替换规则，新增/删除/批量插入 |
| `TextReplaceSetting` | 审核词表，只读（`status==1` 禁止、`status==0` 白名单） |

目录：首次运行从插件目录复制 `baiduCloud.yaml` 到 `resource/plugins/baiduCloud.yaml`（`pluginsDev/src/replace/main.py:19-21`）。

## 与其他插件耦合

- 与 `admin` 耦合于 `data.is_admin`（`pluginsDev/src/replace/main.py:120` 对 QQ 频道做管理员校验）。
- 与 `func` 存在顺序耦合：`replace.message_created` 早于 `func.message_before_handle` 执行，因此**替换先于功能开关判定**。
- 别名若替换成某插件指令词，会直接改变其他插件的匹配结果。
- 与 `user`、`arknights/recruit` 共用同一份 `resource/plugins/baiduCloud.yaml` 配置。

## 打包与发布

| 项 | 值 |
|----|----|
| plugin_id | `amiyabot-replace` |
| version | `2.8` |
| 产物 | `amiyabot-replace-2.8.zip` |

元数据定义于 `pluginsDev/src/replace/main.py:76-86`。打包用 `python run_build.py --type plugins`，产出到 `plugins/`。
