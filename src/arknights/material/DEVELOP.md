# material 开发说明

查询材料掉落地点、合成配方与最优刷取关卡，掉率数据来自 yituliu.cn
（`pluginsDev/src/arknights/material/main.py:205-224`）。

## 使用指引

- 同目录 [README.md](README.md)：面向用户的使用指引，由 `document=f'{curr_dir}/README.md'` 加载
  （`material/main.py:220`），用户发送宿主 `功能` / `帮助` 指令时可见。**勿将其当作开发文档编辑。**
- `README-public.md`：对外发布版本的说明，源码中未见引用。

## 插件注册信息

| 项 | 值 |
| --- | --- |
| 类 | `MaterialPluginInstance`（`material/main.py:205`） |
| plugin_id | `amiyabot-arknights-material` |
| name / version | 明日方舟材料物品查询 / `2.8` |
| plugin_type | `official` |
| priority | 未声明 |
| Requirement | `Requirement('amiyabot-arknights-gamedata', official=True)`（`material/main.py:223`） |
| 消息组 | 无 |

- `install()`（`material/main.py:206-208`）起两个异步任务：`save_yituliu_data()` 与 `init_materials()`。
- `uninstall()`（`material/main.py:210-211`）解除 `gameDataInitialized` 订阅。

## 触发方式与指令

| 指令 / 关键词 | 匹配方式 | level | 说明 |
| --- | --- | --- | --- |
| 材料名 / `查询` / `材料` | `verify=verify`，`allow_direct=True` | 动态 5 或 1 | 主查询入口（`material/main.py:258`） |
| 定时刷新 | `@bot.timed_task(each=3600)` | — | 每小时刷新 yituliu 数据（`material/main.py:277-279`） |

无固定 `keywords` 指令，仅靠 `verify` 语义匹配。

### `verify`（`material/main.py:237-255`）

1. 消息词数超过 `searchSetting.lengthLimit` 返回 `False`（`material/main.py:238-240`）。
2. 剔除「材料」「阿米娅」后用 `find_most_similar` 在 `MaterialData.materials` 中找材料名
   （`material/main.py:242`）。
3. `keyword = any_match(data.text, ['查询', '材料'])`；非关键词触发时要求匹配到的名字确实出现在消息中
   （`material/main.py:243-246`）。
4. 返回值 `(True, (5 if keyword else 1), name)`，即关键词触发等级更高（`material/main.py:253`）。
5. `blockMishap` 为真且名字不等于整条消息且无关键词时返回 `False`（`material/main.py:249-251`）。

## 文件结构

| 文件 / 目录 | 作用 |
| --- | --- |
| `main.py` | 全部实现：`YituliuData` 表、`MaterialData` 工具类、`verify`、处理器、定时任务（279 行） |
| `template/material.html` + `material.css` | 材料详情模板（合成树 + 产出关卡 + 推荐） |
| `template/img/pc_bg.jpeg` | 背景图 |
| `template/font.css` + `HarmonyOS_Sans_SC.ttf` | 字体 |
| `template/js/vue.min.js` | 前端渲染库 |
| `config_default.yaml` / `config_schema.json` / `logo.png` | 配置模板与图标 |
| `README.md` / `README-public.md` | 用户可见文档，见上 |
| `__init__.py` | `from .main import bot` |

## 核心实现

1. **数据表 `YituliuData`**（`material/main.py:27-34`）：`@table class YituliuData(BotBaseModel)`，
   字段 `materialId`、`stageId`、`stageEfficiency`、`apExpect`、`knockRating`、`sampleConfidence`。
2. **`save_yituliu_data`**（`material/main.py:40-83`）：拉取 `yituliu_t3`
   （`https://backend.yituliu.cn/stage/t3?expCoefficient=0.625`）与 `yituliu_t2`（同 `t2`，
   `material/main.py:23-24`）两个接口。每个响应的 `data` 是「同一材料下多个关卡」的嵌套数组，取
   `i[0]['itemId']` 为材料 ID；特殊处理 `30012` → `30013`（`material/main.py:52-53`）。合并两个来源后
   `truncate_table()` + `batch_insert()`（`material/main.py:80-81`）。
3. **`init_materials`**（`material/main.py:85-90`）：把 `ArknightsGameData.materials_map` 的全部键拷进
   类变量 `MaterialData.materials`，作为相似度匹配的候选池。
4. **`find_material_children`**（`material/main.py:92-111`）：递归展开合成树。以
   `materials_made[material_id]` 为子节点来源，对每个子材料附带其 `materials` 元信息与更深层的
   `children`；用 `parent_id` 参数防止回到父节点形成环（`material/main.py:104-107`）。
5. **`check_material`**（`material/main.py:113-166`）：
   - 组装 `result`：`name`、`info`（材料元数据）、`children`（合成树）、`source.main` / `source.act`
     （产出关卡）、`recommend`（yituliu 推荐）。
   - `find_yituliu_data([material, *children])`（`material/main.py:168-178`）递归收集各材料的掉落数据。
   - 推荐关卡按 `compare_efficiency` 排序（`material/main.py:134`）。
   - 产出地点来自 `ArknightsGameData.materials_source`，按关卡 ID 是否含 `main` 分流到 `source.main`
     或 `source.act`（`material/main.py:151-164`）。
6. **三级排序器**（`material/main.py:180-202`）：`compare_knock_rating` 比掉率 → `compare_ap_expect`
   先比理智期望（差异 > 3% 才判定优劣，否则回退到掉率） → `compare_efficiency` 先比效率（同样 3%
   阈值，否则回退到理智期望）。用 `cmp_to_key` 包装后 `sorted(..., reverse=True)`。
7. **查询流程**（`material/main.py:258-274`）：`name` 为空时 `data.wait` 询问材料名并对回复做
   `find_most_similar`；最终 `MaterialData.check_material(name)` 渲染 `template/material.html`。

## 依赖的 core 能力

- `core.log`、`Message`、`Chain`、`AmiyaBotPluginInstance`、`Requirement`（`material/main.py:9`）。
- `core.util`：`any_match`、`find_most_similar`、`remove_punctuation`（`material/main.py:10`）。
- `core.database.bot.*`：`BotBaseModel` 等（`material/main.py:11`）。
- `core.resource.arknightsGameData.ArknightsGameData`（`material/main.py:12`）。
- `amiyabot.event_bus`（`material/main.py:6`）、`amiyabot.network.httpRequests.http_requests`
  （`material/main.py:7`）、`functools.cmp_to_key`（`material/main.py:14`）。

## 写入的表 / 目录 / 缓存

| 类型 | 名称 | 说明 |
| --- | --- | --- |
| 表 | `YituliuData` | 每次刷新做 `truncate_table()` + `batch_insert()` 全量替换（`material/main.py:80-81`） |
| 内存 | `MaterialData.materials` | 材料名候选池，`install()` 与事件回调均会重建（`material/main.py:85-90`） |

不受 `bot.install()` 重装影响，事件回调只重建内存中的材料名列表（`material/main.py:227-234`）。

## 与其他插件耦合

- `Requirement('amiyabot-arknights-gamedata', official=True)`（`material/main.py:223`）。
- 订阅 `gameDataInitialized` 重建材料名列表（`material/main.py:227-234`），回调中先用
  `asyncio.get_running_loop()` 守卫。
- 与 gamedata 插件的 `materials` / `materials_map` / `materials_made` / `materials_source` 四个静态
  字段强耦合。
- `install()` 的 `create_task(save_yituliu_data())` 与 `timed_task(each=3600)` 都会触发同一函数，
  二者均做全表替换（`material/main.py:207`、`material/main.py:277`）。

## 打包与发布

```bash
python run_build.py --type plugins
```

产物为 `amiyabot-arknights-material-2.8.zip`（`{plugin_id}-{version}.zip`）。

## 配置

| 配置项 | 默认值 | 读取处 | 含义 |
| --- | --- | --- | --- |
| `searchSetting.lengthLimit` | `5` | `material/main.py:238` | 消息词数上限，超出则不匹配 |
| `blockMishap` | `false` | `material/main.py:249` | 误触发抑制开关 |
