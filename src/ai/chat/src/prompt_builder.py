import os

from datetime import datetime
from typing import List, Optional

from .context import ChatEntry

curr_dir = os.path.dirname(__file__)
default_persona_path = os.path.abspath(f'{curr_dir}/../template/Amiya.txt')

# 角色消息模式下，历史记录中同一角色的连续消息需要合并，避免部分服务商拒绝连续同角色消息
_output_rules_directed = (
    '（输出要求）\n'
    '1. 你正在QQ聊天中与他人对话，回复要口语化、简短自然，一般不超过100字。\n'
    '2. 直接输出回复内容，不要输出旁白、心理描写、括号说明或任何前缀。\n'
    '3. 记录中的发言者只是聊天参与者，你只能以阿米娅的身份发言，不要替他人发言。\n'
    '4. 最新一条消息是对你说的，请结合上下文直接回复。'
)

_output_rules_proactive = (
    '（输出要求）\n'
    '1. 你正在QQ群聊中旁观大家的聊天，现在可以选择自然地加入话题，插一句话。\n'
    '2. 回复要口语化、简短自然，一般不超过50字，不要输出旁白、心理描写或任何前缀。\n'
    '3. 记录中的发言者只是聊天参与者，你只能以阿米娅的身份发言，不要替他人发言。\n'
    '4. 如果话题不适合参与，可以简短地表达一下关注或关心。'
)


def load_default_persona() -> Optional[str]:
    if os.path.exists(default_persona_path):
        with open(default_persona_path, mode='r', encoding='utf-8') as file:
            return file.read()
    return None


def build_system_prompt(persona: Optional[str], directed: bool, references: str = '') -> str:
    """组装 system 提示词：人设 + 剧情资料 + 动态时间 + 输出要求。"""
    if not persona or not persona.strip():
        persona = load_default_persona() or '你是阿米娅，罗德岛的公开领袖，请以阿米娅的身份与大家聊天。'

    now = datetime.now()
    calendar = ['一', '二', '三', '四', '五', '六', '日'][now.weekday()]
    time_text = f'（当前时间：{now.year}年{now.month}月{now.day}日 星期{calendar} {now.hour:02d}:{now.minute:02d}）'

    rules = _output_rules_directed if directed else _output_rules_proactive

    reference_text = ''
    if references and references.strip():
        reference_text = (
            '（罗德岛内部资料，与当前话题相关。回答时可以参考这些资料，'
            '资料中没有的内容请明确表示不确定，不要编造）\n'
            f'{references.strip()}\n\n'
        )

    return f'{persona.strip()}\n\n{reference_text}{time_text}\n\n{rules}'


def build_role_messages(
    persona: Optional[str],
    history: List[ChatEntry],
    directed: bool,
    references: str = '',
) -> List[dict]:
    """构建 OpenAI 格式的多轮消息。

    history 为按时间排序的上下文（含触发消息），其中机器人自己的发言映射为
    assistant 角色，其他人的发言以「昵称：内容」的形式映射为 user 角色。
    """
    messages = [{'role': 'system', 'content': build_system_prompt(persona, directed, references)}]

    for entry in history:
        if entry.is_bot:
            content = entry.text
        else:
            name = entry.nickname or entry.user_id or '用户'
            content = f'{name}：{entry.text}'

        role = 'assistant' if entry.is_bot else 'user'
        if messages[-1]['role'] == role:
            messages[-1]['content'] += '\n' + content
        else:
            messages.append({'role': role, 'content': content})

    return messages


def build_text_prompt(
    persona: Optional[str],
    history: List[ChatEntry],
    directed: bool,
    references: str = '',
) -> str:
    """构建纯文本提示词，供不支持角色消息的适配器（ERNIE / ChatGPT 等）使用。"""
    lines = []
    for entry in history:
        if entry.is_bot:
            lines.append(f'阿米娅（你）：{entry.text}')
        else:
            name = entry.nickname or entry.user_id or '用户'
            lines.append(f'{name}：{entry.text}')

    transcript = '\n'.join(lines)
    system = build_system_prompt(persona, directed, references)
    rules = '请直接以阿米娅的身份输出回复内容本身' if directed else '请直接以阿米娅的身份输出一句自然的插话'

    return f'{system}\n\n（以下是最近的聊天记录）\n{transcript}\n\n（{rules}，不要复述记录。）'
