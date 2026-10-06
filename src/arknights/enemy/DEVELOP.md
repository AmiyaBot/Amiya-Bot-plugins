# enemy 开发说明

查询敌方单位各等级属性与关联单位，渲染为 HTML 图片（`pluginsDev/src/arknights/enemy/main.py:86-99`）。

## 使用指引

- 同目录 [README.md](README.md)：面向用户的使用指引，由 `document=f'{curr_dir}/README.md'` 加载
  （`enemy/main.py:95`），用户发送宿主 `功能` / `帮助` 指令时可见。**勿将其当作开发文档编辑。**
- `README-public.md`：对外发布版本的说明，源码中未见引用。

## 插件注册信息

| 项 | 值 |
| --- | --- |
| 类 | `EnemiesPluginInstance`（`enemy/main.py:86`） |
| plugin_id | `amiyabot-arknights-enemy` |
| name / version | 明日方舟敌方单位查询 / `3.7` |
| plugin_type | `official` |
| priority | 未声明 |
| Requirement | `Requirement('amiyabot-arknights-gamedata', official=True)`（`enemy/main.py:98`） |
| 消息组 | 无 |

## 触发方式与指令

| 指令 / 关键词 | 匹配方式 | level | 说明 |
| --- | --- | --- | --- |
| `/敌方单位` | `keywords='/敌方单位'` | 5 | 仅提示用法（`enemy/main.py:145-147`） |
| 敌方单位名 | `verify=verify`，`allow_direct=True` | 动态 1 或 6 | 主查询入口（`enemy/main.py:150`） |

### `verify`（`enemy/main.py:102-142`）

1. 消息词数超过配置 `searchSetting.lengthLimit` 直接返回 `False`（`enemy/main.py:103-105`）。
2. 正则 `(/)?(敌[人|方])?(单位)?(资料)?(.*)` 取第 5 组为候选名（`enemy/main.py:109-111`）。
3. 先查 `enemyIndex` 精确映射（按索引号找名字），否则 `find_most_similar` 在全部敌人名中找最相似
   （`enemy/main.py:113-121`）。
4. `level = (5 + int(bool(name))) if keyword else 1`，即以「查询」/「敌人」/「敌方」触发时等级更高
   （`enemy/main.py:123-124`）。
5. `blockMishap` 配置为真且名字不等于整条消息且无关键词时返回 `False`（`enemy/main.py:126-128`）。
6. 排除单体名 `-`、以及非关键词触发时的 `w` 与 `「阿米娅」`（`enemy/main.py:130-137`）。

## 文件结构

| 文件 / 目录 | 作用 |
| --- | --- |
| `main.py` | 全部实现：`Enemy` 工具类、`verify`、两个 `on_message` 处理器（189 行） |
| `template/enemy.html` + `enemy.css` | 单个敌方单位属性表模板 |
| `template/enemyIndex.html` + `enemyIndex.css` | 多结果序号选择模板 |
| `template/img/` | `enemy.png`、`pc_bg.jpeg` |
| `template/font.css` + `HarmonyOS_Sans_SC.ttf` | 字体 |
| `template/js/vue.min.js` | 前端渲染库 |
| `config_default.yaml` / `config_schema.json` / `logo.png` | 配置模板与图标 |
| `README.md` / `README-public.md` | 用户可见文档，见上 |
| `__init__.py` | `from .main import bot` |

## 核心实现

1. **`Enemy.find_enemies`**（`enemy/main.py:15-23`）：遍历 `ArknightsGameData.enemies`，按小写精确匹配
   或（长度 > 1 时）子串匹配，返回 `[name, item]` 列表。
2. **`Enemy.get_enemy`**（`enemy/main.py:25-76`）：以 `key_map` 声明 19 个属性路径
   （`enemy/main.py:27-47`）——`attributes.maxHp`、`attributes.atk`、`attributes.def`、
   `attributes.magicResistance`、`attributes.moveSpeed`、`attributes.baseAttackTime`、
   `attributes.hpRecoveryPerSec`、`attributes.massLevel`、各免疫标记 `stunImmune` / `silenceImmune` /
   `sleepImmune` / `frozenImmune` / `levitateImmune` / `disarmedCombatImmune` / `fearedImmune` /
   `palsyImmune` / `attractImmune`、`rangeRadius`、`lifePointReduce`。
   遍历敌人各等级数据（`item['level']` 为第一维），逐 key 用 `get_value` 取值，取不到则沿用上一个等级
   的值（`enemy/main.py:56-68`）——实现属性的等级间继承。
3. **`Enemy.get_value`**（`enemy/main.py:78-83`）：按 `.` 逐级下钻 source，最终返回
   `(source['m_defined'], integer(source['m_value']))`，`m_defined` 用于判断该属性是否真实定义。
4. **关联单位**：`get_links=True` 时遍历 `enemy['info']['linkEnemies']` 递归取关联敌人，
   内层传 `get_links=False` 防无限递归（`enemy/main.py:70-74`）。
5. **查询流程**（`enemy/main.py:150-189`）：无名字时先尝试用 keypoint 直接查，再 `data.wait` 询问名称；
   命中 1 个直接渲染 `template/enemy.html`；命中多个则渲染 `template/enemyIndex.html` 让用户回复序号
   （`enemy/main.py:169-187`）。

## 依赖的 core 能力

- `core.Message`、`Chain`、`AmiyaBotPluginInstance`、`Requirement`（`enemy/main.py:4`）。
- `core.util`：`integer`、`any_match`、`find_most_similar`、`get_index_from_text`、`remove_punctuation`
  （`enemy/main.py:5`）。
- `core.resource.arknightsGameData.ArknightsGameData`（`enemy/main.py:6`）。

## 写入的表 / 目录 / 缓存

**无数据表、无落盘写入。** 本插件是纯只读消费者，只读 `ArknightsGameData.enemies`。

## 与其他插件耦合

- `Requirement('amiyabot-arknights-gamedata', official=True)`（`enemy/main.py:98`）。
- **不订阅 `gameDataInitialized`**，只在请求时按需读取 `ArknightsGameData.enemies`。数据未就绪时
  `find_enemies` 返回空列表，用户看到「没有找到敌方单位的资料」（`enemy/main.py:189`），属功能降级
  而非崩溃。

## 打包与发布

```bash
python run_build.py --type plugins
```

产物为 `amiyabot-arknights-enemy-3.7.zip`（`{plugin_id}-{version}.zip`）。

## 配置

| 配置项 | 默认值 | 读取处 | 含义 |
| --- | --- | --- | --- |
| `searchSetting.lengthLimit` | `5` | `enemy/main.py:103` | 消息词数上限，超出则不匹配 |
| `blockMishap` | `false` | `enemy/main.py:126` | 误触发抑制开关 |
