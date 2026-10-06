# gacha 开发说明

抽卡模拟器，支持官方卡池切换、保底计数、box 统计与自定义卡池
（`pluginsDev/src/arknights/gacha/main.py:33-73`）。

## 使用指引

- 同目录 [README.md](README.md)：面向用户的使用指引，由 `document=f'{curr_dir}/README.md'` 加载
  （`gacha/main.py:69`），用户发送宿主 `功能` / `帮助` 指令时可见。**勿将其当作开发文档编辑。**
- 同目录 [README_USE.md](README_USE.md)：指令用法说明，由 `instruction=f'{curr_dir}/README_USE.md'` 加载
  （`gacha/main.py:70`）。
- `README_USE-public.md`：对外发布版本的用法说明，源码中未见引用。

## 插件注册信息

| 项 | 值 |
| --- | --- |
| 类 | `GachaPluginInstance`（`gacha/main.py:33`） |
| plugin_id | `amiyabot-arknights-gacha` |
| name / version | 明日方舟模拟抽卡 / `3.0` |
| plugin_type | `official` |
| priority | 未声明 |
| Requirement | **无** |
| 消息组 | `GroupConfig('gacha', allow_direct=True)`（`gacha/main.py:77`） |
| 配置 | `config/global_config_default.json` + `config/global_config_schema.json`（`gacha/main.py:71-72`） |

`install()`（`gacha/main.py:53-60`）：

1. `asyncio.create_task(self.sync_pool())` —— 异步发起且不等待。
2. 把自身实例存入模块级 `bot_caller['plugin_instance']`（`gacha/main.py:55`），供 `gachaBuilder` 在无
   `bot` 引用时读取配置。
3. 把 demo 卡池 `config/f175f6a942a746b6a0e00b151253955a.json` 复制到
   `resource/plugins/gacha/custom-pools/`（`gacha/main.py:57-60`）。

插件在**导入时**即创建 4 个目录（`gacha/main.py:22-30`）：`pool`、`custom-pools`、
`custom-pool-images`、`custom-pool-operators`。

## `sync_pool` 与宿主表约定

`sync_pool(force=False)`（`gacha/main.py:34-51`）：

1. 非强制模式下若 `Pool.get_or_none()` 已有数据则直接返回 `False`（`gacha/main.py:36-38`），即
   **仅在卡池表为空时自动同步**。
2. 请求 `remote_config.remote.plugin + '/api/v1/gacha'`（`gacha/main.py:40`），响应 JSON 的 `data`
   字段含 `OperatorConfig` 与 `Pool` 两个数组（`gacha/main.py:43`）。
3. **先 `OperatorConfig.delete().execute()` 与 `Pool.delete().execute()` 清表，再 `batch_insert` 全量
   覆盖**（`gacha/main.py:45-49`），成功返回 `True`。
4. 整个写库过程包在 `async with log.catch('pool sync error:')` 中（`gacha/main.py:42`）。

管理员可发送 `同步卡池` 强制触发（`gacha/main.py:354-364`）：经 `data.wait` 二次确认后调用
`sync_pool(force=True)`。

表结构定义在宿主 `core/database/bot.py`：`Pool`（`:169-258`）、`OperatorConfig`。`Pool` 的关键字段：
`pool_name`、`pool_uuid`、`pool_description`、`pool_image`、`limit_pool`（0 常规 / 1 限定 / 2 联合 /
3 前路回响 / 4 中坚 / 5 其他）、`is_classicOnly`、`is_official`，以及各稀有度的 `pickup_N` /
`pickup_N_rate` / `pickup_s_N`。

### 与宿主 `core/server/gacha.py` 的接口约定

宿主控制台通过**插件实例属性**调用本插件的 `sync_pool`（`core/server/gacha.py:62-71`）：

```python
sync_pool = getattr(bot.plugins['amiyabot-arknights-gacha'], 'sync_pool')
res = await sync_pool(force=True)
```

约定要点：

- 宿主以 `plugin_id` 为键在 `bot.plugins` 中查找插件实例，**未安装时返回 code=500「尚未安装此插件」**
  （`core/server/gacha.py:64-65`）。
- `sync_pool` 必须是**可直接 await 的可调用对象**，且接受关键字参数 `force=True`。本插件将其定义为
  `@staticmethod async def sync_pool(force: bool = False)`（`gacha/main.py:34-35`），符合该约定。
- **返回值为真值表示成功**：宿主据 `if res:` 决定返回「同步成功」还是 code=500「同步失败」
  （`core/server/gacha.py:69-71`）。本插件在写入成功时返回 `True`，非强制模式且已有数据时返回
  `False`，异常路径无返回值（返回 `None`），二者都会被宿主判为失败。
- 宿主另有 `/pool/getPool` 端点直接读 `Pool` 与 `OperatorConfig` 两张表（`core/server/gacha.py:73-79`），
  因此 `sync_pool` 写入的表结构必须与宿主控制台的 `PoolModel` 一致。

## 触发方式与指令

除 `同步卡池` 外，全部处理器均带 `group_id='gacha'`，并因消息组配置而 `allow_direct=True`。

| 指令 / 关键词 | 匹配方式 | level | 说明 |
| --- | --- | --- | --- |
| `抽`、`连`、`寻访` | `group_id='gacha'`，`keywords=[...]` | 3 | 抽卡主入口（`gacha/main.py:121`） |
| `保底` | `group_id='gacha'`，`keywords=['保底']` | 默认 | 查询距上次六星的抽数与下次概率（`gacha/main.py:176`） |
| `卡池`、`池子` | `group_id='gacha'`，`keywords=[...]` | 5 | 切换卡池（`gacha/main.py:276`） |
| `box` | `group_id='gacha'`，`keywords=['box']` | 默认 | 个人 box 统计图（`gacha/main.py:287`） |
| `获取当前抽卡概率` | `group_id='gacha'`，`keywords=[...]` | 默认 | 输出各星级综合出率，调试用（`gacha/main.py:298`） |
| `同步卡池` | `keywords=Equal('同步卡池')` | 默认 | 管理员强制同步，**不带 `group_id`**（`gacha/main.py:354`） |

抽卡指令的正则表（`gacha/main.py:75`）：`抽卡\d+次`、`寻访\d+次`、`抽\d+次`、`\d+次寻访`、
`\d+连寻访`、`\d+连抽`、`\d+连`、`\d+抽`；无数字时若含「单抽」则视为 1 次（`gacha/main.py:136-143`）。

## 文件结构

| 文件 / 目录 | 作用 |
| --- | --- |
| `main.py` | 插件实例、`sync_pool`、6 个处理器、`re_list` 正则表、`change_pool`（364 行） |
| `gachaBuilder.py` | `PoolSpOperator` 表、`GachaBuilder` 全部抽卡算法与输出模式（592 行） |
| `box.py` | `get_user_box`（`:10`）与 `get_user_gacha_detail`（`:66`），读 `OperatorBox` 出图 |
| `utils/pool_methods.py` | 卡池工具函数集（240 行，见下） |
| `utils/get_operators.py` | `get_operators(classic_only)` 与 `get_operator_by_names(names)` |
| `utils/create_gacha_image.py` | 抽卡结果图合成 |
| `utils/logger.py` | `debug_log` 开关（7 行） |
| `config/` | `f175f6a942a746b6a0e00b151253955a.json`（demo 自定义卡池）、`global_config_default.json`、`global_config_schema.json` |
| `gacha/` | 结果图素材 `1.png`–`6.png`（星级）、`bg.png` |
| `classify/`、`rank/` | 职业图标 8 个、稀有度图标 6 个 |
| `README.md` / `README_USE.md` / `README_USE-public.md` | 用户可见文档，见上 |
| `__init__.py` | `from .main import bot` |

## 核心实现

### 抽卡算法（`gachaBuilder.py`）

1. **卡池装载**（`gachaBuilder.py:34-48`）：取 `UserGachaInfo`，按 `use_custom_gacha_pool` 决定用
   `get_custom_pool` 还是 `get_official_pool`；官方池取不到时 `change_to_latest_pool(user_id)` 回退到
   最新池（`gachaBuilder.py:44-46`）。
2. **填充干员池**（`gachaBuilder.py:50-65`）：`get_operators(classic_only)` 取全部可选干员并按稀有度
   分桶。`get_operators`（`gacha/utils/get_operators.py:5-24`）的过滤逻辑：`classic_only` 时只保留
   `is_classic`；否则排除 `limit`、`unavailable` 以及「`is_classic` 且稀有度 ≥ 5」的干员。
3. **基础概率区间**（`gachaBuilder.py:110`）：`rarity_range = {6: 2, 5: 8, 4: 50, 3: 40, 2: 0, 1: 0}`，
   注释说明 3 星 40%（区间 1~40）、4 星 50%（41~90）、5 星 8%（91~98）、6 星 2%（99~100）。
4. **权重解析 `__get_weight`**（`gachaBuilder.py:267-286`）：按逗号切分卡池配置字符串，`名字|权重`
   格式解析权重，缺省为 1，同名累加。
5. **UP 概率 `__get_pickup_rate`**（`gachaBuilder.py:119-170`）：按 `limit_pool` 类型给默认值 —— 6 星在
   `pickup_6_rate` 为空时，官方池按 `limit_pool` 0/1/2/3/4/5 分别返回 0.5/0.7/1/1/1/1，非官方池默认
   0.7（`gachaBuilder.py:128-148`）；5 星在 `limit_pool == 2` 时为 1，否则空值默认 0.5；4 星及以下
   空值默认 0。
6. **权重归一化 `__get_gacha`**（`gachaBuilder.py:183-264`）：核心算法，把 pickup 权重与
   special/fillin 权重合并归一化。
   - 权重放大 10000 倍规避浮点精度问题（`gachaBuilder.py:203`）。
   - `up_rate` 截断到 `[0, 1]`（`gachaBuilder.py:196-200`）。
   - pickup 部分：负权重按 0 处理后归一化，乘以 `up_rate * 10000`（`gachaBuilder.py:213-229`）。
   - fillin 部分：把 fillin 干员权重并入 special（每个 +1，`gachaBuilder.py:236-240`），再按
     `(1 - up_rate) * scale_up_factor` 归一化（`gachaBuilder.py:258`）。
   - 关键规则：**干员一旦已在 pickup 中，fillin 概率完全失效**（`gachaBuilder.py:249`、`:261`）。
   - 负权重用于「减少权重」：例如 `pickup_s` 标 `能天使|-1` 可与 fillin 的 `能天使|1` 抵消为 0
     （`gachaBuilder.py:205-208`）。
7. **保底 `check_break_even`**（`gachaBuilder.py:442`）：与 `gacha/main.py:180-182` 的显示逻辑对应 ——
   基础 `break_even_rate = 98`，`gacha_break_even > 50` 后每多 1 次减 2，即 51 次时概率 4%，逐次
   递增到 100%。
8. **执行抽卡**（`gachaBuilder.py:478` 起）：`start_gacha(times, coupon, point)` →
   `choose_operator(rarity)` 按权重随机 → `__get_operator(name)`；`set_box(result)` 写入用户 box
   （`gachaBuilder.py:573`）。
9. **两种输出模式**：`continuous_mode`（`gachaBuilder.py:287`，> 10 连，汇总各星级与高星结果）与
   `detailed_mode`（`gachaBuilder.py:364`，≤ 10 连，逐张渲染）。调用分流见 `gacha/main.py:164-167`。

### `pickup_N` / `pickup_s` / rate 字段语义

`Pool` 表中每个稀有度有一组三个字段（`core/database/bot.py:208-218` 的注释为权威说明）：

| 字段 | 语义 |
| --- | --- |
| `pickup_N` | 该星级 UP 干员列表，逗号分隔，每项可写 `干员名\|权重`，权重可为负 |
| `pickup_s_N` | 该星级 special 干员列表，写法同上。「五倍权重提升的任意干员，或者 1 倍权重但会在本池抽出的限定干员」；其他 fillin 干员权重为 1 |
| `pickup_N_rate` | N 星 UP 干员占该星级出率的比例，为小数；`> 1` 会被当 1 处理，`None` 视为 0（实际由 `__get_pickup_rate` 兜底给默认值） |

注释原文另注明：设置为 100 即联合寻访（只有 UP 干员）；所有 UP 干员加权平分 `rate` 给出的概率，剩余
由常规干员填充。

### 卡池管理与工具函数

- **卡池切换 `change_pool`**（`gacha/main.py:88-118`）：官方池更新 `UserGachaInfo.gacha_pool` 与
  `use_custom_gacha_pool=False`；趣味池更新 `custom_gacha_pool` 与 `use_custom_gacha_pool=True`。
  卡池名带「【限定】」前缀（`limit_pool != 0` 时）或「【趣味】」前缀。卡池图片来自 `get_pool_image`。
- **卡池列表与选择**（`gacha/main.py:189-251`）：`switch_to_official_pool` 只保留官方池（`is_official`
  为 None 或 True），支持按名字、按序号、或交互式回复序号切换；QQ 频道下管理员可用「所有人」切换
  全部用户（`gacha/main.py:212-216`）。趣味卡池切换 `switch_to_custom_pool`（`gacha/main.py:254-273`）
  要求卡池编号以 `Custom-` 开头，**当前入口被 `and False` 条件屏蔽**（`gacha/main.py:281`）。
- **各池工具函数**（`gacha/utils/pool_methods.py`）：`get_pool_name`（`:28`）、`get_pool_id`（`:35`）、
  `get_pool_selector`（`:45`）、`get_pool_image`（`:56`）、`copy_props`（`:84`）、
  `get_official_pool`（`:111`）、`save_image_from_base64`（`:119`）、`get_custom_pool`（`:153`）、
  `change_to_latest_pool`（`:232`）。
- **资源与消耗校验**（`gacha/main.py:129-167`）：取 `UserGachaInfo.coupon` 为寻访凭证数；
  `times > 300` 时拒绝（`gacha/main.py:151`）；凭证不足时按 `(times - coupon) * 600` 计算合成玉消耗，
  不足则提示（`gacha/main.py:151-162`）。

### 自定义卡池

- 目录 `resource/plugins/gacha/custom-pools/`：每池一个 JSON 文件，文件名即 `pool_selector`。
  `get_custom_pool`（`utils/pool_methods.py:153`）读取后按 `copy_props`（`:84`）逐属性装配到 `Pool`
  实例；`pool_image_raw` 为 base64 时经 `save_image_from_base64`（`:119`）落盘到 `custom-pool-images/`。
- 目录 `resource/plugins/gacha/custom-pool-operators/`：自定义干员数据。
- demo 卡池随插件分发于 `config/f175f6a942a746b6a0e00b151253955a.json`，`install()` 时复制到
  `custom-pools/`（`gacha/main.py:57-60`）。

## 依赖的 core 能力

- `core.log`、`Message`、`Chain`、`Equal`、`AmiyaBotPluginInstance`（`gacha/main.py:10`）。
- `core.util`：`any_match`、`create_dir`（`gacha/main.py:11`）、`insert_empty`（`gachaBuilder.py:7`）。
- `core.resource.remote_config`（`gacha/main.py:12`）。
- `core.database.user`：`UserInfo`、`UserGachaInfo`（`gacha/main.py:13`）、`OperatorBox`
  （`gachaBuilder.py:5`、`box.py:3`）。
- `core.database.bot`：`OperatorConfig`、`Admin`、`Pool`、`BotBaseModel`（`gacha/main.py:14`、
  `gachaBuilder.py:6`）。
- `core.resource.arknightsGameData.ArknightsGameData`（`gachaBuilder.py:8`）。
- `amiyabot`：`QQGuildBotInstance`、`GroupConfig`（`gacha/main.py:8`）、`http_requests`
  （`gacha/main.py:9`）。

## 写入的表 / 目录 / 缓存

| 类型 | 名称 | 说明 |
| --- | --- | --- |
| 表 | `Pool` | 卡池定义，`sync_pool` 中先 delete 再 batch_insert |
| 表 | `OperatorConfig` | 干员配置，同上全量覆盖 |
| 表 | `PoolSpOperator` | 卡池特殊干员，外键关联 `Pool` 并 `on_delete='CASCADE'`（`gachaBuilder.py:24-30`） |
| 表 | `UserGachaInfo` | `gacha_pool`、`custom_gacha_pool`、`use_custom_gacha_pool`、`gacha_break_even`、`coupon` |
| 表 | `OperatorBox` | 用户抽卡结果（`set_box`） |
| 表 | `UserInfo` | 消耗 `jade_point` |
| 目录 | `resource/plugins/gacha/{pool,custom-pools,custom-pool-images,custom-pool-operators}` | 导入时 `create_dir`（`gacha/main.py:22-30`） |

## 与其他插件耦合

- **未声明 `Requirement` 也未订阅 `gameDataInitialized`，但消费 `ArknightsGameData`**
  （`gachaBuilder.py:8`、`gachaBuilder.py:51`、`gacha/utils/get_operators.py:1`、`gacha/box.py:4`），
  是启动期最脆弱的一环：数据未就绪时 `GachaBuilder.__init__` 抛异常，被 `gacha/main.py:123-127`
  捕获并回「无法初始化卡池」。
- `sync_pool` 是网络请求且不等待完成（`gacha/main.py:54`），同步完成前抽卡会因取不到卡池而失败。
- 与 `user` 插件共享 `UserGachaInfo.coupon`：签到发放的寻访凭证即在此消费。
- 与 `game/guess`、`game/wordle2` 共享合成玉账户（`UserInfo.jade_point`）。

## 打包与发布

```bash
python run_build.py --type plugins
```

产物为 `amiyabot-arknights-gacha-3.0.zip`（`{plugin_id}-{version}.zip`）。
