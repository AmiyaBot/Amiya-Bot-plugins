# ai/blm 插件开发说明

大语言模型调用库：为其他插件提供统一的多厂商 LLM 适配层，支持函数调用与 MCP。

## 使用指引

- [README.md](README.md) — 面向用户的功能说明，由 `pluginsDev/src/ai/blm/main.py:54` 的 `document=` 参数加载。

宿主的 `功能`/`帮助` 指令会把它渲染给用户看。本文件是开发者文档，不面向用户。

## 触发方式与指令

| 指令/关键词 | 匹配方式 | level | 说明 |
|------------|---------|-------|------|
| `测试调用库` | `keywords=['测试调用库']` | 5 | 用 `ERNIE-Bot` 模型调用 `bot.chat_flow` 并回显测试结果（`pluginsDev/src/ai/blm/main.py:60-64`） |

除此之外无用户指令，其余全部是供其他插件 import 的编程接口。

## 文件结构

| 文件/目录 | 作用 |
|-----------|------|
| `__init__.py` | 一行 `from .main import bot`，插件包入口 |
| `main.py` | `bot` 实例、动态配置 schema 函数、测试指令 |
| `src/common/blm_plugin_instance.py` | `BLMLibraryPluginInstance`：适配器装配、模型/assistant 注册表、对外调用接口、函数注册装饰器 |
| `src/common/blm_types.py` | `BLMAdapter` 抽象基类、`BLMFunctionCall` 数据类；模块导入时创建缓存目录 |
| `src/common/database.py` | 两张表：token 消耗记录、元数据存储 |
| `src/common/quota_check.py` | `QuotaController`：滑动窗口配额限流 |
| `src/common/extract_json.py` | 从模型输出中提取 JSON |
| `src/functions/core.py` | `parse_docstring`：从 reST 风格 docstring 生成 JSON Schema |
| `src/chat_gpt/chat_gpt_adapter.py` | ChatGPT 适配器 |
| `src/chat_gpt/gpt_assistant_adapter.py` | GPT Assistant 适配器（线程模式） |
| `src/ernie/ernie_adapter.py` | 文心 ERNIE 适配器 |
| `src/ernie/qianfan_adapter.py` | 千帆适配器 |
| `src/deepseek/deekseek_adapter.py` | DeepSeek 适配器（文件名拼写为 `deekseek`） |
| `src/openai_compatible/openai_compatible_adapter.py` | OpenAI SDK 兼容适配器 |
| `src/mcp/mcp_client_manager.py` | `MCPClientManager`：MCP 服务连接与工具调用 |
| `config_templates/global_config_default.json` | 全局配置默认值：6 个适配器的 `enable` 与凭据、`show_log` |
| `config_templates/global_config_schema.json` | 全局配置 JSON Schema（含 `default_model`、`default_assistant` 动态枚举） |
| `images/chino_logo_comment.png` | 额外素材 |
| `README.md` | 对用户展示的使用指引 |
| `logo.png` | 插件图标 |

## 核心实现

1. **适配器装配**（`pluginsDev/src/ai/blm/src/common/blm_plugin_instance.py:67-98`）：`install()` 先建表，再按配置逐项判断 `enable`，命中则 `self.adapters.append(...)`：
   - `ChatGPT` → `ChatGPTAdapter`（`pluginsDev/src/ai/blm/src/chat_gpt/chat_gpt_adapter.py:40`）
   - `GPTAssistant` → `ChatGPTAssistantAdapter`（`pluginsDev/src/ai/blm/src/chat_gpt/gpt_assistant_adapter.py:40`）
   - `ERNIE` → `ERNIEAdapter`（`pluginsDev/src/ai/blm/src/ernie/ernie_adapter.py:21`）
   - `QianFan` → `QianFanAdapter`（`pluginsDev/src/ai/blm/src/ernie/qianfan_adapter.py:25`）
   - `DeepSeek` → `DeepSeekAdapter`（`pluginsDev/src/ai/blm/src/deepseek/deekseek_adapter.py:25`）
   - `OpenAISDKCompatible` → `OpenAICompatibleAdapter`（`pluginsDev/src/ai/blm/src/openai_compatible/openai_compatible_adapter.py:25`）
   - `MCP` → `self.mcp_manager = MCPClientManager(self)`（`pluginsDev/src/ai/blm/src/common/blm_plugin_instance.py:94-96`）
   - 最后调用 `self.model_list()` 预构建 `model_map`。默认配置中全部适配器 `enable` 为 false（`pluginsDev/src/ai/blm/config_templates/global_config_default.json`）。
2. **模型注册表**：`model_list()` 汇总各适配器的模型并填 `self.model_map[model_name] = adapter`（`pluginsDev/src/ai/blm/src/common/blm_plugin_instance.py:131-139`）；`assistant_list()` 同理填 `assistant_map[id]`（`pluginsDev/src/ai/blm/src/common/blm_plugin_instance.py:200-208`）；`thread_map` 用于 assistant 会话线程（`pluginsDev/src/ai/blm/src/common/blm_plugin_instance.py:227`）。
3. **对外接口**（`pluginsDev/src/ai/blm/src/common/blm_plugin_instance.py:162-257`）：
   - `completion_flow(prompt, model, context_id, channel_id)` — 纯补全。
   - `chat_flow(prompt, model, context_id, channel_id, functions, json_mode)` — 对话，支持函数调用与 JSON 模式。
   - `assistant_thread_create` / `assistant_thread_touch` / `assistant_run` — assistant 模式的线程管理。
   - 以上均支持 `model` 传字符串或 dict；传 None 时回退到全局配置的 `default_model`（`pluginsDev/src/ai/blm/src/common/blm_plugin_instance.py:153-158`）。
4. **函数调用注册 `register_blm_function`**（`pluginsDev/src/ai/blm/src/common/blm_plugin_instance.py:100-129`）：装饰器，用 `parse_docstring(func)` 从 reST 风格 docstring 自动生成 JSON Schema，包成 `BLMFunctionCall` 存入 `functions_registry`。
   - `parse_docstring`（`pluginsDev/src/ai/blm/src/functions/core.py:5-56`）：正则提取 `:param x: 描述`（`pluginsDev/src/ai/blm/src/functions/core.py:23`）与 `:type x: 类型`（`pluginsDev/src/ai/blm/src/functions/core.py:24`），把 Python 类型映射为 JSON 类型（`str→string`、`int→integer`、`bool→boolean`、`float→number`，`pluginsDev/src/ai/blm/src/functions/core.py:33-41`），全部参数计入 `required`（`pluginsDev/src/ai/blm/src/functions/core.py:44`）。
   - 通过属性 `amiyabot_function_calls` 扁平化导出（`pluginsDev/src/ai/blm/src/common/blm_plugin_instance.py:259-267`），供其他插件传给 `chat_flow(functions=...)`。
5. **MCP 客户端**（`pluginsDev/src/ai/blm/src/mcp/mcp_client_manager.py`）：
   - 可选依赖：`mcp` 包导入失败则 `self.disabled = True` 并退化为空实现（`pluginsDev/src/ai/blm/src/mcp/mcp_client_manager.py:9-28`）。
   - 配置来源为 `get_config("MCP")` 的 `config` 字段，支持 JSON 字符串或 dict（`pluginsDev/src/ai/blm/src/mcp/mcp_client_manager.py:35-50`）。
   - 遍历 `mcpServers`，按 `transportType == "sse"` 走 `sse_client`，否则走 `stdio_client`（`pluginsDev/src/ai/blm/src/mcp/mcp_client_manager.py:64-95`）。
   - 工具以 `"{server}:{tool.name}"` 命名并转为 OpenAI function 格式（`pluginsDev/src/ai/blm/src/mcp/mcp_client_manager.py:97-111`）；`execute_tool_call` 解析该前缀定位会话、调用工具，并把 assistant tool_calls 与 tool 结果追加进 messages 列表（`pluginsDev/src/ai/blm/src/mcp/mcp_client_manager.py:113-155`）。
   - `cleanup()` 通过 `AsyncExitStack.aclose()` 统一关闭（`pluginsDev/src/ai/blm/src/mcp/mcp_client_manager.py:157-161`）。
6. **配额控制 `QuotaController`**（`pluginsDev/src/ai/blm/src/common/quota_check.py:4-38`）：滑动窗口限流。维护 `query_times` 列表，每次 `check(query_per_hour, peek=False)` 先剔除 1 小时前的记录（`pluginsDev/src/ai/blm/src/common/quota_check.py:25`）；未超限则追加当前时间戳并返回剩余次数，超限返回 0；`query_per_hour` 为 None 或 ≤0 时返回 `100000` 表示不限（`pluginsDev/src/ai/blm/src/common/quota_check.py:18-19`）。`peek=True` 只查询不计数。由 `DeepSeekAdapter`（`pluginsDev/src/ai/blm/src/deepseek/deekseek_adapter.py:30`）与 `OpenAICompatibleAdapter`（`pluginsDev/src/ai/blm/src/openai_compatible/openai_compatible_adapter.py:30`）持有实例。
7. **动态配置 schema**（`pluginsDev/src/ai/blm/main.py:13-45`）：`global_config_schema` 传入函数，运行时把可用模型名与 `名称[id]` 形式的 assistant 列表写入 schema 的 enum；仅当 `bot` 已存在时才注入，否则回退到默认文件路径（`pluginsDev/src/ai/blm/main.py:44-45`）。
8. **`extract_json`**（`pluginsDev/src/ai/blm/src/common/extract_json.py`，74 行）：从模型输出中提取 JSON，经 `pluginsDev/src/ai/blm/src/common/blm_plugin_instance.py:269-270` 暴露。

## 依赖的 core 能力

`core.AmiyaBotPluginInstance`、`core.Requirement`（`pluginsDev/src/ai/blm/src/common/blm_plugin_instance.py:6`）；`core.plugins.customPluginInstance.amiyaBotPluginInstance.{CONFIG_TYPE, DYNAMIC_CONFIG_TYPE}`（`pluginsDev/src/ai/blm/src/common/blm_plugin_instance.py:7`）；`core.database.plugin.db`（表挂载，`pluginsDev/src/ai/blm/src/common/database.py:7`）；`amiyabot.log.LoggerManager`（`pluginsDev/src/ai/blm/src/mcp/mcp_client_manager.py:7`）；`amiyabot.database.ModelClass`（`pluginsDev/src/ai/blm/src/common/database.py:5`）。

## 写入的表/目录

| 表 | 字段 |
|----|------|
| `amiyabot-blm-library-token-consume` | `exec_id`、`channel_id`、`model_name`、`prompt_tokens`、`completion_tokens`、`total_tokens`、`exec_time`（`pluginsDev/src/ai/blm/src/common/database.py:10-22`） |
| `amiyabot-blm-library-meta-storage` | `key`、`meta_str`（`pluginsDev/src/ai/blm/src/common/database.py:25-32`） |

两表在 `install()` 中以 `create_table(safe=True)` 创建（`pluginsDev/src/ai/blm/src/common/blm_plugin_instance.py:68-69`）。

目录 `resource/blm_library/cache`，在模块导入时即 `os.makedirs`（`pluginsDev/src/ai/blm/src/common/blm_types.py:6-9`）；各适配器用它写调试图文，如 `{cache_dir}/CHATGPT.{channel_id}.{时间戳}.txt`（`pluginsDev/src/ai/blm/src/chat_gpt/chat_gpt_adapter.py:417`）与 `{cache_dir}/ERNIE.{channel_id}.{时间戳}.txt`（`pluginsDev/src/ai/blm/src/ernie/ernie_adapter.py:353`）。

## 与其他插件耦合

`blm` 是纯被依赖方（库）。它不 import 任何其他插件，但通过 `plugin_id='amiyabot-blm-library'` 暴露实例，其他插件可从 `main_bot.plugins['amiyabot-blm-library']` 取得它并调用 `chat_flow` / `assistant_run` / `amiyabot_function_calls`。配置模板位于 `config_templates/`。

## 打包与发布

| 项 | 值 |
|----|----|
| plugin_id | `amiyabot-blm-library` |
| version | `1.4.0` |
| 产物 | `amiyabot-blm-library-1.4.0.zip` |

元数据定义于 `pluginsDev/src/ai/blm/main.py:48-57`。打包用 `python run_build.py --type plugins`，产出到 `plugins/`。
