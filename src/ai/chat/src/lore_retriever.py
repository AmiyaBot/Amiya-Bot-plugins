import os

from typing import Dict, List

import jieba

from amiyabot.log import LoggerManager

from . import lore_builder

log = LoggerManager('AILoreRetriever')

_userdict_path = 'resource/plugins/ai-chat/lore_names.txt'

# 关键词提取的停用词
_stopwords = {
    '什么',
    '怎么',
    '怎样',
    '如何',
    '为什么',
    '可以',
    '能够',
    '应该',
    '需要',
    '这个',
    '那个',
    '这些',
    '那些',
    '他们',
    '她们',
    '它们',
    '我们',
    '你们',
    '自己',
    '大家',
    '就是',
    '还是',
    '没有',
    '不是',
    '一下',
    '一些',
    '有点',
    '介绍',
    '讲讲',
    '说说',
    '告诉',
    '知道',
    '了解',
    '感觉',
    '觉得',
    '原来',
    '现在',
    '今天',
    '时候',
    '地方',
    '方面',
    '内容',
    '问题',
    '东西',
    '事情',
    '剧情',
    '故事',
    '章节',
    '台词',
    '其中',
    '之后',
    '以前',
    '以及',
}

# 语料块切分的目标长度
_chunk_size = 700


class LoreChunk:
    __slots__ = ('header', 'owner', 'text')

    def __init__(self, header: str, owner: str, text: str):
        self.header = header
        self.owner = owner
        self.text = text


class LoreRetriever:
    """剧情语料检索器：语料由 lore_builder 清洗为 txt（干员/NPC 档案 + 主线活动剧情），
    检索时按「档案主人直读 + 关键词全文召回」两路取片段注入提示词。

    干员数值类问答由 arknights 系列插件负责，本检索器只服务 AI 对话的剧情/世界观注入。
    """

    def __init__(self):
        self.chunks: List[LoreChunk] = []
        self.owner_chunks: Dict[str, List[int]] = {}
        self.book_chunks: Dict[str, List[int]] = {}
        self.ready = False
        self._version = ''

    def load(self) -> bool:
        """构建（如需）并索引语料库。gamedata 未就绪时返回 False，检索保持静默禁用。"""
        if not os.path.exists(lore_builder.gamedata_marker_path):
            return False

        # 语料版本未变化时跳过重建与重索引（事件刷新与 install 会重复调用 load）
        try:
            with open(lore_builder.gamedata_marker_path, mode='r', encoding='utf-8') as file:
                version = file.read().strip()
        except OSError:
            version = ''

        if self.ready and version and version == self._version:
            return True

        if not lore_builder.build_corpus():
            self.ready = False
            return False

        chunks: List[LoreChunk] = []
        owner_chunks: Dict[str, List[int]] = {}
        book_chunks: Dict[str, List[int]] = {}

        for root, dirs, files in os.walk(lore_builder.corpus_dir):
            rel_dir = os.path.relpath(root, lore_builder.corpus_dir)

            for filename in sorted(files):
                if not filename.endswith('.txt'):
                    continue

                name = filename[:-4]
                is_profile = rel_dir == 'profiles'

                try:
                    with open(os.path.join(root, filename), mode='r', encoding='utf-8') as file:
                        text = file.read()
                except OSError:
                    continue

                header = f'档案·{name}' if is_profile else f'剧情·{name}'
                owner = name if is_profile else ''

                for piece in _split_chunks(text):
                    chunks.append(LoreChunk(header, owner, piece))
                    if is_profile and owner:
                        owner_chunks.setdefault(owner.lower(), []).append(len(chunks) - 1)
                    elif rel_dir.startswith('stories'):
                        # 书名实体：文件名形如「生于黑夜-XX 行动前」，书名取「-」前缀
                        book = name.split('-')[0].strip().lower()
                        if book:
                            book_chunks.setdefault(book, []).append(len(chunks) - 1)

        if not chunks:
            log.warning('剧情语料为空，检索保持禁用')
            return False

        self.chunks = chunks
        self.owner_chunks = owner_chunks
        self.book_chunks = book_chunks
        self._load_userdict(list(owner_chunks.keys()) + sorted(book_chunks.keys()))
        self.ready = True
        self._version = version

        total = sum(len(chunk.text) for chunk in chunks)
        log.info(f'剧情语料索引完成: {len(chunks)} 块, 约 {total / 10000:.1f} 万字')
        return True

    @staticmethod
    def _load_userdict(names):
        try:
            os.makedirs(os.path.dirname(_userdict_path), exist_ok=True)
            with open(_userdict_path, mode='w', encoding='utf-8') as file:
                file.write('\n'.join(f'{name} 500 n' for name in names))
            jieba.load_userdict(_userdict_path)
        except OSError as e:
            log.warning(f'jieba 用户词典写入失败: {e}')

    @staticmethod
    def _keywords(text: str) -> List[str]:
        result = []

        stripped = text.strip()
        if 2 <= len(stripped) <= 12:
            # 完整短语是最强的共现信号（如「卡兹戴尔」「赫德雷和伊内斯」）
            result.append(stripped)

        for word in jieba.lcut(text):
            word = word.strip()
            if len(word) < 2 or word in _stopwords or word in result:
                continue
            if not any('\u4e00' <= char <= '\u9fa5' for char in word):
                # 纯数字与 ASCII 碎片对剧情检索没有意义
                continue
            result.append(word)

        return result

    @staticmethod
    def _render(chunk: LoreChunk, cap: int) -> str:
        text = chunk.text
        if len(text) > cap:
            text = text[:cap]
            for sep in ['。', '！', '？', '……', '；', '\n']:
                index = text.rfind(sep)
                if index > cap * 0.5:
                    text = text[: index + 1]
                    break

        return f'【{chunk.header}】{text.strip()}'

    def retrieve(self, query: str, context: str = '', max_chars: int = 2400) -> str:
        """召回与话题相关的资料片段，渲染为资料块。未就绪或无命中时返回空串。"""
        if not self.ready or not query:
            return ''

        combined = f'{context} {query}'.lower()

        # 档案主人实体：话题主角优先，仅出现在上下文中的实体（代词消解）排在其后。
        # 单字名（如「黑」「陈」）不做子串匹配，误命中太多。
        query_low = query.lower()
        exact = [name for name in self.owner_chunks if len(name) >= 2 and name in combined]
        exact.sort(key=lambda name: (name not in query_low, -len(name)))

        # 书名实体：长书名（≥3字）可在话题或上下文中命中；双字书名（如「春分」「孤星」
        # 是常用词）仅当出现在当前消息时命中；单字书名（如「墟」）不做实体匹配
        books = [
            book
            for book in self.book_chunks
            if (len(book) >= 3 and book in combined) or (len(book) == 2 and book in query_low)
        ]
        books.sort(key=len, reverse=True)

        # 模糊实体：处理书写变体（如「伊内斯」↔游戏内写法「伊内丝」），用去尾前缀探测
        seen = set(exact)
        fuzzy = []
        for name in sorted(self.owner_chunks, key=len, reverse=True):
            if name in seen or len(name) < 3:
                continue
            if name[:-1] in combined:
                fuzzy.append(name)
                seen.add(name)
                if len(fuzzy) >= 3:
                    break

        used = set()
        parts: List[str] = []
        budget = max(400, max_chars)

        for name in exact + fuzzy:
            indices = sorted(
                self.owner_chunks[name][:8],
                key=lambda index: (_profile_priority(self.chunks[index].text), index),
            )
            for index in indices:
                if index in used or budget < 200:
                    break
                piece = self._render(self.chunks[index], cap=500)
                parts.append(piece)
                used.add(index)
                budget -= len(piece) + 1

        for book in books:
            for index in self.book_chunks[book][:10]:
                if index in used or budget < 200:
                    break
                piece = self._render(self.chunks[index], cap=400)
                parts.append(piece)
                used.add(index)
                budget -= len(piece) + 1

        # 关键词全文召回：跨档案与剧情正文的共现片段（人物关系、势力背景等）
        keywords = self._keywords(query)
        if keywords and budget >= 200:
            scored = []
            for index, chunk in enumerate(self.chunks):
                if index in used:
                    continue
                score = 0
                for word in keywords:
                    hits = chunk.text.count(word)
                    if hits:
                        score += hits
                        if len(word) >= 3 and word in chunk.header:
                            score += 2
                if score:
                    # 长度阻尼，避免长文本天然占优
                    scored.append((score * 1000 / (300 + len(chunk.text)), index))

            scored.sort(reverse=True)
            for _, index in scored[:8]:
                if budget < 200:
                    break
                piece = self._render(self.chunks[index], cap=400)
                parts.append(piece)
                used.add(index)
                budget -= len(piece) + 1

        return '\n'.join(parts)


def _profile_priority(text: str) -> int:
    """档案主人直读的段落优先级：履历与剧情资料在前，体检数值与临床诊断殿后。"""
    if text.startswith('【基础档案】') or text.startswith('【临床诊断分析】'):
        return 2
    if text.startswith('【客观履历】'):
        return 0
    return 1


def _split_chunks(text: str, size: int = _chunk_size) -> List[str]:
    """把长文本按段落边界切成检索块。"""
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    if not paragraphs:
        return []

    chunks = []
    current = ''

    for paragraph in paragraphs:
        while len(paragraph) > size:
            # 超长段落先落盘已有内容，再硬切段落本身
            if current:
                chunks.append(current)
                current = ''
            chunks.append(paragraph[:size])
            paragraph = paragraph[size:]

        if len(current) + len(paragraph) + 1 > size:
            chunks.append(current)
            current = paragraph
        else:
            current = f'{current}\n{paragraph}' if current else paragraph

    if current:
        chunks.append(current)

    return chunks
