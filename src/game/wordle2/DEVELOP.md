# game/wordle2 插件开发说明

大帝的CYPHER挑战：用标签线索逐条揭示的干员猜词游戏，普通模式额外给一条提示干员。

## 使用指引

- [README.md](README.md) — 面向用户的功能说明，由 `pluginsDev/src/game/wordle2/main.py:15` 的 `document=` 参数加载。
- [README-public.md](README-public.md) — 公开机器人场景下的对应版本，由 `func` 插件按机器人是否为公开实例自动改选（`pluginsDev/src/func/main.py:207-213`）。

宿主的 `功能`/`帮助` 指令会把它渲染给用户看。本文件是开发者文档，不面向用户。

## 触发方式与指令

| 指令/关键词 | 匹配方式 | 说明 |
|------------|---------|------|
| `大帝挑战`、`大帝的挑战`、`大帝CYPHER挑战`、`大帝的CYPHER挑战` | `keywords=[4 个同义写法]` | 发起游戏（`pluginsDev/src/game/wordle2/main.py:20`） |
| 难度回复 | `data.wait_channel(Chain(data).text(main_text), force=True)` | 需回复「普通」或「硬核」（`pluginsDev/src/game/wordle2/main.py:32-40`） |

## 文件结构

| 文件/目录 | 作用 |
|-----------|------|
| `__init__.py` | 一行 `from .main import bot`，插件包入口 |
| `main.py` | `bot` 实例、难度选择、题库池循环 |
| `gameBuilder.py` | `OperatorPool` 题库池、`TagElement` 标签元素、`GuessProcess` 猜测状态 |
| `gameStart.py` | `game_begin` 单局流程、`guess_filter` 答题者限定、奖励发放 |
| `template/hardcode.html` + `hardcode.css` | 硬核模式页面模板 |
| `template/font.css`、`HarmonyOS_Sans_SC.ttf` | 字体 |
| `template/img/` | 标签背景图、图标 SVG（上/下箭头、点赞/踩、未知）、加载图等 |
| `template/js/vue.min.js` | 前端框架 |
| `README*.md` | 对用户展示的使用指引 |
| `logo.png` | 插件图标 |

本插件无配置文件。

## 核心实现

1. **难度选择**（`pluginsDev/src/game/wordle2/main.py:22-40`）：发送宣传文案后 `wait_channel`；`any_match(choice.text, ['普通','硬核'])` 判难度；未选择则 `event.close_event()` 并取消。`hardcode = (choice_level == '硬核')`（`pluginsDev/src/game/wordle2/main.py:44`）。
2. **题库池 `OperatorPool`**（`pluginsDev/src/game/wordle2/gameBuilder.py:9-23`）：`is_empty` 属性判断是否抽空；`pick_one()` 取一个干员。池空时提示「竟然把所有干员都猜完了...」并重建池，`asyncio.sleep(2)`（`pluginsDev/src/game/wordle2/main.py:47-52`）。
3. **主循环**（`pluginsDev/src/game/wordle2/main.py:46-71`）：
   - 每局发送「题目准备中...共有10次机会竞猜！」（`pluginsDev/src/game/wordle2/main.py:54`）。
   - 抽题后跳过含「预备干员」的干员（`pluginsDev/src/game/wordle2/main.py:58-59`）。
   - 普通模式下：若 `prev` 为空则先抽一个 `prev = pool.pick_one()`，并发送「{prev.name}为博士们提供了帮助！」作为提示干员；硬核模式不提供提示（`pluginsDev/src/game/wordle2/main.py:61-65`）。
   - 调用 `game_begin(data, event, operator, prev, hardcode)`，返回值 `(data, event)`；若 `data` 为假则 `break` 结束（`pluginsDev/src/game/wordle2/main.py:67-71`）。
   - 循环结束后 `event.close_event()`（`pluginsDev/src/game/wordle2/main.py:73-74`）。
4. **`GuessProcess` 状态**（`pluginsDev/src/game/wordle2/gameBuilder.py:36-130`）：
   - 构造时按 `hardcode` 选择 `__build_hardcode()` 或 `__build_normal()` 生成 `tags` 字典（`pluginsDev/src/game/wordle2/gameBuilder.py:48-58`）；普通模式在 `prev` 存在时会额外加入提示干员的标签（`pluginsDev/src/game/wordle2/gameBuilder.py:57`）。
   - `TagElement` 含 `show()` 方法（`pluginsDev/src/game/wordle2/gameBuilder.py:25-33`）。
   - `view_data()` 产出渲染数据，含 `hardcode` 标记（`pluginsDev/src/game/wordle2/gameBuilder.py:102-107`）。
   - `closed_tags` / `count` / `get_tips` / `guess(answer)` 分别用于已揭晓标签统计、标签总数、提示与判定（`pluginsDev/src/game/wordle2/gameBuilder.py:94-121`）。
5. **答题与奖励**（`pluginsDev/src/game/wordle2/gameStart.py`）：`game_begin`（`pluginsDev/src/game/wordle2/gameStart.py:25`）构造 `GuessProcess`（`pluginsDev/src/game/wordle2/gameStart.py:35`），硬核模式使用 `template/hardcode.html` 渲染（`pluginsDev/src/game/wordle2/gameStart.py:44`）；`guess_filter`（`pluginsDev/src/game/wordle2/gameStart.py:17`）限定答题者。时限 110 秒并分步提示（`pluginsDev/src/game/wordle2/gameStart.py:62-64` 在 `alert_step == 2` 时提示「还剩10秒...>.<」）。奖励分两种：
   - 答对：`rewards = 300 * (len(process.closed_tags) + 1)`，经 `UserInfo.add_jade_point(data.user_id, rewards, max_rewards)` 发放（`pluginsDev/src/game/wordle2/gameStart.py:110-112`）。
   - 解锁线索：`UserInfo.add_jade_point(data.user_id, unlock * 100, max_rewards)`（`pluginsDev/src/game/wordle2/gameStart.py:130-131`）。
   - 奖励上限常量 `max_rewards = 30000`（`pluginsDev/src/game/wordle2/gameStart.py:14`）。

## 依赖的 core 能力

`core.Message`、`Chain`、`AmiyaBotPluginInstance`、`Requirement`（`pluginsDev/src/game/wordle2/main.py:3`）；`core.util.any_match`（`pluginsDev/src/game/wordle2/main.py:4`）；`core.database.user.UserInfo`（`gameStart.py` 中用于发放合成玉）；`core.resource.ArknightsGameData`（经 `gameBuilder` 使用）。

## 写入的表/目录

不新建表。通过 `UserInfo.add_jade_point` 写入 core 的 `UserInfo`。无目录写入。

## 与其他插件耦合

- `Requirement('amiyabot-arknights-gamedata', official=True)`（`pluginsDev/src/game/wordle2/main.py:16`）。
- 与 `game/guess` 同样是频道级独占游戏，都通过 `wait_channel` 占用交互通道；两者共用 `UserInfo` 的合成玉账户。

## 打包与发布

| 项 | 值 |
|----|----|
| plugin_id | `amiyabot-game-wordle2` |
| version | `2.5` |
| 产物 | `amiyabot-game-wordle2-2.5.zip` |

元数据定义于 `pluginsDev/src/game/wordle2/main.py:9-17`。打包用 `python run_build.py --type plugins`，产出到 `plugins/`。
