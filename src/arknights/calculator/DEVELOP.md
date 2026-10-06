# calculator 开发说明

计算从今天到指定日期可获得的合成玉数量（`pluginsDev/src/arknights/calculator/main.py:11-18`）。
用框架 `PluginInstance`，无配置、无表。

## 使用指引

- 同目录 [README.md](README.md)：面向用户的使用指引，由 `document=f'{curr_dir}/README.md'` 加载
  （`calculator/main.py:17`），用户发送宿主 `功能` / `帮助` 指令时可见。**勿将其当作开发文档编辑。**
- `README-public.md`：对外发布版本的说明，源码中未见引用。

## 插件注册信息

| 项 | 值 |
| --- | --- |
| 类 | `PluginInstance`（`calculator/main.py:11`）——**非** `AmiyaBotPluginInstance` |
| plugin_id | `amiyabot-arknights-calculator` |
| name / version | 明日方舟计算器 / `1.5` |
| plugin_type | `official` |
| priority | 未声明 |
| Requirement | 无 |
| 消息组 | 无 |

使用框架原生 `PluginInstance`，因此**没有** `instruction` / `requirements` / `priority`，也没有
`install()` / `uninstall()` 钩子，不读写任何插件配置。

## 触发方式与指令

| 指令 / 关键词 | 匹配方式 | level | 说明 |
| --- | --- | --- | --- |
| `/计算合成玉` | `keywords=['/计算合成玉']` | 99 | 显式指令，可带日期参数；无参数时追问（`calculator/main.py:21-31`） |
| `多少玉` / `多少合成玉` | `keywords=re.compile(r'多少(合成)?玉')`，`allow_direct=True` | 3 | 自然语言入口（`calculator/main.py:34-38`） |

`level=99` 表示最低优先级，避免抢占其他插件的「玉」相关指令。

## 文件结构

| 文件 | 作用 |
| --- | --- |
| `main.py` | 两个处理器与 `bot` 定义（38 行） |
| `jade.py` | 全部计算逻辑：周期判定、逐日累加、日期换算（119 行） |
| `logo.png` | 插件图标 |
| `README.md` / `README-public.md` | 用户可见文档，见上 |
| `__init__.py` | `from .main import bot` |

## 核心实现

1. **入口分派**（`calculator/main.py:22-38`）：`action` 剥离指令词后若有内容直接计算，否则
   `data.wait` 追问截止日期；自然语言入口直接把原文交给 `calc_jade`。
2. **时间解析**（`jade.py:35-61`）：调用 `core.util.extract_time(text)` 解析用户输入的日期文本，取
   最后一个结果；超前当前年份 100 年以上或目标时间已过期时返回对应提示。
3. **限时卡池周期**（`jade.py:12-32`）：`get_extra_card_period(year)` 返回「5 月 1 日前最后一个周六」
   起算的 30 天窗口；`is_in_extra_card_period(timestamp)` 对前后一年各检查一次，判断某时间戳是否落在
   周期内。
4. **结果计算**（`jade.py:64-96` 的 `calc_result(end_date)`）：逐日累加各类来源 —— 月卡签到 200、
   每日任务 100、每周任务 500（周一）、剿灭行动 1800（周一），落在额外月卡周期内再加 200；最后汇总
   并输出分项明细。
5. **日期换算**（`jade.py:99-119`）：`calc_date` 从当天零点起按 86400 秒逐日推进到目标日期；
   `date_to_stamp`、`stamp_to_date` 为字符串与时间戳互转。
6. **异常兜底**（`jade.py:58-61`）：`ValueError` 与 `OverflowError` 分别返回友好提示。

## 依赖的 core 能力

- `core.Message`、`Chain`（`calculator/main.py:6`）。
- `core.util.extract_time`（`jade.py:4`）。
- `amiyabot.PluginInstance`（`calculator/main.py:4`）。

不依赖 `ArknightsGameData`。

## 写入的表 / 目录 / 缓存

**无数据表、无目录写入、无缓存。** 纯函数式日期推算。

## 与其他插件耦合

**无耦合。** 不依赖 `ArknightsGameData`，不声明 `Requirement`，不订阅任何 `event_bus` 事件。
概念上与其他插件共享「合成玉」这一货币（如 gacha 插件消费 `UserInfo.jade_point`），但无代码级调用。

## 打包与发布

```bash
python run_build.py --type plugins
```

产物为 `amiyabot-arknights-calculator-1.5.zip`（`{plugin_id}-{version}.zip`）。
