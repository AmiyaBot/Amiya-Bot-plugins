import json
import os
import random
import re
import time
import traceback

from typing import Optional, Tuple, Union

from amiyabot import Message, Chain, event_bus
from amiyabot.builtin.messageChain.element import Text
from amiyabot.log import LoggerManager

from core import AmiyaBotPluginInstance, Requirement
from core import bot as main_bot

from .src.context import ChatContextStore, ChatEntry
from .src import prompt_builder
from .src.lore_retriever import LoreRetriever

curr_dir = os.path.dirname(__file__)
log = LoggerManager('AIChat')

BLM_PLUGIN_ID = 'amiyabot-blm-library'

# 纯数字、纯符号等无意义内容不作为主动插话的时机
_meaningless_pattern = re.compile(r'^[\d\s\W]+$')


def get_blm():
    return main_bot.plugins.get(BLM_PLUGIN_ID)


def generate_schema():
    filepath = f'{curr_dir}/configs/global_config_schema.json'

    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        log.info(f'Failed to load JSON from {filepath}.')
        return None

    blm = get_blm()
    if blm:
        try:
            # 与 blm 一致：请求配置时刷新装配，保证刚启用的模型无需重启即出现在枚举中
            if hasattr(blm, 'refresh_adapters'):
                blm.refresh_adapters()
            data['properties']['model']['enum'] = [''] + [model['model_name'] for model in blm.model_list()]
        except KeyError as e:
            log.info(f'Expected keys not found in the JSON structure: {e}')

    return data


class AIChatPluginInstance(AmiyaBotPluginInstance):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._store: Optional[ChatContextStore] = None
        self._retriever: Optional[LoreRetriever] = None

    @property
    def store(self) -> ChatContextStore:
        if self._store is None:
            self._store = ChatContextStore(
                max_messages=self.get_config('context_max_messages') or 20,
                timeout_minutes=self.get_config('context_timeout_minutes') or 30,
            )
        return self._store

    @property
    def retriever(self) -> LoreRetriever:
        if self._retriever is None:
            self._retriever = LoreRetriever()
        return self._retriever

    def install(self):
        # 安装时按当前配置重建上下文存储
        self._store = ChatContextStore(
            max_messages=self.get_config('context_max_messages') or 20,
            timeout_minutes=self.get_config('context_timeout_minutes') or 30,
        )
        # 剧情语料：gamedata 插件已就绪时立即加载，未就绪时静默禁用（事件刷新兜底）
        self.retriever.load()

    def uninstall(self):
        event_bus.unsubscribe('gameDataInitialized', refresh_lore)


bot = AIChatPluginInstance(
    name='AI 对话',
    version='1.3.3',
    plugin_id='amiyabot-ai-chat',
    plugin_type='official',
    description='兜底 AI 对话：其他插件功能优先触发，无人响应时由大语言模型参与聊天',
    document=f'{curr_dir}/README.md',
    instruction=f'{curr_dir}/README_USE.md',
    requirements=[Requirement('amiyabot-blm-library')],
    priority=0,
    global_config_default=f'{curr_dir}/configs/global_config_default.json',
    global_config_schema=generate_schema,
    channel_config_default=f'{curr_dir}/configs/channel_config_default.json',
    channel_config_schema=f'{curr_dir}/configs/channel_config_schema.json',
)


@event_bus.subscribe('gameDataInitialized')
def refresh_lore(_):
    # gamedata 插件刷新资源后同步重建剧情语料（事件语义是「刷新」而非首次初始化）
    if bot.retriever.load():
        log.info('剧情资料语料已刷新')


def context_key(data: Message) -> str:
    if data.is_direct:
        base = data.channel_id or data.guild_id or data.user_id
        return f'direct_{base}_{data.user_id}'
    return data.channel_id or data.guild_id or data.user_id


# 频道默认值：用于判断「频道配置是否被实际定制过」。
# 框架的 get_config 降级链是 频道配置→频道默认→全局，频道配置记录一经保存就会带上全部频道默认值，
# 使共享键的全局设置被永久遮蔽，因此这里对共享键做二次降级。
def _load_channel_defaults() -> dict:
    try:
        with open(f'{curr_dir}/configs/channel_config_default.json', mode='r', encoding='utf-8') as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}


_channel_defaults = _load_channel_defaults()


def effective_config(name: str, data: Message):
    """共享配置键的有效值：频道值等于频道默认值（即未被定制）时降级到全局配置。"""
    value = bot.get_config(name, context_key(data))
    if name in _channel_defaults and value == _channel_defaults[name]:
        return bot.get_config(name)
    return value


def get_config(name: str, data: Message):
    return bot.get_config(name, context_key(data))


def get_weight(data: Message) -> int:
    weight = get_config('reply_priority', data)
    try:
        return int(weight)
    except (TypeError, ValueError):
        return -1


def is_mentioned(data: Message) -> bool:
    text = data.text_original.lower()
    for keyword in get_config('mention_keywords', data) or []:
        if keyword and keyword.lower() in text:
            return True
    return False


def is_self_message(data: Message) -> bool:
    # 部分适配器（如 CQHttp）会投递机器人自己的消息，兜底响应会导致自问自答
    return str(data.user_id) == str(data.instance.appid)


async def check_ai_chat(data: Message):
    """兜底校验：只有当没有其他插件响应时，才由 AI 接手。

    本插件返回的权重固定为可配置的兜底优先级（默认 -1），而框架总是选择
    权重最高的响应，所有正常插件功能的权重都不低于 0。因此这里返回 True
    并不会抢占其他插件，只会在候选中只剩下本插件时被选中。
    """
    if not get_blm():
        return False

    if is_self_message(data):
        return False

    if not data.text_original.strip():
        return False

    channel_id = context_key(data)

    # 生效范围：白名单模式下，仅名单内的群聊开放（私聊不受限）
    if not data.is_direct and bot.get_config('allow_mode') == '仅白名单':
        whitelist = [str(item) for item in (bot.get_config('channel_whitelist') or [])]
        if channel_id not in whitelist:
            return False

    if bot.get_config('enable', channel_id) is False:
        return False

    weight = get_weight(data)
    now = time.time()
    state = bot.store.state(channel_id)

    # AT 机器人：一定响应。其他插件命中时权重机制自动让它们优先。
    if data.is_at:
        return True, weight, {'trigger': 'at'}

    # 私聊：一定响应
    if data.is_direct:
        return True, weight, {'trigger': 'direct'}

    # 频道配置为「仅AT响应」时，群聊普通消息不再触发
    if bot.get_config('at_only', channel_id):
        return False

    # 昵称提及
    if is_mentioned(data):
        return True, weight, {'trigger': 'mention'}

    # 连续对话：AI 回复后不久，同一位用户继续发言视为在延续对话
    followup_window = float(get_config('followup_window_seconds', data) or 0)
    if followup_window > 0 and now - state.last_reply_ts <= followup_window:
        if data.user_id and data.user_id == state.last_reply_user:
            return True, weight, {'trigger': 'followup'}

    # 主动插话：概率 + 冷却，默认关闭
    if effective_config('proactive_reply', data):
        text = data.text_original.strip()
        if not _meaningless_pattern.match(text):
            cooldown = float(effective_config('proactive_cooldown_seconds', data) or 300)
            probability = float(effective_config('proactive_probability', data) or 0)
            if probability > 0 and now - max(state.last_reply_ts, state.last_proactive_ts) >= cooldown:
                if len(bot.store.recent(channel_id)) >= 4 and random.random() < probability:
                    # 在校验阶段即占用冷却，避免短时间多条消息同时通过判断
                    state.last_proactive_ts = now
                    return True, weight, {'trigger': 'proactive'}

    return False


# 模型把思考/导演注释写进正文时的特征词（用于识别开头括号段是否为思考过程，避免误伤正常括号内容）
_reasoning_markers = re.compile(
    '回答|回复|应该|需要|简洁|口语|用户|扮演|设定|输出|语气|风格|要求|提示|介绍|思考|保持|简短'
)
# 行首成对括号段：半角/全角，长度足以排除动作神态类短括号（如「（笑）」）
_leading_paren = re.compile(r'^\s*[（(]([^()（）]{6,300})[)）]\s*')


def _strip_reasoning_prefix(text: str) -> str:
    """剥离回复开头的思考/导演注释段。

    推理模型有时把 reasoning 直接写进正文（或 blm 的 deep_think 把 reasoning_content
    以括号拼在正文前），这些内容对聊天场景是噪音。仅当括号段包含思考特征词时剥离，
    避免误伤正文里正常的括号表达。
    """
    while True:
        matched = _leading_paren.match(text)
        if not matched:
            return text
        if not _reasoning_markers.search(matched.group(1)):
            return text
        rest = text[matched.end() :]
        if not rest.strip():
            # 整条回复只有括号段时保留原文，避免把回复清空
            return text
        text = rest


def _collapse_repetition(text: str) -> str:
    """折叠整段重复的回复（如「X\\nX\\nX」→「X」）。

    上下文若混入了重复的自身发言，模型会模仿这种重复；此处在输出侧兜底压成一份。
    仅在全文由完全相同的若干段构成时才折叠，不会影响正常的排比或重复用词。
    """
    stripped = text.strip()
    if len(stripped) < 20:
        return text

    # 按行重复（最常见形态：同一句被逐行重复）
    lines = [line.strip() for line in stripped.split('\n') if line.strip()]
    if len(lines) >= 2 and len(set(lines)) == 1:
        return lines[0]

    # 无缝块重复（同一段文字直接拼接多次）
    length = len(stripped)
    for count in range(2, 6):
        if length % count:
            continue
        unit = stripped[: length // count]
        if unit.strip() and unit * count == stripped:
            return unit

    return text


def clean_reply(text: str, max_length: int) -> str:
    text = re.sub(r'<think>.*?</think>', '', text or '', flags=re.S).strip()
    text = _strip_reasoning_prefix(text)
    text = _collapse_repetition(text)
    # 去掉模型自我标注的前缀与包裹引号
    text = re.sub(r'^(阿米娅|Amiya|amiya)\s*[:：]\s*', '', text).strip()
    if len(text) >= 2 and text[0] in "'\"“”‘’「」【】" and text[-1] in "'\"“”‘’「】":
        text = text[1:-1].strip()

    if max_length > 0 and len(text) > max_length:
        cut = text[:max_length]
        for sep in ['\n', '。', '！', '？', '；', '，', ' ']:
            index = cut.rfind(sep)
            if index > max_length * 0.5:
                cut = cut[: index + 1]
                break
        text = cut

    return text.strip()


def resolve_model(data: Message) -> Optional[Tuple[str, object]]:
    """确定使用的模型。返回 (model_name, adapter)，没有可用模型时返回 None。"""
    blm = get_blm()
    if not blm:
        return None

    model_name = effective_config('model', data)
    adapter = None

    if model_name:
        adapter = blm.model_map.get(model_name)
        if adapter is None:
            log.warning(f'模型 {model_name} 不存在，回退到调用库默认模型')

    if adapter is None:
        default = blm.get_default_model()
        if not default:
            log.warning('未配置任何可用模型，请先在「大语言模型调用库」中配置模型提供商并设置默认模型')
            return None
        model_name = default['model_name']
        adapter = blm.model_map.get(model_name)

    return model_name, adapter


async def call_llm(data: Message, history: list, directed: bool, references: str = '') -> Optional[str]:
    blm = get_blm()
    if not blm:
        return None

    channel_id = context_key(data)
    resolved = resolve_model(data)
    if not resolved:
        return None

    model_name, adapter = resolved
    persona = effective_config('system_prompt', data) or ''

    # 上下文由本插件管理（不传 context_id），按适配器能力选择消息形态
    if getattr(adapter, 'supports_role_messages', False):
        prompt = prompt_builder.build_role_messages(persona, history, directed, references)
    else:
        prompt = prompt_builder.build_text_prompt(persona, history, directed, references)

    try:
        return await blm.chat_flow(prompt, model=model_name, channel_id=channel_id)
    except Exception as e:
        log.error(f'AI 对话调用失败: {e}\n{traceback.format_exc()}')
        return None


@bot.message_created
async def _(data: Message, _):
    # 收集上下文：所有收到的消息（包括将由其他插件处理的消息）都会进入记录。
    # 本钩子只记录，不响应，因此群聊开启接收全部消息也不会刷屏。
    if is_self_message(data):
        return data

    text = data.text_original.strip()
    if not text:
        if data.image:
            text = '[图片]'
        elif data.face:
            text = '[表情]'
        else:
            return data

    bot.store.record(
        context_key(data),
        ChatEntry(time=time.time(), user_id=data.user_id, nickname=data.nickname, text=text),
    )

    return data


@bot.message_after_send
async def _(data: Chain, factory_name: str, _):
    # 机器人（含本插件与其他插件）发出的回复进入上下文，让 AI 知道大家聊到了哪。
    # 这是机器人发言进入上下文的唯一入口：handler 生成回复后不再重复记录，
    # 否则每条回复会在上下文里出现两遍，模型看到后模仿重复，形成 2→4→8 的递增劣化。
    if not data.data:
        return

    text = '\n'.join(item.content for item in data.chain if isinstance(item, Text)).strip()
    if not text:
        return

    key = context_key(data.data)
    entries = bot.store.recent(key)

    # 幂等保护：同一句回复在短时间内被重复投递（部分适配器/多账号会重复触发）时只记一次
    if entries and entries[-1].is_bot and entries[-1].text == text and time.time() - entries[-1].time < 5:
        return

    bot.store.record(
        key,
        ChatEntry(time=time.time(), user_id='', nickname='阿米娅', text=text, is_bot=True),
    )


@bot.on_message(verify=check_ai_chat, check_prefix=False, allow_direct=True)
async def _(data: Message):
    keypoint = data.verify.keypoint if data.verify else {}
    trigger = keypoint.get('trigger', '') if isinstance(keypoint, dict) else ''
    channel_id = context_key(data)
    state = bot.store.state(channel_id)
    now = time.time()

    # 除 AT / 私聊 / 昵称提及外的触发（连续对话、主动插话）受最小回复间隔约束
    if trigger in ('followup', 'proactive'):
        min_interval = float(get_config('min_reply_interval_seconds', data) or 0)
        if now - state.last_reply_ts < min_interval:
            return None

    history = bot.store.recent(channel_id)
    if not history:
        return None

    directed = trigger != 'proactive'

    # 剧情资料检索：档案语料就绪且未在频道禁用时，把相关片段注入提示词
    references = ''
    if effective_config('lore_retrieval', data) is not False:
        max_chars = int(get_config('lore_max_chars', data) or 2400)
        context_text = ' '.join(entry.text for entry in history[-5:] if not entry.is_bot)
        references = bot.retriever.retrieve(history[-1].text, context_text, max_chars)

    reply = await call_llm(data, history, directed, references)
    if not reply:
        return None

    reply = clean_reply(reply, int(get_config('max_reply_length', data) or 0))
    if not reply:
        return None

    state.last_reply_ts = now
    state.last_reply_user = data.user_id
    # 回复本身由 message_after_send 在发送后记入上下文，此处不再记录（避免重复）

    at = bool(get_config('at_reply', data)) and trigger == 'at'
    return Chain(data, at=at).text(reply)
