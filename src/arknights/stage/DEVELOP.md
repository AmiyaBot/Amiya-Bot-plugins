# stage 开发说明

查询关卡敌人配置、掉落与地图图片，支持活动关卡列表
（`pluginsDev/src/arknights/stage/main.py:37-54`）。

## 使用指引

- 同目录 [README.md](README.md)：面向用户的使用指引，由 `document=f'{curr_dir}/README.md'` 加载
  （`stage/main.py:52`），用户发送宿主 `功能` / `帮助` 指令时可见。**勿将其当作开发文档编辑。**
- `README-public.md`：对外发布版本的说明，源码中未见引用。

## 插件注册信息

| 项 | 值 |
| --- | --- |
| 类 | `StagePluginInstance`（`stage/main.py:37`） |
| plugin_id | `amiyabot-arknights-stages` |
| name / version | 明日方舟关卡查询 / `2.7` |
| plugin_type | `official` |
| priority | 未声明 |
| Requirement | `Requirement('amiyabot-arknights-gamedata', official=True)`（`stage/main.py:53`） |
| 消息组 | 无（用 `allow_direct=True` 单点声明） |
| 缓存目录 | `cache_dir = 'resource/plugins/stages'`（`stage/main.py:15`） |

- `install()`（`stage/main.py:38-40`）：`create_dir(cache_dir)` 后起异步任务 `Stage.init_stages()`。
- `uninstall()`（`stage/main.py:42-43`）：解除 `gameDataInitialized` 订阅。

本插件**没有** `config_default.yaml` / `config_schema.json`，不读取任何插件配置。

## 触发方式与指令

| 指令 / 关键词 | 匹配方式 | level | 说明 |
| --- | --- | --- | --- |
| `地图`、`关卡` | `keywords=['地图','关卡']`，`allow_direct=True` | 5 | 主查询入口（`stage/main.py:67`） |

## 文件结构

| 文件 / 目录 | 作用 |
| --- | --- |
| `main.py` | 全部实现：`Stage.init_stages`、`multiple_zone_stage` 常量、单个处理器（175 行） |
| `sxys.json` | 活动地图名 → 图片 key 的映射表（静态资源） |
| `template/stage.html` + `stage.css` | 关卡详情模板 |
| `template/img/` | `enemy.png`、`pc_bg.jpeg` |
| `template/font.css` + `HarmonyOS_Sans_SC.ttf` | 字体 |
| `template/js/vue.min.js` | 前端渲染库 |
| `logo.png` | 插件图标 |
| `README.md` / `README-public.md` | 用户可见文档，见上 |
| `__init__.py` | `from .main import bot` |

## 核心实现

1. **jieba 词典构建 `init_stages`**（`stage/main.py:25-34`）：把 `ArknightsGameData.stages_map` 与
   `side_story_map` 的全部键写成 `{name} 500 n` 格式的 `resource/plugins/stages/stages.txt`
   （`stage/main.py:31-32`），再 `jieba.load_userdict` 加载（`stage/main.py:34`），使关卡代号可被分词
   正确切出。
2. **sxys 地图短路分支**（`stage/main.py:74-91`）：读取插件自带 `sxys.json`。同时用原键与去标点键
   （保留 `-`）建立两张查找表，`any_match` 命中后从 COS 下载
   `https://amiyabot-1302462817.cos.ap-guangzhou.myqcloud.com/resource/maps/{key}.jpg` 到缓存目录并
   直接发图。
3. **难度后缀解析**（`stage/main.py:93-108`）：先 `jieba.lcut` 分词，再按关键词映射难度 —— `突袭` →
   `_hard`、`简单`/`剧情` → `_easy`、`困难`/`磨难` → `_tough`、`险地` → `_sixstar`，并生成展示用
   后缀文案。
4. **关卡匹配**（`stage/main.py:110-136`）：对每个分词结果尝试 `item + level` 在 `stages_map` 中查找。
   多个同名/同代号关卡时列出 `[序号] {code} {name}` 让用户回复序号。
5. **关卡渲染**（`stage/main.py:138-154`）：组装 `res`，其中 `zones` 从 `multiple_zone_stage` 常量取
   （`CF-9`、`CF-EX-8`、`CF-S-1` 为 2，`stage/main.py:17-21`）。剧情难度（`_easy`）复用 `main` 关卡的
   `levelData`（`stage/main.py:146-149`）。若 `resource/gamedata/map/{stageId}.png` 不存在，把
   `tough`/`easy` 替换为 `main` 以复用地图（`stage/main.py:151-152`）。最终渲染 `template/stage.html`。
6. **活动列表**（`stage/main.py:155-173`）：关卡未命中时，若分词结果命中 `side_story_map` 的活动名，
   则以 Markdown 表格列出该活动全部关卡（`difficulty == 'FOUR_STAR'` 者标注「突袭」）；若消息含
   「活动」则列出全部活动名。

消息解析用正则 `r'(/)?([地图|关卡])?(.*)'`（`stage/main.py:69`），第 3 组为空时仅提示用法
（`stage/main.py:71-72`）。

## 依赖的 core 能力

- `core.log`、`Message`、`Chain`、`AmiyaBotPluginInstance`、`Requirement`（`stage/main.py:10`）。
- `core.util`：`any_match`、`remove_punctuation`、`get_index_from_text`、`create_dir`（`stage/main.py:11`）。
- `core.resource.arknightsGameData.ArknightsGameData`（`stage/main.py:12`）。
- `amiyabot.event_bus`（`stage/main.py:7`）、`amiyabot.network.download.download_async`
  （`stage/main.py:8`）、第三方 `jieba`（`stage/main.py:4`）。

## 写入的表 / 目录 / 缓存

无数据表。

| 类型 | 路径 | 说明 |
| --- | --- | --- |
| 文件 | `resource/plugins/stages/stages.txt` | jieba 用户词典，每次 install 覆盖写（`stage/main.py:31-32`） |
| 文件 | `resource/plugins/stages/{key}.jpg` | sxys 活动地图图片缓存（`stage/main.py:82-89`） |
| 静态资源 | `sxys.json` | 随插件分发，不被写入 |

## 与其他插件耦合

- `Requirement('amiyabot-arknights-gamedata', official=True)`（`stage/main.py:53`）。
- 订阅 `gameDataInitialized` 并**整体重装自己**（`stage/main.py:57-64`），因为需要重新生成 jieba 词典
  文件；回调中先用 `asyncio.get_running_loop()` 守卫。
- 依赖 `ArknightsGameData.stages` / `stages_map` / `side_story_map` 三个静态字段。
- 依赖 `resource/gamedata/map/` 下的地图图片（由 gamedata 插件拉取）判断地图是否存在
  （`stage/main.py:151`）。

## 打包与发布

```bash
python run_build.py --type plugins
```

产物为 `amiyabot-arknights-stages-2.7.zip`（`{plugin_id}-{version}.zip`）。
