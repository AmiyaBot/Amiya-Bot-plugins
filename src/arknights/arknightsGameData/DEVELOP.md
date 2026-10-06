# arknightsGameData 开发说明

全部 arknights 功能的数据源插件。以 `priority=999` 最先安装，把游戏数据解析进 core 的静态类，再通过
`event_bus` 广播就绪信号。

## 使用指引

- 同目录 [README.md](README.md)：面向用户的使用指引，由 `document=f'{curr_dir}/../README.md'` 加载
  （`pluginsDev/src/arknights/arknightsGameData/builder/__init__.py:45`），用户发送宿主的 `功能` / `帮助`
  指令时会看到其内容。**修改本文件即改变用户可见文本，勿将其当作开发文档编辑。**
- 配置模板 `config_default.yaml` + `config_schema.json` 位于**上一级** `pluginsDev/src/arknights/`
  目录，通过 `f'{curr_dir}/../'` 引用（`builder/__init__.py:46-47`）。

## 插件注册信息

| 项 | 值 |
| --- | --- |
| 类 | `ArknightsGameDataPluginInstance`（`builder/__init__.py:27-49`） |
| plugin_id | `amiyabot-arknights-gamedata` |
| name / version | 明日方舟数据解析 / `4.2` |
| plugin_type | `official` |
| priority | **`999`**（`builder/__init__.py:48`） |
| 配置 | `global_config_schema` / `global_config_default` 指向上一级的 `config_schema.json` / `config_default.yaml` |
| Requirement | 无（它是被依赖方） |

`priority=999` 的含义：宿主 `PluginsLoader.install_loaded_plugins()` 按 `priority` **倒序**安装插件，
999 使本插件成为**全局第一个安装**的插件，从而保证其它 arknights 插件加载时数据已经就绪。

## 触发方式与指令

三条运维指令均**限定管理员**，判定方式是处理函数内的 `Admin.get_or_none(account=data.user_id)`
（非框架的 `level`），非管理员返回 `None` 静默忽略：

| 指令 | 匹配方式 | 说明 |
| --- | --- | --- |
| `更新资源` | `keywords=Equal('更新资源')` | 检查并拉取游戏资源（`arknightsGameData/main.py:17-35`） |
| `解析资源` | `keywords=Equal('解析资源')` | 重新解析已下载的数据（`arknightsGameData/main.py:38-49`） |
| `清除立绘缓存` | `keywords=Equal('清除立绘缓存')` | 删除 `{gamedata_path}/skin`（`arknightsGameData/main.py:52-61`） |

`更新资源` 的前置校验：若 `gamedata_path` 存在却缺 `version.txt`，先 `shutil.rmtree` 清理脏目录再重试
（`arknightsGameData/main.py:22-27`）。

## 文件结构

| 路径 | 作用 |
| --- | --- |
| `builder/__init__.py` | 插件实例、`install` / `uninstall`、事件定义、四类数据解析入口、资源注入（399 行） |
| `builder/operatorBuilder.py` | `OperatorImpl` / `TokenImpl` / `Collection` / `parse_template`，干员数据模型与收藏集构建（609 行） |
| `builder/common.py` | `ArknightsConfig`、`JsonData`（JSON 读取与缓存）、`SkinsPathCache`（立绘缓存表）、`gamedata_path` |
| `builder/wiki.py` | `PRTS`：语音文件路径解析与批量下载 |
| `builder/sklandApi.py` | 森空岛 API 相关辅助（`*` 导入到 `builder/__init__.py:17`） |
| `main.py` | 三条管理员指令 |
| `config_default.yaml` / `config_schema.json` / `logo.png` | 位于上一级 `arknights/` 目录，供本插件引用 |
| `__init__.py` | `from .main import bot` |

## 核心实现

### 完整时序

```
install()                                     builder/__init__.py:28-32
  ├─ autoUpdate 为真 或 resource/gamedata 不存在
  │    └─ download_gamedata()                 builder/__init__.py:59-66
  │         ├─ 目录存在但缺 version.txt → 仅告警返回        builder/__init__.py:60-62
  │         ├─ GitAutomation(gamedata_path, repo).update(['--depth 1'])   builder/__init__.py:64
  │         │     repo = https://gitee.com/amiya-bot/amiya-bot-assets.git  builder/__init__.py:20
  │         └─ event_bus.publish('gameDataFetched')         builder/__init__.py:66
  │              └─ @event_bus.subscribe('gameDataFetched') → initialize_data()
  │                                                         arknightsGameData/main.py:12-14
  └─ 否则直接 initialize_data()               builder/__init__.py:32

initialize_data()                             builder/__init__.py:52-56
  ├─ ArknightsConfig.initialize()
  ├─ ArknightsGameData.initialize()  → 触发 gamedata_initialize()
  └─ event_bus.publish('gameDataInitialized') builder/__init__.py:56
```

### `gamedata_initialize`（`builder/__init__.py:69-97`）

1. 校验 `resource/gamedata/version.txt` 存在，否则返回 `None`（`:71-72`）。
2. `extract_zip(f'{gamedata_path}/gamedata.zip', f'{gamedata_path}/gamedata', overwrite=True)` 解压（`:74`）。
3. 读 `version.txt` 写入 `cls.version`（`:76-77`）。
4. 读 `indexes/skinUrls.json`，把 `skin_id -> url` 填进 `SkinIndexes.url_indexes`（`:81-86`）。
5. **固定顺序**解析四类数据（`:88-91`）：

| 顺序 | 赋值 | 定义处 | 数据源 |
| --- | --- | --- | --- |
| 1 | `cls.enemies = init_enemies()` | `:236-261` | `enemy_handbook_table` + `levels/enemydata/enemy_database` |
| 2 | `cls.stages, cls.stages_map, cls.side_story_map = init_stages()` | `:264-363` | `activity_table`、`character_table`、`stage_table`、`item_table`、`levels/` |
| 3 | `cls.operators, cls.tokens, cls.birthday = init_operators()` | `:100-181` | `character_table`、`char_patch_table`、`gacha_table`、`building_table` |
| 4 | `cls.materials, cls.materials_map, cls.materials_made, cls.materials_source = init_materials()` | `:184-233` | `item_table.items` |

6. 写库：`OperatorIndex.truncate_table()` → `OperatorIndex.batch_insert([item.dict() for _, item in cls.operators.items()])`
   （`:93-94`），再 `JsonData.clear_cache()`（`:95`）。

### `init_enemies`（`builder/__init__.py:236-261`）

合并 `enemy_handbook_table` 与 `enemy_database`（`levels/enemydata`）。数据源的键名有 `Key`/`Value` 与
`key`/`value` 两种写法，做兼容（`:242-245`）。同名敌人追加序号「（n）」（`:254-256`），并以 `name` 与
`enemyId` 双键注册（`:259`）。

### `init_stages`（`builder/__init__.py:264-363`）

- `is_ss` 判定活动类型（`:271-282`）：`isReplicate` 为真排除；`MINISTORY`、`BRANCHLINE`、`SIDESTORY`、
  `type` 以 `SIDE` 结尾均算，按 `startTime` 倒序。
- 关卡难度后缀由 stage_id 特征映射（`:300-308`）：`#f#` → `_hard`、`easy` → `_easy`、`tough` → `_tough`、
  `#s` → `_sixstar`。
- 从 `levels/` 加载关卡数据，遍历 `waves[].fragments[].actions[]`，取 `actionType` 为 `SPAWN` 或 `0`
  的动作统计敌人数量（`:315-331`）；敌人 key 需在 `enemy_handbook_table` 中，找不到时尝试去掉末 2 字符匹配。
- 关卡名去标点后与代号一起写入 `stages_map`，同一 key 可对应多个 stageId（`:356-361`）。
- 活动归属判定（`:344-354`）：`GT` 前缀 → 「骑兵与猎人」、`OF` 前缀 → 「火蓝之心」，其余按活动 id
  是否出现在 stage_id 中匹配。

### `init_operators`（`builder/__init__.py:100-181`）

- 从 `gacha_table.recruitDetail` 用正则 `★\n(.*)` 解析公招干员名单（`:101-106`），据此设置每个
  `OperatorImpl` 的 `is_recruit`。
- 合并 `character_table` 与 `char_patch_table.patchChars`（`:108-113`）。
- `Collection` 收集三类映射：`voice_map`（按 `wordKey` 聚合语音，`:117-123`）、`skins_map`（按 `charId`
  聚合皮肤，含阿米娅近卫/医疗的特殊 charId 改写，`:125-138`）、`tokens_map`（`profession` 不在
  `ArknightsConfig.classes` 中的视为召唤物，`:144-149`）。
- 从「基础档案」文案用正则提取生日 `【(生日|出厂日)】.*?(\d+)月(\d+)日` 与性别 `性别】(\S+)`
  （`:155-173`），`birthday` 最终按月份、日期排序（`:176-181`）。

### `init_materials`（`builder/__init__.py:184-233`）

遍历 `item_table.items`（跳过含 `p_char` 的项），从 `stageDropList` 建产出地点 `materials_source`，
从 `buildingProductList` + `workshopFormulas` / `manufactFormulas` 建合成配方 `materials_made`。

### 向 core 静态类反向注入

本插件不定义 `ArknightsGameData` 类，而是**把自己的实现挂到 core 的静态类上**（`builder/__init__.py:395-399`）：

| 挂载目标 | 注入内容 | 定义处 |
| --- | --- | --- |
| `ArknightsGameData.initialize_methods` | `gamedata_initialize` | `:69-97` |
| `ArknightsGameData.get_real_name` | `PRTS.get_real_name` | `:391` |
| `ArknightsGameDataResource.get_skin_file` | `get_skin_file` | `:366-377` |
| `ArknightsGameDataResource.get_voice_file` | `get_voice_file` | `:380-388` |
| `ArknightsGameDataResource.parse_template` | `parse_template` | 来自 `operatorBuilder` |

因此其他插件调用 `ArknightsGameDataResource.get_skin_file(...)` 时，实际执行的是本插件的实现。
静态类 `ArknightsGameData` / `ArknightsGameDataResource` / `ArknightsConfig` 定义在
`core/resource/arknightsGameData.py`，本插件只填充数据与方法。

- `get_skin_file`（`:366-377`）：按 `skin_id` 查 `SkinIndexes.url_indexes`，把 URL 中的 `quality,Q_90`
  替换为配置值，经 `SkinsPathCache.get_skin_file` 下载缓存；`encode_url` 为真时把 `#` 转义为 `%23`。
- `get_voice_file`（`:380-388`）：委托 `PRTS.get_voice_path` / `PRTS.download_operator_voices`。

### `uninstall`（`builder/__init__.py:34-36`）

解除 `gameDataFetched` 订阅，并从 `ArknightsGameData.initialize_methods` 移除 `gamedata_initialize`。

## 依赖的 core 能力

- `core.resource.arknightsGameData`：`ArknightsGameData`、`ArknightsGameDataResource`、`ArknightsConfig`、
  `STR_DICT_MAP`、`STR_DICT_LIST`（`builder/__init__.py:9`）。
- `core.database.bot.OperatorIndex`（`builder/__init__.py:10`）；`core.database.bot.Admin`（`main.py:7`）。
- `core.util`：`remove_xml_tag`、`remove_punctuation`、`sorted_dict`、`create_dir`、`run_in_thread_pool`、
  `integer`、`TimeRecorder`（`builder/__init__.py:11`、`operatorBuilder.py:7`、`main.py:6`）。
- `core`：`AmiyaBotPluginInstance`、`GitAutomation`、`log`（`builder/__init__.py:12`）。
- `amiyabot.util.extract_zip`（`builder/__init__.py:7`）、`amiyabot.event_bus`（`builder/__init__.py:6`）。

`GitAutomation` 属宿主能力，负责执行 `update(['--depth 1'])` 浅克隆。

## 写入的表 / 目录 / 缓存

| 类型 | 名称 | 位置 |
| --- | --- | --- |
| 表 | `OperatorIndex` | 先 `truncate_table()` 再 `batch_insert`（`builder/__init__.py:93-94`） |
| 表 | `SkinsPathCache` | 立绘缓存索引，按 `skin_id` 记录 `skin_path` + `quality`（`builder/common.py:32-64`） |
| 目录 | `resource/gamedata/` | git 仓库、`gamedata.zip`、解压后的 `gamedata/`、`version.txt`、`indexes/`、`skin/`、`map/`、`levels/`、`avatar/`、`portrait/`，由 `gamedata_path` 决定（`builder/common.py:28`） |
| 内存缓存 | `JsonData.cache` | `get_json_data(name, folder='excel')` 读取入口，解析完统一 `clear_cache()`（`builder/__init__.py:95`） |

`OperatorConfig` 表由宿主/其他插件维护，本插件只读（`builder/common.py:73-78`）。

## 与其他插件耦合

- **全部 arknights 插件的数据提供者**。
- 通过 `ArknightsGameDataResource.get_skin_file` / `get_voice_file` 实现**反向注入**，其他插件调用时
  实际执行本插件代码。
- 发布事件：
  - `gameDataFetched`：仅本插件自己订阅（`arknightsGameData/main.py:12-14`），用于把「下载完成」转成
    「开始解析」。
  - `gameDataInitialized`：由 `operatorArchives`、`material`、`stage`、`recruit` 四个插件订阅，用于重建
    各自索引。`event_bus.publish` 同步且不重放，故订阅者若晚于本插件加载会错过该事件，各自仍在
    `install()` 中自建索引。

## 打包与发布

```bash
python run_build.py --type plugins
```

产物为 `amiyabot-arknights-gamedata-4.2.zip`（`{plugin_id}-{version}.zip`）。

## 配置

| 配置项 | 读取处 | 含义 |
| --- | --- | --- |
| `autoUpdate` | `builder/__init__.py:29` | 为真时每次启动都重新拉取资源 |
| `quality` | `builder/common.py:38` | 立绘下载质量，默认 `90`；与 `SkinsPathCache` 中记录的值比对决定是否重下（`builder/common.py:44-60`） |
