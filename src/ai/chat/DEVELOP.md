# ai/chat 插件开发说明

兜底 AI 对话插件：基于大语言模型调用库实现「其他插件优先、AI 兜底」的聊天体验。本插件是从 `pluginsDev/bak/chatBot`（简易兔兔聊天，ERNIE 时代的阻塞式对话）重写而来，旧版进入聊天模式后独占频道、所有功能不可用；新版无任何独占行为。

## 使用指引

- [README.md](README.md) — 面向用户的功能说明，由 `pluginsDev/src/ai/chat/main.py:66` 的 `document=` 参数加载。

宿主的 `功能`/`帮助` 指令会把它渲染给用户看。本文件是开发者文档，不面向用户。

## 触发方式与指令

无专属指令。唯一的入口是兜底校验：

| 入口 | 匹配方式 | 权重 | 说明 |
|------|---------|------|------|
| `check_ai_chat` | `verify=check_ai_chat, check_prefix=False, allow_direct=True`（`pluginsDev/src/ai/chat/main.py:263`） | 可配置 `reply_priority`，默认 **-1** | 所有消息都会先经此校验，但只有当没有其他处理器命中时才会被选中 |

### 兜底机制的原理

框架分发器 `amiyabot/handler/messageHandler.py` 的 `choice_handlers` 会收集所有校验通过的候选，按 `Verify.weight` **降序**取第一个。各权重参考：

- 未显式指定 `level` 的处理器 → weight = 1（`amiyabot/factory/implemented.py:102` 的 custom_verify 布尔分支，或 keyword 路径的默认值）
- 显式 `level=0` → weight = 0
- 本插件 → weight = `reply_priority`（默认 -1）

因此本插件返回 `True` 不会抢占任何正常功能，只在候选为空或全为负权重时被选中。**level 越大越优先**，`AGENTS.md` 中「level 数值小的处理器优先匹配」的表述与框架源码不符。

### 触发条件（`check_ai_chat` 的判定顺序）

1. blm 库未安装 → False（插件静默）
2. 机器人自己的消息（`data.user_id == data.instance.appid`，CQHttp 等适配器会回环投递）→ False，防自问自答
3. `text_original` 为空 → False
4. 生效范围为「仅白名单」且非私聊、频道不在 `channel_whitelist` → False（含 AT 一并拒绝，私聊放行）
5. 频道配置 `enable` 为 False → False
6. `data.is_at` → 触发 `at`（其他插件命中时权重机制自动让位）
7. `data.is_direct` → 触发 `direct`
8. 频道配置 `at_only` 为 True → False（群聊仅 AT 模式）
9. 消息包含 `mention_keywords`（大小写不敏感）→ 触发 `mention`
10. 距 AI 上次回复 ≤ `followup_window_seconds` 且最新一条消息来自上次回复的用户 → 触发 `followup`
11. 开启 `proactive_reply` 且非纯数字/符号消息、已过 `proactive_cooldown_seconds`、上下文 ≥ 4 条、随机数 < `proactive_probability` → 触发 `proactive`（在校验阶段即占用 `last_proactive_ts`，防止短时间多条消息同时通过）

handler 中 `followup` / `proactive` 触发还受 `min_reply_interval_seconds` 最小回复间隔约束。

## 文件结构

| 文件/目录 | 作用 |
|-----------|------|
| `__init__.py` | 一行 `from .main import bot`，插件包入口 |
| `main.py` | 插件实例、`message_created`/`message_after_send` 钩子、兜底校验与 handler、回复清洗 |
| `src/context.py` | `ChatContextStore`：内存态的频道上下文（每频道 deque，条数上限 + 时间过期）与触发状态（`last_reply_ts` / `last_reply_user` / `last_proactive_ts`） |
| `src/lore_builder.py` | 剧情语料构建：把 gamedata 的干员/NPC 档案（`handbook_info_table`）与主线/活动剧情（`story_review_table` + `story/*.txt`）清洗为 txt 语料库（`resource/plugins/ai-chat/lore/{profiles,stories}/`），按 gamedata 版本号增量重建。清洗逻辑移植自 AmiyaBot/Amiya-Bot-knowledge-base 的 `read_content`/`gen_story`/`gen_character` |
| `src/lore_retriever.py` | 剧情语料检索：语料切块（≤700 字符）入内存，两路召回——①档案主人直读（含去尾前缀模糊匹配书写变体，如「伊内斯」↔「伊内丝」；客观履历/档案资料优先于体检数值）②书名直读（章节顺序）③关键词全文共现打分（jieba 分词 + 停用词 + 完整短语强信号 + 头部奖励，长度阻尼） |
| `src/prompt_builder.py` | 双形态提示词构建：`build_role_messages`（OpenAI 多轮消息）与 `build_text_prompt`（纯文本转写，供不支持角色消息的适配器降级使用）；`references` 参数把检索到的资料块注入 system 提示词；内置 `template/Amiya.txt` 作为默认人设 |
| `configs/*.json` | global + channel 双轨配置（默认值与 JSON Schema） |
| `template/Amiya.txt` | 默认人设（由 `src/prompt_builder.py:10` 的 `default_persona_path` 定位） |
| `README.md` / `README_USE.md` | 用户文档（document= / instruction=） |
| `logo.png` | 插件图标（自 bak/chatBot 复制） |

## 核心实现

1. **上下文收集**（`pluginsDev/src/ai/chat/main.py:207-236`）：
   - `message_created` 钩子对**每条**收到的消息执行（先于分发器），只记录不响应；空文本消息记为 `[图片]` / `[表情]`。
   - `message_after_send` 钩子把机器人（含其他插件）发出的文本回复也记入上下文，AI 因此知道其他插件回答了什么。文本提取依赖 `Chain.chain` 中的 `Text.content` 元素。
2. **LLM 调用**（`pluginsDev/src/ai/chat/main.py:223-247` 附近 `call_llm`）：
   - `resolve_model` 先取频道/全局 `model` 配置（不存在则告警回退），再回退到 blm 的 `default_model`；通过 `blm.model_map` 拿到适配器实例。
   - 适配器具有 `supports_role_messages = True`（见 blm 库的 OpenAICompatible / DeepSeek 适配器）时传 OpenAI 多轮消息（system + 按昵称标注的多轮 user/assistant，连续同角色合并）；否则传纯文本转写。
   - **不传 `context_id`**——上下文完全由本插件管理，避免与 blm 的会话机制重复存储。
3. **回复清洗 `clean_reply`**（含 `_collapse_repetition`：折叠整段重复的回复；含 `_strip_reasoning_prefix`：剥离回复开头的思考/导演注释括号段——推理模型的 reasoning 泄漏、blm `deep_think` 拼接的 `(思考)
正文` 格式；按特征词判别避免误伤动作类短括号，`<think>` 标签残留亦在此剥离）（`pluginsDev/src/ai/chat/main.py:183-202`）：剔除 `<think>` 思考段、`阿米娅：` 自标注前缀、成对包裹引号；超过 `max_reply_length` 时在换行/标点处截断。
4. **回复后状态更新**：写入 `state.last_reply_ts` / `state.last_reply_user`（支撑连续对话），并把回复以 `is_bot=True` 记入上下文。
5. **动态 schema**（`pluginsDev/src/ai/chat/main.py:26-46` `generate_schema`）：与 blm 相同的模式——运行时把 blm 的模型列表注入 `model` 的 enum。
6. **插件优先级**：`priority=0`（低于 blm 的默认 1），保证安装顺序在 blm 之后（`install_loaded_plugins` 按 priority 倒序安装）。

## 剧情资料检索（harness 模式）

兜底回答前的检索注入管线（`main.py` handler 内，仅当 `lore_retrieval` 开启时执行）：

```
触发消息 + 最近 5 条用户发言
  → LoreRetriever.retrieve()
      1. 档案主人实体：精确子串匹配（len≥2）→ 去尾前缀模糊匹配（书写变体）
         → 档案块按「客观履历 > 档案资料/经历/密录 > 体检数值/临床诊断」排序直读
      2. 剧情书实体：书名命中 → 按章节顺序直读
      3. 关键词全文召回：完整短语 + jieba 分词（停用词过滤）共现打分 × 长度阻尼
  → 渲染为「【档案·赫德雷】…」「【剧情·生于黑夜-XX 行动前】…」资料块
  → prompt_builder 注入 system 提示词（含防幻觉指令：资料未提及的明确表示不确定）
```

- 语料来源与体量（以 2026-10 版 gamedata 为准）：437 份干员/NPC 档案（约 120 万字）+ 94 本主线/活动剧情书（约 1600 话）；索引约 1.9 万块，单次检索 0-30ms。
- gamedata 新版的 `handbook_info_table.infoName` 已全部匿名化为 `Unknown`，干员名一律从 `ArknightsGameData.operators` 按 charId 解析（`lore_builder._char_names`）。
- 语料按 gamedata 版本号缓存于 `resource/plugins/ai-chat/lore/`（`profiles/`、`stories/` 与 `.version`），仅在版本变化时重建（全量重建约 2s）。
- 已知取舍：不做向量/embedding 检索；肉鸽剧情（`roguelike_topic_table`）与 `story/*.txt` 中未被 `story_review_table` 引用的长尾脚本暂不收录；单字干员名（黑、陈）不做子串实体匹配（误命中太多），只能通过关键词路径召回。

## 配置

全局与频道两级（`get_config(name, channel_id)` 按「频道配置 → 频道默认 → 全局配置 → 全局默认」降级）：

| 键 | 默认 | 说明 |
|----|------|------|
| `allow_mode` | `全部频道` | 生效范围：`全部频道` 全局开放 / `仅白名单` 只对 `channel_whitelist` 内群聊开放（私聊不受限），全局键 |
| `channel_whitelist` | `[]` | 群聊白名单（频道 ID 字符串数组），全局键 |
| `model` | `''` | 对话模型，空则用 blm 默认模型（channel 可覆盖） |
| `system_prompt` | `''` | 人设，空则用内置 Amiya 模板（channel 可覆盖） |
| `reply_priority` | `-1` | 兜底权重，勿随意调高 |
| `at_reply` | `true` | 响应 AT 时是否 @ 对方 |
| `max_reply_length` | `200` | 单次回复最大字数 |
| `context_max_messages` | `20` | 每频道上下文条数（改动需重启） |
| `context_timeout_minutes` | `30` | 上下文时效分钟数（改动需重启） |
| `mention_keywords` | `["阿米娅","兔兔","Amiya","amiya"]` | 昵称触发词 |
| `followup_window_seconds` | `120` | 连续对话窗口，0 关闭 |
| `min_reply_interval_seconds` | `3` | 两次 AI 回复最小间隔 |
| `proactive_reply` | `false` | 是否主动插话 |
| `proactive_probability` | `0.03` | 插话概率 |
| `proactive_cooldown_seconds` | `300` | 插话冷却 |
| `lore_retrieval` | `true` | 剧情资料检索注入（需 gamedata 就绪，未就绪时静默禁用；channel 可覆盖） |
| `lore_max_chars` | `2400` | 单次注入的资料字符上限 |

频道级额外有 `enable`（默认 true）与 `at_only`（默认 false）。

### 共享键的降级语义（`effective_config`）

`model` / `system_prompt` / `proactive_*` / `lore_retrieval` 同时存在于全局与频道两轨。框架 `get_config` 的降级链是「频道配置 → 频道默认 → 全局」，而频道配置记录一经保存就会物化全部频道默认值（空串不算空值，见 `amiyaBotPluginInstance.is_empty_value`），导致共享键的全局设置被永久遮蔽。因此这些键一律通过 `main.py` 的 `effective_config(name, data)` 读取：频道值等于频道默认值（即未被实际定制）时降级到全局配置。代价是「频道显式设置成与默认值相同的值」无法与「未定制」区分——例如全局开 `proactive_reply` 后，某频道把 `proactive_reply` 显式设为 false 不生效，需改用其他方式（如 `at_only` 或关闭该频道 `enable`）。

## 依赖的 core 能力

`core.AmiyaBotPluginInstance`、`core.Requirement`、`core.bot`（`main_bot.plugins` 查找 blm 实例）；`amiyabot.builtin.messageChain.element.Text`（`message_after_send` 文本提取）。

## 与其他插件耦合

- 强依赖 `amiyabot-blm-library`（`requirements=[Requirement('amiyabot-blm-library')]`），通过 `main_bot.plugins['amiyabot-blm-library']` 调用 `chat_flow`。
- **软依赖 `amiyabot-arknights-gamedata`**（未声明 Requirement，避免纯聊天用户被动下载资源包）：检测 `resource/gamedata/version.txt` 与语料表文件就绪后启用剧情检索；订阅 `gameDataInitialized` 在资源刷新后重建语料。
- `message_after_send` 使 AI 能看到其他插件的回复（单向感知，无接口耦合）。
- 与 `amiyabot-talking`（自定义回复，verify 权重 1）共存：talking 命中时 talking 响应，AI 让位。
- 干员数值类问答（查干员/材料/公招等）由 arknights 系列插件负责且权重更高；剧情检索只服务 AI 兜底回答。

## 打包与发布

| 项 | 值 |
|----|----|
| plugin_id | `amiyabot-ai-chat` |
| version | `1.3.3` |
| 产物 | `amiyabot-ai-chat-1.3.3.zip` |

打包用 `python run_build.py --type plugins`（`buildPlugins.py` 只扫描 `pluginsDev/src`，`bak/` 不参与打包），产出到 `plugins/`。

## 已知限制

- 上下文为内存态，重启后清空。
- 图片不做视觉理解，仅以 `[图片]` 占位（blm 的 vision 能力可供未来接入）。
- 消息处理为逐条 await，上下文时间戳在高并发下可能有毫秒级交错，不影响语义。
