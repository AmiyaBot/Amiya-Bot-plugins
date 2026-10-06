# func 插件开发说明

插件级开关中心：按频道启用/禁用任意插件功能，并统计各功能使用次数。

## 使用指引

- [README.md](README.md) — 面向用户的功能说明，由 `pluginsDev/src/func/main.py:22` 的 `document=` 参数加载。
- [README_USE.md](README_USE.md) — 详细使用指引，由 `pluginsDev/src/func/main.py:23` 的 `instruction=` 参数加载；`func` 渲染文档时优先取 `instruction`，其次才是 `document`（`pluginsDev/src/func/main.py:203-205`）。
- [README_USE-public.md](README_USE-public.md) — 公开机器人场景下的对应版本。

宿主的 `功能`/`帮助` 指令会把上述文档渲染给用户看。本文件是开发者文档，不面向用户。

## 触发方式与指令

| 指令/关键词 | 匹配方式 | level | 说明 |
|------------|---------|-------|------|
| `功能`、`帮助`、`说明`、`help` | `keywords=[...]`, `allow_direct=True` | 默认 | 输出功能清单，回复序号查看用法（`pluginsDev/src/func/main.py:83`） |
| `开启功能` / `开启全部功能` / `开启所有功能` | `keywords=re.compile(r'开启(全部\|所有)?功能')` | 5 | 管理员开启功能（`pluginsDev/src/func/main.py:123`） |
| `关闭功能` / `关闭全部功能` / `关闭所有功能` | `keywords=re.compile(r'关闭(全部\|所有)?功能')` | 5 | 管理员关闭功能（`pluginsDev/src/func/main.py:163`） |

## 文件结构

| 文件/目录 | 作用 |
|-----------|------|
| `__init__.py` | 一行 `from .main import bot`，插件包入口 |
| `main.py` | `bot` 实例、2 个钩子、3 个消息处理器与全部开关逻辑 |
| `database.py` | 定义 `ChannelRecord` 表（频道最后活跃时间） |
| `template.md` | 功能清单 Markdown 模板，含 `{items}` 占位符 |
| `configs/global_config_default.json` | 全局配置默认值（`newChannelDisableAll`、`disabledRemind`、`disabledRemindRate`） |
| `configs/global_config_schema.json` | 全局配置 JSON Schema |
| `README*.md` | 对用户展示的使用指引 |
| `logo.png` | 插件图标 |

## 核心实现

- `@bot.message_before_handle`（`pluginsDev/src/func/main.py:30-73`）是核心拦截逻辑：
  1. 查询本频道已禁用功能 `DisabledFunction`。
  2. 若无 `ChannelRecord` 记录：创建记录；若该频道此前无任何禁用记录且配置 `newChannelDisableAll` 为真，则调用 `disabled_all()` 禁用全部功能并返回 `False` 阻断本条消息（`pluginsDev/src/func/main.py:39-49`）。
  3. 若已有记录：刷新 `last_message` 时间戳（`pluginsDev/src/func/main.py:51-52`）。
  4. `DisabledFunction.get_or_none(function_id=factory_name, channel_id=...)` 命中则累计 `disabled_remind` 计数；达到配置的 `disabledRemindRate` 阈值且 `disabledRemind` 开启时，从 `main_bot.plugins[factory_name]` 取插件名并发送「功能已关闭」提醒（`pluginsDev/src/func/main.py:55-71`）。
  5. 返回 `not bool(disabled)` 决定是否继续处理。
- `@bot.message_after_handle`（`pluginsDev/src/func/main.py:76-80`）：`FunctionUsed.get_or_create(function_id=factory_name)`，已存在则 `use_num + 1`。
- **功能清单**（`pluginsDev/src/func/main.py:90-120`）：读取 `template.md`，按插件名 `sorted(main_bot.plugins.items(), key=lambda n: n[1].name)` 排序，逐项判断 `item.plugin_id in disabled` 生成「开启/已关闭」HTML 着色标记，写入 Markdown 表格后 `data.wait` 等待用户回复序号，命中则调用 `get_plugin_use_doc` 返回文档。
- **文档选择 `get_plugin_use_doc`**（`pluginsDev/src/func/main.py:200-221`）：优先用 `plugin.instruction`，否则 `plugin.document`；若为公开机器人（`QQGroupBotInstance`/`QQGuildBotInstance`）且非 `instance.private`，改用同目录的 `-public` 版本文件；再把 `{bot_name}` 占位符替换为机器人名。
- **开启/关闭**（`pluginsDev/src/func/main.py:123-192`）：`get_plugins_set()` 返回除自身外全部 `plugin_id`；`data.verify.keypoint[0]`（来自正则捕获组）为真表示「全部」，直接 `DisabledFunction.delete()` 或 `disabled_all()`；否则列出候选让用户按序号单选。关闭时 `DisabledFunction.create(function_id, channel_id)`。
- **`disabled_all`**（`pluginsDev/src/func/main.py:195-197`）：批量构造并 `DisabledFunction.batch_insert`。
- `factory_name` 参数即 `plugin_id`，框架以插件为单位分发 `message_before_handle` / `message_after_handle`。

## 依赖的 core 能力

`core.database.bot.DisabledFunction`、`FunctionUsed`（`pluginsDev/src/func/main.py:10`）；`core.database.bot.BotBaseModel`（`pluginsDev/src/func/database.py:4`）；`core.util.get_index_from_text`、`check_file_content`（`pluginsDev/src/func/main.py:11`）；`core.bot`（主机器人实例，用于遍历 `main_bot.plugins`，`pluginsDev/src/func/main.py:9,69,93`）；`amiyabot.adapters.tencent` 的 `QQGuildBotInstance`、`QQGroupBotInstance`（`pluginsDev/src/func/main.py:7-8`）。

## 写入的表/目录

| 表 | 内容 |
|----|------|
| `DisabledFunction` | 各频道被禁用的功能 ID |
| `FunctionUsed` | 各功能累计使用次数 |
| `ChannelRecord` | 频道最后活跃时间，字段 `channel_id`、`last_message`（`pluginsDev/src/func/database.py:7-10`） |

无目录写入，只读 `template.md`。

## 与其他插件耦合

引用全部插件。`main_bot.plugins` 是全局注册表，`func` 通过它枚举并开关任意插件。`ChannelRecord` 与 `DisabledFunction` 的 channel 维度记录服务于「新频道默认关闭」策略。与 `admin` 耦合于 `data.is_admin`（`pluginsDev/src/func/main.py:125,165`）。

## 打包与发布

| 项 | 值 |
|----|----|
| plugin_id | `amiyabot-functions` |
| version | `2.7` |
| 产物 | `amiyabot-functions-2.7.zip` |

元数据定义于 `pluginsDev/src/func/main.py:16-26`。打包用 `python run_build.py --type plugins`，产出到 `plugins/`。
