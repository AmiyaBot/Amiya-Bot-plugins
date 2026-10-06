# recruit 开发说明

文本或截图输入公招标签，求解可锁定稀有干员的标签组合，支持多路 OCR
（`pluginsDev/src/arknights/recruit/main.py:146-165`）。

## 使用指引

- 同目录 [README.md](README.md)：面向用户的使用指引，由 `document=f'{curr_dir}/README.md'` 加载
  （`recruit/main.py:160`），用户发送宿主 `功能` / `帮助` 指令时可见。**勿将其当作开发文档编辑。**
- 同目录 [README_USE.md](README_USE.md)：指令用法说明，由 `instruction=f'{curr_dir}/README_USE.md'`
  加载（`recruit/main.py:161`）。
- `README_USE-public.md`：对外发布版本的用法说明，源码中未见引用。

## 插件注册信息

| 项 | 值 |
| --- | --- |
| 类 | `RecruitPluginInstance`（`recruit/main.py:146`） |
| plugin_id | `amiyabot-arknights-recruit` |
| name / version | 明日方舟公招查询 / `3.1` |
| plugin_type | `official` |
| priority | 未声明 |
| Requirement | `Requirement('amiyabot-arknights-gamedata', official=True)`（`recruit/main.py:164`） |
| 消息组 | 无（用 `allow_direct=True` 单点声明） |

- `install()`（`recruit/main.py:147-148`）起异步任务 `Recruit.init_tags_list()`。
- `uninstall()`（`recruit/main.py:150-151`）解除 `gameDataInitialized` 订阅。

**模块导入时**执行两件事：复制 `baiduCloud.yaml` 到 `resource/plugins/`（`recruit/main.py:33-35`），
复制 `tools/Windows.Media.Ocr.Cli.exe` 到 `resource/plugins/`（`recruit/main.py:37-39`）。两处均有
`os.path.exists` 守卫，幂等。

## 触发方式与指令

| 指令 / 关键词 | 匹配方式 | level | 说明 |
| --- | --- | --- | --- |
| `公招`、`公开招募` | `keywords=['公招','公开招募']`，`allow_direct=True` | 10 | 文本或截图入口（`recruit/main.py:288`） |
| 自动识图 | `verify=auto_discern`，`check_prefix=False`，`allow_direct=True` | 默认 | 直接发公招截图即触发（`recruit/main.py:316`） |

## OCR 四条路径

`get_ocr_result`（`recruit/main.py:239-285`）按优先级依次尝试，任一成功即返回：

1. **百度 OCR**（`recruit/main.py:243-249`）：若 `baidu.enable`，先 `basic_accurate`，失败再
   `basic_general`，拼接 `words_result` 的 `words`。
2. **go-cqhttp OCR**（`recruit/main.py:252-258`）：结果为空且实例是 `CQHttpBotInstance` 时，调
   `/ocr_image` 接口，从消息段取图片 `file`，拼接 `texts`。
3. **PaddleOCR**（`recruit/main.py:261-267`）：`paddle_enabled` 时经 `run_in_thread_pool` 调用本地
   `paddle_ocr.ocr`，取 `text[1][0]`。
4. **Windows 本地 OCR**（`recruit/main.py:270-283`）：`localOCR_enabled`（`platform.release() == '10'`，
   `recruit/main.py:45`）时把图片存成临时 PNG，用 `os.popen` 调用 `Windows.Media.Ocr.Cli.exe`。

PaddleOCR 在模块导入时尝试初始化，`ModuleNotFoundError` 时 `paddle_enabled = False`
（`recruit/main.py:47-55`），属可选依赖降级。

百度配置来源：`get_baidu()`（`recruit/main.py:178-190`）优先用全局配置的 `enable` / `appid` /
`apiKey` / `secretKey`，否则读 `resource/plugins/baiduCloud.yaml`。

### 图片自动识别（dhash 模板匹配）

`auto_discern`（`recruit/main.py:223-236`）：对消息中每张图片下载后用 `dhash.dhash_int` 算感知哈希，
与 `recruit.yaml` 中的 `templateHash` 比较，`dhash.get_num_bits_different` 差值 ≤ `maxDifferent`
即判定为公招界面截图，并把 `data.image` 收敛为该图。

## 标签组合算法

1. **词典构建 `init_tags_list`**（`recruit/main.py:61-76`）：基础标签为 `['资深', '高资', '高级资深']`，
   再遍历 `ArknightsGameData.operators` 收集所有 `item.tags` 去重；写成 `{tag} 500 n` 格式的
   `tags.txt` 并 `jieba.load_userdict`。
2. **分词取标签**（`recruit/main.py:87-101`）：用 `jieba.posseg.lcut` 对去掉「公招」的文本分词，命中
   词典的词收为标签。特殊归一化：「资深/资深干员」统一为 `资深干员`；「高资/高级资深/高级资深干员」
   统一为 `高级资深干员` 并把 `max_rarity` 提到 6。
3. **候选干员筛选 `find_operator_tags_by_tags`**（`recruit/main.py:193-209`）：遍历
   `ArknightsGameData.operators`，跳过 `not item.is_recruit` 与 `rarity > max_rarity` 的干员，收集其
   命中的标签，按稀有度倒序。
4. **组合枚举 `find_combinations`**（`recruit/main.py:212-220`）：用 `combinations` 枚举长度 1~3 的
   全部组合，剔除同时含「高级资深干员」与「资深干员」的互斥组合，随后 `reverse`。
5. **组合判定与排序**（`recruit/main.py:114-138`）：对每个组合用
   `all_match(item['operator_tags'], comb)` 判断干员是否满足全部标签；6 星干员要求组合含「高级资深
   干员」；只保留稀有度 ≥ 4 或 == 1 的干员并记录最高稀有度。最终 `groups` 按
   `(-len(tags), -max_rarity)` 排序，即**标签数多的组合优先，其次稀有度高的优先**
   （`recruit/main.py:135`）。
6. **结果输出**（`recruit/main.py:134-143`）：有组合则渲染 `template/operatorRecruit.html`；无组合回
   「没有找到可以锁定稀有干员的组合」；干员查询失败回「无法查询到标签所拥有的稀有干员」。

## 文件结构

| 文件 / 目录 | 作用 |
| --- | --- |
| `main.py` | 全部实现：`Recruit` 工具类、OCR 四路、`auto_discern`、标签算法、两个处理器（318 行） |
| `tools/Windows.Media.Ocr.Cli.exe` | 本地 OCR 可执行文件，导入时复制到 `resource/plugins/` |
| `recruit.yaml` | dhash 模板配置：`autoDiscern.templateHash`、`autoDiscern.maxDifferent` |
| `baiduCloud.yaml` | 百度 OCR 凭据模板，导入时复制到 `resource/plugins/` |
| `config_default.yaml` / `config_schema.json` | 插件全局配置模板（`enable` / `appId` / `apiKey` / `secretKey`） |
| `template/operatorRecruit.html` + `operatorRecruit.css` | 公招组合结果模板 |
| `template/img/pc_bg.jpeg`、`font.css`、`HarmonyOS_Sans_SC.ttf`、`js/vue.min.js` | 模板资源 |
| `logo.png` | 插件图标 |
| `README.md` / `README_USE.md` / `README_USE-public.md` | 用户可见文档，见上 |
| `__init__.py` | `from .main import bot` |

## 核心实现

- **交互入口**（`recruit/main.py:288-318`）：带图片直接 OCR；否则先走文本解析，解析不出再视条件询问
  截图。若既无百度 OCR、实例又不是 CQHttp、且本地 OCR 不可用则直接返回 `None`（`recruit/main.py:302-303`）；
  未收到图时区分 QQ 群聊给出 @ 提示（`recruit/main.py:310-313`）。

## 依赖的 core 能力

- `core.log`、`Message`、`Chain`、`AmiyaBotPluginInstance`、`Requirement`（`recruit/main.py:24`）。
- `core.util`：`all_match`、`read_yaml`、`create_dir`、`run_in_thread_pool`（`recruit/main.py:25`）。
- `core.lib.baiduCloud.BaiduCloud`（`recruit/main.py:26`）。
- `core.resource.arknightsGameData.ArknightsGameData`（`recruit/main.py:27`）。
- `amiyabot`：`event_bus`、`download_async`、`CQHttpBotInstance`、`QQGroupBotInstance`
  （`recruit/main.py:19-22`）。
- 第三方：`dhash`、`jieba`、`PIL`，以及可选依赖 `paddleocr`。

## 写入的表 / 目录 / 缓存

无独立数据表。

| 类型 | 路径 | 说明 |
| --- | --- | --- |
| 文件 | `pluginsDev/src/arknights/recruit/tags.txt` | jieba 用户词典，每次 `init_tags_list` 覆盖写 |
| 文件 | `resource/plugins/baiduCloud.yaml` | 导入时复制（`recruit/main.py:33-35`） |
| 文件 | `resource/plugins/Windows.Media.Ocr.Cli.exe` | 导入时复制（`recruit/main.py:37-39`） |
| 临时文件 | `{curr_dir}/{random}.png` | 本地 OCR 用，用后即删（`recruit/main.py:272`、`recruit/main.py:281`） |

## 与其他插件耦合

- `Requirement('amiyabot-arknights-gamedata', official=True)`（`recruit/main.py:164`）。
- 订阅 `gameDataInitialized` 并**整体重装自己**（`recruit/main.py:168-175`），因为需要重新生成
  `tags.txt` 词典；回调中先用 `asyncio.get_running_loop()` 守卫。
- 依赖 `ArknightsGameData.operators` 的 `tags`、`is_recruit`、`rarity` 字段。
- 与 `user`、`replace` 插件共用同一份 `resource/plugins/baiduCloud.yaml` 配置。

## 打包与发布

```bash
python run_build.py --type plugins
```

产物为 `amiyabot-arknights-recruit-3.1.zip`（`{plugin_id}-{version}.zip`）。

## 配置

| 配置项 | 来源 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `enable` | `config_default.yaml` | `false` | 是否启用百度 OCR |
| `appId` / `apiKey` / `secretKey` | `config_default.yaml` | 空 | 百度 OCR 凭据，为空时回退读 `baiduCloud.yaml` |
| `autoDiscern.templateHash` | `recruit.yaml` | 见文件 | 公招界面截图的 dhash 基准值 |
| `autoDiscern.maxDifferent` | `recruit.yaml` | `25` | 汉明距离阈值 |
