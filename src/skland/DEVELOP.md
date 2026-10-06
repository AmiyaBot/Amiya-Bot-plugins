# skland 插件开发说明

森空岛集成：通过森空岛（鹰角官方社区）API 查询玩家游戏数据并渲染为图片。

## 使用指引

- [README.md](README.md) — 面向用户的功能说明，由 `pluginsDev/src/skland/main.py:136` 的 `document=` 参数加载。
- [README_USE.md](README_USE.md) — 详细使用指引，由 `pluginsDev/src/skland/main.py:137` 的 `instruction=` 参数加载。
- [README_TOKEN.md](README_TOKEN.md) — Token 获取专项说明，同上被加载为使用文档。
- [README_USE-public.md](README_USE-public.md) — 公开机器人场景下的对应版本。

宿主的 `功能`/`帮助` 指令会把上述文档渲染给用户看。本文件是开发者文档，不面向用户。

## 触发方式与指令

| 指令/关键词 | 匹配方式 | level | 说明 |
|------------|---------|-------|------|
| `我的游戏信息`、`森空岛` | `group_id='skland'`, `keywords=[...]` | 5 | 渲染账号总览 `template/userInfo.html`（`pluginsDev/src/skland/main.py:183`） |
| `我的仓库` | `group_id='skland'`, `keywords=['我的仓库']` | 5 | 渲染 `template/warehouse.html`（`pluginsDev/src/skland/main.py:212`） |
| `我的干员`、`练度` | `group_id='skland'`, `keywords=[...]` | 5 | 指定干员渲染 `charInfo.html`，否则 `chars.html`（`pluginsDev/src/skland/main.py:236`） |
| `我的基建` | `group_id='skland'`, `keywords=['我的基建']` | 5 | 渲染 `template/building.html`（`pluginsDev/src/skland/main.py:323`） |
| `抽卡记录` | `group_id='skland'`, `keywords=['抽卡记录']` | 5 | 渲染 `template/gacha.html`（`pluginsDev/src/skland/main.py:344`） |
| `我的进度`、`我的关卡` | `group_id='skland'`, `keywords=[...]` | 5 | 渲染 `template/progress.html`（`pluginsDev/src/skland/main.py:396`） |
| `绑定` | `group_id='skland'`, `keywords='绑定'`, `allow_direct=True` | 默认 | 输出 Token 获取引导（`pluginsDev/src/skland/main.py:416`） |
| Token 粘贴 | `verify=is_token_str`, `check_prefix=False`, `allow_direct=True` | 10 | 自动识别并保存 Token（`pluginsDev/src/skland/main.py:437`） |

`is_token_str`（`pluginsDev/src/skland/main.py:146-157`）：尝试按 JSON 解析消息原文，取 `data.content` 并要求 `msg` 含「鹰角网络通行证账号」，成功则返回 `(True, 10, token)`。消息组配置为 `GroupConfig('skland', allow_direct=True)`（`pluginsDev/src/skland/main.py:142`）。

## 文件结构

| 文件/目录 | 作用 |
|-----------|------|
| `__init__.py` | 一行 `from .main import bot`，插件包入口 |
| `main.py` | `bot` 实例、`UserToken` 表、`SKLandPluginInstance` 取数方法、8 个消息处理器 |
| `api.py` | `SKLandAPI` / `SKLandUser`：登录换证、签名、请求头组装、DID 提取、`Constants` 远端常量同步 |
| `gacha.py` | 抽卡记录两条数据源：官方接口与 arkgacha.kwer.top 第三方接口 |
| `tools.py` | `face_detect`：用 OpenCV 检测动漫人脸位置 |
| `lbpcascade_animeface.xml` | OpenCV 动漫人脸级联分类器 |
| `config_templates/global_config_default.json` | 全局配置默认值 |
| `config_templates/global_config_schema.json` | 全局配置 JSON Schema |
| `resource/constants.json` | 远端常量缓存（含各接口 URL、请求头模板、签名头模板） |
| `resource/template.html` | DID 提取用页面模板，含 `{{config}}` 占位符 |
| `resource/fp.min.js` | 设备指纹脚本，被 `template.html` 引用 |
| `img/` | 绑定引导图与截图 |
| `template/` | 8 套 HTML/CSS（userInfo、warehouse、chars、charInfo、building、progress、gacha）+ `assets/`（职业、阵营、稀有度、技能等级等图片）、`js/`、`font/` |
| `README*.md` | 对用户展示的使用指引 |
| `logo.png` | 插件图标 |

## 核心实现

1. **签名算法 `SKLandUser.generate_sign`**（`pluginsDev/src/skland/api.py:195-207`）：
   - 取签名请求头模板 `SIGN_HEADERS_BASE` 副本，写入 `timestamp`，序列化为紧凑 JSON（`separators=(',', ':')`）。
   - 拼接 `path + body_or_query + timestamp + header_ca_str`。
   - `hmac.new(sign_token.encode(), s.encode(), hashlib.sha256).hexdigest()` → 再取 `hashlib.md5(...).hexdigest()`，得到最终 `sign`。
2. **请求头组装 `get_headers`**（`pluginsDev/src/skland/api.py:209-230`）：`cred` 来自凭据、`timestamp` 来自 `get_timestamp`；GET 用 `parse.urlencode(body)` 或 URL 自带 query，POST 用紧凑 JSON；签名后把 `sign` 与 `header_ca` 合并。
3. **时间戳 `get_timestamp`**（`pluginsDev/src/skland/api.py:186-193`）：配置 `skland.web_timestamp` 为真时向 `BINDING_URL` 取服务端时间戳；否则本地 `int(time.time()) - timestamp_delay`（默认延迟 2 秒）。
4. **DID（设备 ID）获取 `__get_did`**（`pluginsDev/src/skland/api.py:157-174`）：读取 `resource/template.html`，把 `{{config}}` 替换为 `SKLAND_SM_CONFIG` 的紧凑 JSON 写入 `resource/temp.html`；用 `basic_browser_service.browser` 打开该 file:// 页面，等待 `.did` 选择器，取其 `inner_text()` 作为 device_id，随后关闭上下文并删除临时文件。即**用真实浏览器执行前端 JS 反混淆脚本生成设备指纹**。
5. **登录换取凭据**（`pluginsDev/src/skland/api.py:114-155`）：`__get_grant` 用 `appCode + token + type`（`type` 由 token 长度是否 > 30 决定）POST 到 `GRANT_CODE_URL` 换取 `code` 与 `uid`；`__get_cred` 用 `code + kind=1` 加 `dId` 头 POST 到 `CRED_CODE_URL` 换取 `cred` 与 `token`（签名密钥）。
6. **用户缓存 `SKLandAPI.user`**（`pluginsDev/src/skland/api.py:94-112`）：以 token 为 key 缓存 `SKLandUser`；同一 user_id 重复绑定时删除旧 token 条目（`pluginsDev/src/skland/api.py:103-104`）。`user_id_map` 属性做 `user_id → token` 反查（`pluginsDev/src/skland/api.py:90-92`）。
7. **常量同步 `Constants.sync`**（`pluginsDev/src/skland/api.py:33-74`）：先取 `remote_config.remote.plugin + '/api/v1/updatetime'` 的 `skland` 字段为远端版本时间；与本地 `resource/constants.json` 的 mtime 比较，过期则拉 `'/api/v1/skland'` 并写回本地文件。两个网络请求均带无限重试（失败 `asyncio.sleep(1)` 后重试）。
8. **Token 有效期处理**（`pluginsDev/src/skland/main.py:160-180` 的 `check_user_info`）：取不到用户信息时，若首次失败则调用 `refresh_token` 后重试一次；仍失败则提示重新绑定。`refresh_token`（`pluginsDev/src/skland/main.py:36-51`）调 `user.refresh_token()` 并回写 `UserToken.token`。
9. **干员详情**（`pluginsDev/src/skland/main.py:236-320`）：`get_longest` 从 `ArknightsGameData.operators` 里匹配消息中最长的干员名；命中则组装 skins / equips / charModules，其中模组属性经 `snake_case_to_pascal_case` + `integer` 转换（`pluginsDev/src/skland/main.py:288-294`）；阿米娅近卫/医疗的特殊 charId 用 `amiya_promotion` 映射（`pluginsDev/src/skland/main.py:250-253`）。未指定干员时附带 `limitChars`/`freeChars`（取自 `OperatorConfig.operator_type` 为 0/1 与 5 的记录，`pluginsDev/src/skland/main.py:302-316`）。
10. **抽卡记录**（`pluginsDev/src/skland/main.py:344-393` + `pluginsDev/src/skland/gacha.py`）：区分官服与 B 服（`server_name == 'bilibili服'` 时改用 `UserToken.bilibili_token`）。两条数据源 —— 官方接口 `get_gacha_official`（`pluginsDev/src/skland/gacha.py:9-47`，翻 1~9 页 `ak.hypergryph.com/user/api/inquiry/gacha`）与第三方 `get_gacha_arkgacha_kwer_top`（按配置 `arkgacha_kwer_top.enable` 切换，签名算法见 `pluginsDev/src/skland/gacha.py:50` 起）。渲染宽度 320。
11. **立绘头像检测**：`face_detect`（`pluginsDev/src/skland/tools.py:6-27`）用 `cv2.CascadeClassifier` 加载 `lbpcascade_animeface.xml` 检测动漫人脸位置，按宽度比例换算坐标，用于干员卡背景构图（`pluginsDev/src/skland/main.py:280`）。
12. **HTML 渲染同步**：`WaitALLRequestsDone`（`pluginsDev/src/skland/main.py:124-127`）重写 `on_page_rendered`，等待 `networkidle` 确保图片加载完成。
13. **敏感信息保护**（`pluginsDev/src/skland/main.py:437-441`）：非私聊场景下粘贴 Token 会先 `data.recall()` 撤回消息，再提示注意保护敏感信息。

## 依赖的 core 能力

`core.AmiyaBotPluginInstance`、`Message`、`Chain`、`Requirement`（`pluginsDev/src/skland/main.py:9`）；`core.util.snake_case_to_pascal_case`、`integer`（`pluginsDev/src/skland/main.py:10`）；`core.database.user.UserBaseModel`（`pluginsDev/src/skland/main.py:11`）；`core.database.bot.OperatorConfig`（`pluginsDev/src/skland/main.py:12`）；`core.resource.arknightsGameData.ArknightsGameData`、`ArknightsGameDataResource`（`pluginsDev/src/skland/main.py:13`）；`core.resource.remote_config`（`pluginsDev/src/skland/api.py:15`）；`amiyabot.builtin.lib.browserService.basic_browser_service`（`pluginsDev/src/skland/api.py:16`，DID 提取）；`amiyabot.network.httpRequests.http_requests`（`pluginsDev/src/skland/api.py:10`）；第三方 `cv2`（可选，缺失时 `face_detect` 返回空列表）。

## 写入的表/目录

表 `UserToken`（`user_id` 主键、`token`、`bilibili_token`，`pluginsDev/src/skland/main.py:22-26`；B 服 Token 特别长故用 `TextField`）。

目录：`resource/constants.json`（远端常量缓存，`pluginsDev/src/skland/api.py:28,64-65`）、`resource/temp.html`（DID 临时文件，用后删除，`pluginsDev/src/skland/api.py:159,173`）。`template/`、`img/` 为只读素材。

## 与其他插件耦合

- `Requirement('amiyabot-arknights-gamedata', official=True)`（`pluginsDev/src/skland/main.py:138`），依赖 `ArknightsGameData.operators` / `materials` 与 `ArknightsGameDataResource.get_skin_file`。
- **被 `arknights/intellect` 反向调用**：`intellect` 在 `记录真实理智` 指令中检查 `'amiyabot-skland' in main_bot.plugins`，并调用 `skland.get_token(user_id)` 与 `skland.get_user_info(token)`（`pluginsDev/src/arknights/intellect/main.py:106-129`）。
- 通过 `skland_api.set_bot(bot)` 把插件实例注入 API 层以读取配置（`pluginsDev/src/skland/main.py:143`）。

## 打包与发布

| 项 | 值 |
|----|----|
| plugin_id | `amiyabot-skland` |
| version | `5.6` |
| 产物 | `amiyabot-skland-5.6.zip` |

元数据定义于 `pluginsDev/src/skland/main.py:130-141`。打包用 `python run_build.py --type plugins`，产出到 `plugins/`。
