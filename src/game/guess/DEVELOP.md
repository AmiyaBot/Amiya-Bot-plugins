# game/guess 插件开发说明

兔兔猜干员：多人参与的干员竞猜游戏，按难度给出不同线索类型，结算合成玉奖励。

## 使用指引

- [README.md](README.md) — 面向用户的功能说明，由 `pluginsDev/src/game/guess/main.py:13` 的 `document=` 参数加载。
- [README-public.md](README-public.md) — 公开机器人场景下的对应版本，由 `func` 插件按机器人是否为公开实例自动改选（`pluginsDev/src/func/main.py:207-213`）。

宿主的 `功能`/`帮助` 指令会把它渲染给用户看。本文件是开发者文档，不面向用户。

## 触发方式与指令

| 指令/关键词 | 匹配方式 | 说明 |
|------------|---------|------|
| `猜干员` | `keywords=['猜干员']` | 发起游戏，先选难度（`pluginsDev/src/game/guess/main.py:28-29`） |
| 难度回复 | `data.wait_channel(choice_chain, force=True, data_filter=level_filter)` | 需回复「初级/中级/高级/资深」之一 |

难度与线索类型的映射（`pluginsDev/src/game/guess/main.py:30-35`）：

| 难度 | 线索内容 | 结算倍率 |
|------|---------|---------|
| 初级 | 立绘 | 1 |
| 中级 | 技能 | 2 |
| 高级 | 语音 | 3 |
| 资深 | 档案 | 4 |

倍率由 `list(level.keys()).index(choice_level) + 1` 得出（`pluginsDev/src/game/guess/main.py:80`）。

## 文件结构

| 文件 | 作用 |
|------|------|
| `__init__.py` | 一行 `from .main import bot`，插件包入口 |
| `main.py` | `bot` 实例、难度选择、主循环与结算 |
| `guessStart.py` | 单题状态机 `guess_start`、`guess_filter`、按钮能力判断 `can_send_buttons` |
| `guessBuilder.py` | `GameState` 状态常量、`RateCalculator`、`GuessUser`、`GuessResult`、`GuessReferee` |
| `guessTools.py` | `ImageCropper`：按透明度裁剪干员立绘 |
| `guess.yaml` | 静态题库/文案配置 |
| `config_default.yaml` | 全局配置默认值（题量、奖励、`markdown_template_id` 等） |
| `config_schema.json` | 全局配置 JSON Schema |
| `bot.png` | 游戏配图 |
| `README*.md` | 对用户展示的使用指引 |
| `logo.png` | 插件图标 |

## 核心实现

1. **难度选择**（`pluginsDev/src/game/guess/main.py:37-75`）：构造难度文本；若 `can_send_buttons(data, markdown_template_id)` 为真，则改用 `InlineKeyboard` 发送 4 个按钮（`action_data` 为难度名，`action_enter=True`），并走 `markdown_template` 通道（`pluginsDev/src/game/guess/main.py:42-59`）。`markdown_template_id` 由 `get_markdown_template_id` 按 `data.instance.appid` 在配置中查找（`pluginsDev/src/game/guess/main.py:20-25`）。
   - `level_filter` 限定「只接受发起游戏的同一 user_id 的消息」（`pluginsDev/src/game/guess/main.py:60-66`），避免被群内其他人的消息打断。
2. **主循环**（`pluginsDev/src/game/guess/main.py:87-139`）：
   - `operators = copy.deepcopy(ArknightsGameData.operators)` 做题库快照，`operators.pop(random.choice(...))` 随机抽题（`pluginsDev/src/game/guess/main.py:88-91`）。
   - 过滤含「预备干员」与「盟约」字样的干员（`pluginsDev/src/game/guess/main.py:93-96`）。
   - 每进入新回合（`referee.round` 变化）发送「题目准备中...（n/N）」，并在已有排名时附带 `referee.calc_rank()`（`pluginsDev/src/game/guess/main.py:98-105`）。
   - 调用 `guess_start(referee, target, event, operator, 线索类型, 难度名, 倍率)` 进入答题（`pluginsDev/src/game/guess/main.py:107-115`）。
3. **状态机**：`GameState` 定义 5 态（`pluginsDev/src/game/guess/guessBuilder.py:10-15`）：

   | 常量 | 值 | 含义 |
   |------|----|------|
   | `systemSkip` | 0 | 系统跳过（默认态） |
   | `userSkip` | 1 | 用户跳过 |
   | `bingo` | 2 | 猜中 |
   | `userClose` | 3 | 用户关闭 |
   | `systemClose` | 4 | 系统关闭 |

   主循环据此判定（`pluginsDev/src/game/guess/main.py:121-127`）：`userClose`/`systemClose` → `end=True`；`userSkip`/`systemSkip` → `skip=True`（跳过不计回合）；`bingo` → 用 `UserInfo.add_jade_point(user_id, rewards, game_config.jade_point_max)` 即时发奖并 `referee.set_rank(...)` 记排名。
4. **数据结构**（`pluginsDev/src/game/guess/guessBuilder.py`）：`RateCalculator` 维护 `user_rate` 与 `total_rate`（`pluginsDev/src/game/guess/guessBuilder.py:18-28`）；`GuessUser` 含 `user_id/nickname/index/point/max_combo`（`pluginsDev/src/game/guess/guessBuilder.py:31-40`）；`GuessResult` 含 `answer/state/point/rewards/event`（`pluginsDev/src/game/guess/guessBuilder.py:43-54`）；`GuessReferee` 含 `round/combo_user/combo_count/user_num/user_index/user_ranking` 与 `markdown_template_id`（`pluginsDev/src/game/guess/guessBuilder.py:57-68`）。
5. **答题流程**（`pluginsDev/src/game/guess/guessStart.py`）：`guess_start`（`pluginsDev/src/game/guess/guessStart.py:38`）为单题状态机，`guess_filter`（`pluginsDev/src/game/guess/guessStart.py:30`）限定答题者。状态赋值点：`systemClose`（`pluginsDev/src/game/guess/guessStart.py:199`）、`userSkip`（`pluginsDev/src/game/guess/guessStart.py:215`）、`userClose`（`pluginsDev/src/game/guess/guessStart.py:290`）、`bingo`（`pluginsDev/src/game/guess/guessStart.py:330`）。猜中时按 `guess_config.rewards.bingo * level_rate * (100 + result.total_rate) / 100` 计算奖励（`pluginsDev/src/game/guess/guessStart.py:296`）。
6. **结算**（`pluginsDev/src/game/guess/main.py:141-176`）：
   - 回合数 `< guess_config.finish_min` 时不结算，直接返回（`pluginsDev/src/game/guess/main.py:144-147`）。
   - `finish_rate = round(round / questions, 2)`；`rewards_rate = (100 + max(total_rate, -50)) / 100`（下限保护 -50）（`pluginsDev/src/game/guess/main.py:149-150`）。
   - 名次奖励系数取自 `guess_config.rewards.golden/silver/copper`，最终 `rewards = int(bonus * level_rate * finish_rate * rewards_rate)`（`pluginsDev/src/game/guess/main.py:157-168`）。
   - 逐个 `UserInfo.add_jade_point(uid, rewards, game_config.jade_point_max)` 发放（`pluginsDev/src/game/guess/main.py:171-172`）。
7. **配置来源**：`guess_config` 与 `game_config` 由 `guessStart` 导入（`pluginsDev/src/game/guess/main.py:5` 的 `from .guessStart import *`）；`guess.yaml` 为静态题库/配置。
8. **`ImageCropper`**（`pluginsDev/src/game/guess/guessTools.py:7-81`）：按透明度裁剪干员立绘，`max_transparent_ratio=30.0`，提供 `crop_positions` / `transparent_ratio` / `expand` / `crop`。

## 依赖的 core 能力

`core.AmiyaBotPluginInstance`、`core.Requirement`（`pluginsDev/src/game/guess/main.py:1`）；`core.util.TimeRecorder`（`pluginsDev/src/game/guess/main.py:2`）；`core.database.user.UserInfo`（`pluginsDev/src/game/guess/main.py:3`）；`core.resource.ArknightsGameData`（经 `guessStart` 使用）；`amiyabot.builtin.message.ChannelMessagesItem`（`pluginsDev/src/game/guess/guessBuilder.py:6`）。

## 写入的表/目录

不新建表。通过 `UserInfo.add_jade_point` 写入 core 的 `UserInfo`（合成玉与上限）。无目录写入。

## 与其他插件耦合

- `Requirement('amiyabot-arknights-gamedata', official=True)`（`pluginsDev/src/game/guess/main.py:16`），强依赖干员数据。
- 与 `user` 插件共享 `UserInfo`（合成玉账户）与配置键 `jade_point_max`（`pluginsDev/src/game/guess/main.py:126,172`）。
- 与 `arknights/gacha` 间接耦合：猜干员发放的合成玉可在抽卡中使用。
- 与 `game/wordle2` 同为频道级独占游戏，都通过 `wait_channel` 占用交互通道。

## 打包与发布

| 项 | 值 |
|----|----|
| plugin_id | `amiyabot-game-guess` |
| version | `3.5` |
| 产物 | `amiyabot-game-guess-3.5.zip` |

元数据定义于 `pluginsDev/src/game/guess/main.py:7-17`。打包用 `python run_build.py --type plugins`，产出到 `plugins/`。
