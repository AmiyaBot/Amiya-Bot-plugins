# operatorArchives 开发说明

功能最密集的查询插件，覆盖干员信息、技能、材料、模组、皮肤、语音、档案、阵营八大类查询，并以 HTML
模板渲染为图片（`pluginsDev/src/arknights/operatorArchives/operatorCore.py:36-48`）。

## 使用指引

- 同目录 [README.md](README.md)：面向用户的使用指引，由 `document=f'{curr_dir}/README.md'` 加载
  （`operatorCore.py:42`），用户发送宿主 `功能` / `帮助` 指令时可见。**勿将其当作开发文档编辑。**
- 同目录 [README_USE.md](README_USE.md)：指令用法说明，由 `instruction=f'{curr_dir}/README_USE.md'` 加载
  （`operatorCore.py:43`）。
- `README_USE-public.md`：对外发布版本的用法说明，源码中未见引用。

## 插件注册信息

| 项 | 值 |
| --- | --- |
| 类 | `OperatorPluginInstance`（`operatorCore.py:16-47`） |
| plugin_id | `amiyabot-arknights-operator` |
| name / version | 明日方舟干员资料 / `6.3` |
| plugin_type | `official` |
| priority | 未声明 |
| Requirement | `Requirement('amiyabot-arknights-gamedata', official=True)`（`operatorCore.py:46`） |
| 消息组 | `GroupConfig('operator', allow_direct=True)`（`operatorCore.py:48`） |
| 关键常量 | `default_level = 8`（`operatorCore.py:13`） |

`install()` 起三个异步任务构建索引（`operatorCore.py:17-20`）；`uninstall()` 解除事件订阅（`operatorCore.py:22-23`）。

## 触发方式与指令

全部处理器共用 `group_id='operator'`：

| 指令 | 匹配方式 | level | 说明 |
| --- | --- | --- | --- |
| `模组` | `keywords=['模组']` | 8 | 干员模组查询（`main.py:20`） |
| `语音` | `keywords=['语音']` | 8 | 语音列表与语音文件（`main.py:44`） |
| `档案`、`资料` | `keywords=['档案','资料']` | 8 | 干员档案文本（`main.py:159`） |
| `皮肤`、`立绘` | `keywords=['皮肤','立绘']` | 8 | 立绘渲染与图片发送（`main.py:211`） |
| 精英/专精/材料 相关 | `verify=FuncsVerify.level_up` | 10 | 升级与技能材料消耗（`main.py:267`） |
| 技能/召唤物 相关 | `verify=FuncsVerify.operator` | 7 | 干员详情页（`main.py:296`） |
| 阵营相关 | `verify=FuncsVerify.group` | 9 | 阵营干员列表（`main.py:327`） |
| `阵营` | `keywords='阵营'` | 8 | 全部阵营总表（`main.py:367`） |
| `/干员查询` | `keywords='/干员查询'` | 10 | 显式入口，带 `force=True` 的追问（`main.py:391`） |

`/干员查询` 是唯一不带 `group_id` 的处理器（`main.py:391`）。

### `FuncsVerify`（`operatorCore.py:61-92`）

| 方法 | 命中条件 | 返回 level |
| --- | --- | --- |
| `level_up` | 消息含「精英」「专精」「材料」（`operatorCore.py:65`） | `default_level + 2` = 10 |
| `operator` | 消息含「技能」「召唤物」；`blockMishap` 配置为真且干员名不等于整条消息且不含「查询」时，强制要求命中条件（`operatorCore.py:75-77`） | `default_level - 1` = 7 |
| `group` | 匹配阵营名；`blockMishap` 逻辑同上（`operatorCore.py:88-90`） | `default_level + 1` = 9 |

三者均返回三元组 `(是否命中, level, OperatorSearchInfo)`。

## 文件结构

| 文件 / 目录 | 职责 |
| --- | --- |
| `operatorCore.py` | `bot` 实例、`default_level`、`OperatorSearchInfo`、`FuncsVerify`、`search_info` 匹配器、`get_index` |
| `operatorInfo.py` | 索引与词典构建：`operator_list`、`skins_map`、`operator_group_map`、`voice_keywords`、`stories_keywords`、jieba 词典 |
| `operatorData.py` | 数据组装：`OperatorData` 各 `@classmethod` 与 `JsonData` 读表（`operatorData.py:11`、`:219`） |
| `main.py` | 9 个 `on_message` 处理器与 `WaitALLRequestsDone` |
| `template/` | 7 套 HTML/CSS：`operatorInfo`、`operatorCost`、`skillsDetail`、`operatorSkin`、`operatorModule`、`operatorToken`、`operatorStory`（档案/模组故事共用），另有 `css/skillType.css`、`font.css`、`js/character.js`、`js/gamedata.js`、字体与背景图 |
| `classify/` | 8 个职业图标 PNG |
| `level/` | 精英化/专精等级图标（`evolve1`、`evolve2`、`master1-3`） |
| `rank/` | 稀有度图标 1–6 星 |
| `config_default.yaml` / `config_schema.json` / `logo.png` | 配置模板与图标 |
| `README.md` / `README_USE.md` / `README_USE-public.md` | 用户可见文档，见上 |
| `__init__.py` | `from .main import bot` |

## 核心实现

### 匹配器 `search_info`（`operatorCore.py:95-128`）

1. 五类索引来源（`operatorCore.py:96-102`）：`name`（`operator_list` + 英文名映射 keys）、`skin_key`
   （`skins_map.keys()`）、`group_key`（`operator_group_map.keys()`）、`voice_key`（`voice_keywords`）、
   `story_key`（`stories_keywords`）。
2. 匹配方法由配置 `searchSetting.similarMode` 决定：真用 `find_most_similar`，假用 `get_longest`
   （`operatorCore.py:111`，`get_longest` 定义于 `:131-137`）。
3. 命中后要求去标点后确实出现在消息中（`operatorCore.py:115`）；消息词数超过 `searchSetting.lengthLimit`
   时直接返回空（`operatorCore.py:108-109`）。
4. 英文名经 `operator_en_name_map` 映射回中文名（`operatorCore.py:118-120`），并要求名字出现在
   `data.text_words` 中（`:122-123`）。
5. 最后绑定 `info.char = ArknightsGameData.operators[info.name]`（`operatorCore.py:125-126`）。

### 索引与词典构建（`operatorInfo.py`）

- `init_operator()`（`:87-110`）：填 `operator_list`、`operator_en_name_map`；用 `chinese_to_digits` +
  `is_contain_digit` 收集含数字的干员名到 `operator_contain_digit_list`；把 `item.team` / `item.group` /
  `item.nation`（排除空值与「未知」）归入 `operator_group_map`；单字名收进 `operator_one_char_list`。
- `set_jieba_dict()`（`:69-84`）：写入 `resource/plugins/operators.txt`，每行 `{干员名} 1 n`；单字名先
  `jieba.del_word(f'兔兔{name}')` 清理历史词，再 `jieba.load_userdict`。
- `init_stories_keywords()`（`:113-127`）：遍历干员 `stories()`，标题去「？」后与数字形式一并存入
  `stories_keywords`。
- `init_skins_keywords()`（`:129-140`）：遍历 `skins()`，跳过「初始」「精英一」「精英二」，以
  `skin_name` 为键建 `skins_map`。
- `voice_keywords`（`operatorInfo.py:23-59`）为固定语音标题列表。

### 序号解析 `get_index`（`operatorCore.py:140-144`）

先用 `OperatorInfo.operator_contain_digit_list` 把文本中的数字型干员名替换掉，再交给
`get_index_from_text`，避免「2」被误判为序号。

### 各处理器

- **模组查询**（`main.py:20-41`）：`OperatorData.find_operator_module(info, is_story)`；含「故事」时由
  `find_operator_module_story` 返回 `[{'name','text'}]` 结构化列表，渲染 `template/operatorStory.html`；
  否则渲染 `template/operatorModule.html`；无模组时提示（`main.py:37`）。
- **语音查询**（`main.py:44-156`）：支持中日英韩俄德方言意大利共 8 种语言分支，映射为 `voice_type` 后缀
  （`_cn` / `_en` / `_kr` / `_custom` / `_ita`，`main.py:48-70`）。带 `skin_key` 时从
  `JsonData.get_json_data('charword_table')['charWords']` 中按 `wordKey`（由 skin_id 的 `@` 替换为 `_`
  得到）筛出皮肤专属语音（`main.py:84-94`）。未指定语音时列出全部语音的 Markdown 表格并等待序号
  （`main.py:115-131`）；命中后调用 `ArknightsGameDataResource.get_voice_file(opt, voice_key, voice_type,
  skin_key)` 取语音文件并 `reply.voice(file)`（`main.py:148-152`）。
- **档案查询**（`main.py:159-212`）：`opt.stories()` 取全部档案，列出标题表格等待序号。命中后先经
  `ArknightsGameDataResource.parse_template([], story_text)` 把游戏原始富文本标签转成 HTML，再渲染
  `template/operatorStory.html`（`main.py:201-210`）——**不能走 `.markdown()`**，它生成的是 Markdown
  图片，会把 `<span>` 当普通字符绘制。
- **皮肤查询**（`main.py:211-264`）：`opt.skins()` 列立绘，命中后组装 `skin_data`（含 `name` / `data` /
  `path`），`path` 来自 `ArknightsGameDataResource.get_skin_file(skin_item, encode_url=True)`；渲染
  `template/operatorSkin.html`；配置 `operatorSkin.showImage` 为真时额外直接发送图片（`main.py:261-263`）。
- **技能与材料**（`main.py:267-293`）：消息含「材料」走 `OperatorData.get_level_up_cost` +
  `operatorCost.html`；否则 `get_skills_detail` + `skillsDetail.html`。稀有度 ≤ 2 的干员分别提示不需要
  材料 / 没有技能（`main.py:278-285`）。
- **干员详情**（`main.py:296-324`）：含「技能」走技能页；否则 `OperatorData.get_operator_detail` 返回
  `(result, tokens)`，渲染 `operatorInfo.html`（宽度 1600）；有召唤物或配置 `operatorInfo.showToken`
  为真时再渲染 `operatorToken.html`。
- **阵营查询**（`main.py:327-364`）：按实例类型分流 —— Mirai 用 `MiraiForwardMessage`、CQHTTP 用
  `CQHTTPForwardMessage` 组装合并转发消息，逐干员渲染 `operatorInfo.html` 后 `reply.send()`；其他平台
  退化为 Markdown 列表（`main.py:343-348`）。发送前先提示「正在查询，博士请稍等...」（`main.py:350`）。
- **阵营总表**（`main.py:367-388`）：按稀有度着色（6 星 `#FF4343`、5 星 `#FEA63A`、4 星 `#A288B5`），
  输出 Markdown 表格。

### HTML 渲染同步

`WaitALLRequestsDone`（`main.py:14-17`）继承 `ChainBuilder` 并重写 `on_page_rendered`，等待
`networkidle` 后再截图，确保页面资源加载完成。仅在模组渲染处显式传入
（`main.py:41`）。

## 依赖的 core 能力

- `core.Chain`、`core.Message`（`main.py:6`）；`core.AmiyaBotPluginInstance`、`Requirement`（`operatorCore.py:7`）、
  `log`（`operatorInfo.py:6`）。
- `core.resource.arknightsGameData.ArknightsGameData`、`ArknightsGameDataResource`（`main.py:7`、`operatorCore.py:9`）。
- `core.util`：`any_match`、`find_most_similar`、`get_index_from_text`、`remove_punctuation`、
  `chinese_to_digits`、`is_contain_digit`、`create_dir`（`operatorCore.py:8`、`operatorInfo.py:7`）。
- `amiyabot`：`ChainBuilder`（`main.py:2`）、`GroupConfig` / `event_bus`（`operatorCore.py:5`）、
  `MiraiForwardMessage` / `CQHttpBotInstance`（`main.py:3-4`）。
- 第三方 `jieba`（`operatorInfo.py:3`）。

## 写入的表 / 目录 / 缓存

- **无独立数据表。**
- 文件：`resource/plugins/operators.txt`（jieba 用户词典，`operatorInfo.py:71-84`）。
- 内存索引：`OperatorInfo` 上的全部索引，以及 `JsonData.cache`（`operatorData.py:219-232`，
  `get_json_data(name, folder='excel')` 按文件名缓存 JSON）。
- 立绘与语音文件由 gamedata 插件注入的函数落盘缓存至 `resource/gamedata/`。

## 与其他插件耦合

- `Requirement('amiyabot-arknights-gamedata', official=True)`（`operatorCore.py:46`）。
- 订阅 `gameDataInitialized` 并在事件触发时**整体重装自己**（`operatorCore.py:22-33`），因为需要三个
  `init_*` 全部重跑；回调中先用 `asyncio.get_running_loop()` 守卫。
- 通过 `ArknightsGameDataResource.get_skin_file` / `get_voice_file` 调用 gamedata 插件注入的实现。

## 打包与发布

```bash
python run_build.py --type plugins
```

产物为 `amiyabot-arknights-operator-6.3.zip`（`{plugin_id}-{version}.zip`）。

## 配置

| 配置项 | 读取处 | 含义 |
| --- | --- | --- |
| `searchSetting.similarMode` | `operatorCore.py:105` | 真用 `find_most_similar`，假用 `get_longest` |
| `searchSetting.lengthLimit` | `operatorCore.py:106` | 消息词数上限，超出则不匹配 |
| `operatorInfo.blockMishap` | `operatorCore.py:75`、`:88` | 误触发抑制开关 |
| `operatorInfo.showToken` | `main.py:319` | 是否总是渲染召唤物页 |
| `operatorSkin.showImage` | `main.py:261` | 是否额外直接发送立绘图 |
