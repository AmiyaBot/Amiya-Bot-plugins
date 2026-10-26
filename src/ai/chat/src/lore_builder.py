import json
import os
import re
import shutil

from typing import Dict, List

from amiyabot.log import LoggerManager

log = LoggerManager('AILoreBuilder')

# gamedata 插件把 assets 仓库克隆到 resource/gamedata，gamedata.zip 解压在其 gamedata/ 子目录
gamedata_marker_path = 'resource/gamedata/version.txt'
gamedata_dir = 'resource/gamedata/gamedata'
corpus_dir = 'resource/plugins/ai-chat/lore'

_xml_tag = re.compile(r'<[^>]+>', re.S)
_nickname_patterns = [
    ('Dr.{@nickname}', '博士'),
    ('{@nickname}博士', '博士'),
    ('{@nickname}', '博士'),
    ('Dr.{@Nickname}', '博士'),
    ('{@Nickname}博士', '博士'),
    ('{@Nickname}', '博士'),
]

_filename_illegal = re.compile(r'[\\/:*?"<>|]')


def _check_nickname(line: str) -> str:
    for pattern, replacement in _nickname_patterns:
        line = line.replace(pattern, replacement)
    return line


def read_story_script(path: str, char_names: Dict[str, str]) -> str:
    """清洗剧情脚本文本：台词行归一为「角色：“台词”」，丢弃演出与镜头标记。

    移植自 AmiyaBot/Amiya-Bot-knowledge-base 的 read_content。
    """
    if not path or not os.path.exists(path):
        return ''

    try:
        with open(path, mode='r', encoding='utf-8') as file:
            content = file.read()
    except OSError as e:
        log.warning(f'剧情脚本读取失败: {path} {e}')
        return ''

    paragraph = 0
    lines: List[str] = []

    for row in content.split('\n'):
        line = _check_nickname(row)

        if line.startswith('['):
            matched = re.search(r'^\[name="(\S+)?"](.*)', line)
            if matched:
                if paragraph != 1:
                    lines.append('')
                    paragraph = 1
                lines.append(f'{matched.group(1) or "（未知）"}：“{matched.group(2).strip()}”')
                continue

            matched = re.search(r'text="([^"]+)"', line)
            if matched:
                if paragraph != 2:
                    lines.append('')
                    paragraph = 2
                lines.append(matched.group(1).replace('\\n', ''))
                continue

            matched = re.search(r'^\[Dialog\(head="(\S+)",.*](.*)', line)
            if matched:
                if paragraph != 3:
                    lines.append('')
                    paragraph = 3
                name = char_names.get(matched.group(1), '')
                lines.append(f'{name or "（未知）"}：“{matched.group(2).strip()}”')
                continue
        else:
            if paragraph != 0:
                lines.append('')
                paragraph = 0

            lines.append(line)

    return _xml_tag.sub('', '\n'.join(lines)).strip('\n')


def _char_names() -> Dict[str, str]:
    """charId -> 中文名。gamedata 新版已把 handbook 的 infoName 匿名化为 Unknown，
    真实名取自 character_table 解析出的内存对象 ArknightsGameData.operators。"""
    names: Dict[str, str] = {}
    try:
        from core.resource.arknightsGameData import ArknightsGameData

        operators = ArknightsGameData.operators or {}
    except Exception:
        operators = {}

    for key, operator in operators.items():
        name = getattr(operator, 'name', '')
        if not name:
            continue
        names[key] = name
        operator_id = getattr(operator, 'id', '')
        if operator_id:
            names[operator_id] = name

    return names


def _write(path: str, content: str):
    path = os.path.join(corpus_dir, path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode='w', encoding='utf-8') as file:
        file.write(content)


def _build_profiles(char_names: Dict[str, str]) -> int:
    """干员/NPC 档案 → profiles/<名>.txt（档案段落 + 干员密录剧情）。"""
    table_path = f'{gamedata_dir}/excel/handbook_info_table.json'

    with open(table_path, mode='r', encoding='utf-8') as file:
        data = json.load(file)

    profiles: Dict[str, List[str]] = {}

    def collect(owner: str, entry: dict):
        sections = []
        for item in entry.get('storyTextAudio') or []:
            title = (item.get('storyTitle') or '').strip()
            for story in item.get('stories') or []:
                text = (story.get('storyText') or '').strip()
                if text:
                    sections.append(f'【{title}】{text}' if title else text)

        for group in entry.get('handbookAvgList') or []:
            set_name = (group.get('storySetName') or '').strip()
            contents = []
            for avg in group.get('avgList') or []:
                if avg.get('storyIntro'):
                    contents.append(avg['storyIntro'])
                # storyInfo 位于 story/[uc]info/...，storyTxt 位于 story/...
                if avg.get('storyInfo'):
                    contents.append(read_story_script(f'{gamedata_dir}/story/[uc]{avg["storyInfo"]}.txt', char_names))
                if avg.get('storyTxt'):
                    contents.append(read_story_script(f'{gamedata_dir}/story/{avg["storyTxt"]}.txt', char_names))
            content = '\n'.join(part for part in contents if part).strip()
            if content:
                sections.append(f'【{set_name}】{content}' if set_name else content)

        if sections:
            profiles.setdefault(name_of(owner), []).append('\n\n'.join(sections))

    def name_of(owner: str) -> str:
        return _filename_illegal.sub('_', owner.strip())

    for char_id, entry in (data.get('handbookDict') or {}).items():
        fallback = (entry.get('infoName') or '').strip()
        name = char_names.get(char_id) or (fallback if fallback and fallback != 'Unknown' else '')
        if name:
            collect(name, entry)

    for entry in (data.get('npcDict') or {}).values():
        name = (entry.get('name') or '').strip()
        if name:
            collect(name, entry)

    for name, sections in profiles.items():
        _write(f'profiles/{name}.txt', '\n\n'.join(sections))

    return len(profiles)


def _build_stories(char_names: Dict[str, str]) -> int:
    """主线与活动剧情 → stories/<书名>/<章节>.txt。移植 gen_story 的主线/活动部分。"""
    table_path = f'{gamedata_dir}/excel/story_review_table.json'

    with open(table_path, mode='r', encoding='utf-8') as file:
        review = json.load(file)

    books = set()

    for item in (review.values() if isinstance(review, dict) else review):
        entry_id = item.get('id') or ''
        if not (entry_id.startswith('main') or 'act' in entry_id):
            continue

        book = _filename_illegal.sub('_', (item.get('name') or entry_id).strip())
        sections = sorted(item.get('infoUnlockDatas') or [], key=lambda n: n.get('storySort') or 0)

        for sec in sections:
            content = read_story_script(f"{gamedata_dir}/story/{sec.get('storyTxt')}.txt", char_names)
            if not content:
                continue

            section = f"{book}-{sec.get('storyName', '')} {sec.get('avgTag', '')}".strip()
            section = section.replace(':', '：').replace('?', '？')
            section = _filename_illegal.sub('_', section)

            _write(f'stories/{book}/{section}.txt', content)
            books.add(book)

    return len(books)


def build_corpus() -> bool:
    """清洗剧情数据为 txt 语料库。gamedata 版本变化时重建，否则跳过。"""
    if not (os.path.exists(gamedata_marker_path) and os.path.exists(f'{gamedata_dir}/excel/handbook_info_table.json')):
        return False

    try:
        with open(gamedata_marker_path, mode='r', encoding='utf-8') as file:
            version = file.read().strip()
    except OSError:
        version = ''

    version_file = f'{corpus_dir}/.version'
    if os.path.exists(version_file):
        try:
            with open(version_file, mode='r', encoding='utf-8') as file:
                if file.read().strip() == version and (
                    os.path.exists(f'{corpus_dir}/profiles') or os.path.exists(f'{corpus_dir}/stories')
                ):
                    return True
        except OSError:
            pass

    log.info('开始构建剧情语料库...')

    if os.path.exists(corpus_dir):
        shutil.rmtree(corpus_dir)

    char_names = _char_names()

    # 分段容错：档案与剧情任一失败不影响另一部分产出
    profile_count = 0
    book_count = 0
    try:
        profile_count = _build_profiles(char_names)
    except Exception as e:
        log.error(f'档案语料构建失败: {e}')

    try:
        book_count = _build_stories(char_names)
    except Exception as e:
        log.error(f'剧情书语料构建失败: {e}')

    if not profile_count and not book_count:
        return False

    os.makedirs(corpus_dir, exist_ok=True)
    with open(version_file, mode='w', encoding='utf-8') as file:
        file.write(version)

    log.info(f'剧情语料库构建完成: {profile_count} 份档案, {book_count} 本剧情书')
    return True
