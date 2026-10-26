import time

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional


@dataclass
class ChatEntry:
    """一条群聊上下文记录。is_bot 为 True 时表示是机器人自己（含其他插件）发出的消息。"""

    time: float
    user_id: str
    nickname: str
    text: str
    is_bot: bool = False


@dataclass
class ChannelState:
    history: Deque[ChatEntry] = field(default_factory=deque)
    last_reply_ts: float = 0.0
    last_reply_user: str = ''
    last_proactive_ts: float = 0.0


class ChatContextStore:
    """内存态的频道上下文存储。

    群聊开启「接收全部消息」后，机器人会收到每一条消息，但绝不能每条都回。
    本存储只负责安静地收集上下文与维护触发时机状态，是否回复由触发逻辑决定。
    """

    def __init__(self, max_messages: int = 20, timeout_minutes: float = 30):
        self.max_messages = max(4, int(max_messages))
        self.timeout_seconds = max(1.0, float(timeout_minutes) * 60)
        self.channels: Dict[str, ChannelState] = {}

    def state(self, channel_id: str) -> ChannelState:
        if channel_id not in self.channels:
            self.channels[channel_id] = ChannelState()
        return self.channels[channel_id]

    def record(self, channel_id: str, entry: ChatEntry):
        state = self.state(channel_id)
        state.history.append(entry)

        # 上限限制 + 超时裁剪，保证上下文始终是最近的一小段对话
        while len(state.history) > self.max_messages:
            state.history.popleft()
        self._prune(state)

    def recent(self, channel_id: str) -> List[ChatEntry]:
        state = self.state(channel_id)
        self._prune(state)
        return list(state.history)

    def forget(self, channel_id: str):
        self.channels.pop(channel_id, None)

    def _prune(self, state: ChannelState):
        deadline = time.time() - self.timeout_seconds
        while state.history and state.history[0].time < deadline:
            state.history.popleft()
