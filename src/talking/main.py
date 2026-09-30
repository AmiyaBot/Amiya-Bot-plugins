import os
import re
import time
import aiohttp
import random
import shutil
import tempfile
from datetime import datetime

from amiyabot import Message, Chain
from core import AmiyaBotPluginInstance

curr_dir = os.path.dirname(__file__)
face_dir = 'resource/plugins/user/face'


# Image URL cache: url -> (text, image_url_or_path, timestamp)
_url_cache: dict[str, tuple[str, str | None, float]] = {}
_cache_timeout = 300  # 5 minutes cache
_temp_dir = tempfile.gettempdir()  # the cache file is saved in the system temporary directory

# Random variable: {rand} / {rand:min,max} / {rand:text1,text2,...}
# the argument can contain the nested variables and braces, such as {rand:{nickname} hello}
_rand_prefix = '{rand'
_number_pattern = re.compile(r'[+-]?\d*\.?\d+')

# Date and time variable: {date} / {date:YYYY-M-d ddd} / {time} / {time:HH:mm}
_datetime_pattern = re.compile(r'\{(date|time)(?::([^}]*))?\}')

# URL variable, page variable, face variable and the image path in the content,
# such as the path returned by a random variable
_content_pattern = re.compile(
    r'\{url:(?P<url>[^}]+)\}'
    r'|\{page:(?P<page>[^{}]+)\}'
    r'|\{face\}'
    r'|(?P<path>(?:[A-Za-z]:[\\/]|[\\/]|[\w.\-]+[\\/])[^\s<>"|?*\r\n]*?\.(?:png|jpe?g|gif|webp|bmp|ico))',
    re.IGNORECASE,
)

# The default render options of the page variable: render time, width and height
_page_default_options = (1000, 1280, 720)

# The parsed content of a reply, each item is a (kind, content, options) tuple:
#   ('text', text, ()) / ('image', path, ()) / ('page', url, (render_time, width, height))
_ContentElement = tuple[str, str, tuple[int, ...]]

_month_names = ['一月', '二月', '三月', '四月', '五月', '六月',
                '七月', '八月', '九月', '十月', '十一月', '十二月']
_weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
_full_weekday_names = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']

# The braces of the content wrapped by backquote are escaped, so that it can be output as is
_escape_open = '\x00'
_escape_close = '\x01'


def _get_cached(url: str) -> tuple[str, str | None] | None:
    """Get cached content if not expired."""
    if url in _url_cache:
        text, img, timestamp = _url_cache[url]
        if time.time() - timestamp < _cache_timeout:
            return text, img
        else:
            # Remove expired cache
            del _url_cache[url]
            # Clean up temp file
            if img and os.path.exists(img) and img.startswith(_temp_dir):
                try:
                    os.remove(img)
                except Exception:
                    pass
    return None


def _is_image_by_content(data: bytes) -> tuple[bool, str]:
    """Detect if content is an image by magic bytes.
    
    Returns:
        tuple: (is_image, extension)
    """
    if len(data) < 4:
        return False, ''
    # PNG, JPEG, GIF, WebP magic bytes
    signatures = [
        (b'\x89PNG\r\n\x1a\n', '.png'),
        (b'\xff\xd8\xff', '.jpg'),
        (b'GIF87a', '.gif'),
        (b'GIF89a', '.gif'),
        (b'RIFF', '.webp'),  # WebP starts with RIFF....WEBP
        (b'BM', '.bmp'),     # BMP
    ]
    for sig, ext in signatures:
        if data.startswith(sig):
            return True, ext
    return False, ''


def _is_image_by_url(url: str) -> tuple[bool, str]:
    """Detect if URL likely points to an image by extension."""
    image_exts = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.ico'}
    lower = url.lower()
    for ext in image_exts:
        if lower.endswith(ext) or ('?' in lower and lower.split('?')[0].endswith(ext)):
            return True, ext
    return False, ''


async def fetch_url_content(url: str) -> tuple[str, str | None]:
    """Fetch content from a URL with intelligent detection.
    
    Returns:
        tuple: (text content, image path if it's an image, else None)
    """
    # Check cache with expiration
    cached = _get_cached(url)
    if cached:
        return cached
    
    cache_path = os.path.join(_temp_dir, f'url_content_{abs(hash(url))}')
    
    try:
        # Always download and save content first
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=10),
                ssl=False  # Skip SSL verification for self-signed certificates
            ) as response:
                if response.status == 200:
                    data = await response.read()
                    
                    # Save raw content
                    with open(cache_path, 'wb') as f:
                        f.write(data)
                    
                    # Then check if it's an image by content
                    is_image, ext = _is_image_by_content(data)
                    
                    if is_image:
                        # Rename to proper extension, the old cache file is replaced
                        img_path = f'{cache_path}{ext}'
                        os.replace(cache_path, img_path)
                        _url_cache[url] = ('', img_path, time.time())
                        return '', img_path
                    
                    # Return text content
                    text = data.decode('utf-8', errors='ignore')
                    _url_cache[url] = (text, None, time.time())
                    return text, None
                    
    except Exception as e:
        print(f'[TalkingPlugin] Fetch URL error: {url}, error: {e}')
    
    _url_cache[url] = ('', None, time.time())
    return '', None


def get_face() -> list[str]:
    """Get all face image paths from the face directory."""
    images: list[str] = []
    for root, _, files in os.walk(face_dir):
        images += [os.path.join(root, file) for file in files if file != '.gitkeep']

    return images


def generate_random_number(min_val: float, max_val: float, decimal: int = 0) -> str:
    """Generate a random number string within the given range."""
    return f'{random.uniform(min_val, max_val):.{decimal}f}'


def _decimal_places(argument: str) -> int:
    """Get the number of decimal places of a numeric argument."""
    return len(argument.split('.')[1]) if '.' in argument else 0


def _is_number(argument: str) -> bool:
    """Check if the argument is a numeric value."""
    return bool(_number_pattern.fullmatch(argument))


def _escape_braces(text: str) -> str:
    """Escape the braces to keep the text away from being parsed as a variable."""
    return text.replace('{', _escape_open).replace('}', _escape_close)


def _unescape_braces(text: str) -> str:
    """Restore the braces escaped by _escape_braces."""
    return text.replace(_escape_open, '{').replace(_escape_close, '}')


def _strip_quotes(argument: str) -> str:
    """Remove the paired quotes around the argument."""
    if len(argument) > 1 and argument[0] in ('"', "'") and argument[-1] == argument[0]:
        return argument[1:-1]
    return argument


def _text_value(argument: str) -> str:
    """Get the text of a random argument, the content wrapped by backquote is kept as is."""
    if len(argument) > 1 and argument[0] == '`' and argument[-1] == '`':
        return _escape_braces(argument[1:-1])
    return _strip_quotes(argument)


def _split_arguments(content: str) -> list[str]:
    """Split arguments by comma, the comma inside quotes, backquotes or variables is not split."""
    arguments = []
    current = ''
    quote = ''
    depth = 0
    for char in content:
        if quote:
            current += char
            if char == quote:
                quote = ''
        elif char in ('"', "'", '`'):
            quote = char
            current += char
        elif char == '{':
            depth += 1
            current += char
        elif char == '}':
            depth = max(depth - 1, 0)
            current += char
        elif char == ',' and not depth:
            arguments.append(current.strip())
            current = ''
        else:
            current += char
    arguments.append(current.strip())

    return [argument for argument in arguments if argument]


def _page_element(argument: str) -> tuple[str, tuple[int, ...]]:
    """Get the url and the render options of a page variable.

    The render options are render time, width and height, such as {page:url,1000,1280,720}.
    """
    arguments = _split_arguments(argument)
    options = []

    # the trailing numbers are the render options, the others are a part of the url
    while len(arguments) > 1 and len(options) < len(_page_default_options) and arguments[-1].isdigit():
        options.insert(0, int(arguments.pop()))

    return (_strip_quotes(','.join(arguments)), tuple(options) + _page_default_options[len(options):])


def _random_value(content: str | None) -> str:
    """Get the replacement content for a random variable."""
    arguments = _split_arguments(content) if content else []
    numbers = [float(argument) for argument in arguments if _is_number(argument)]

    # {rand}: a random number from 0 to 100
    if not arguments:
        return generate_random_number(0, 100)
    # {rand:max}: treat as {rand:0,max}, 0 is treated as text
    if len(numbers) == len(arguments) == 1 and numbers[0] != 0:
        return generate_random_number(0, numbers[0], _decimal_places(arguments[0]))
    # {rand:min,max}: a random number from min to max
    if len(numbers) == len(arguments) == 2:
        decimal = max([_decimal_places(argument) for argument in arguments])
        return generate_random_number(min(numbers), max(numbers), decimal)

    # the rest are random texts, quoted numbers are treated as text as well
    return random.choice([_text_value(argument) for argument in arguments])


# the random variable can be nested, the nested ones are replaced from the outside in
_rand_nesting_limit = 5


def _rand_variable(text: str, start: int) -> tuple[int, str | None] | None:
    """Get the end and the argument of the random variable started at the given position.

    Returns None when the content is not a random variable.
    """
    position = start + len(_rand_prefix)
    if position >= len(text):
        return None
    if text[position] == '}':
        return position + 1, None
    if text[position] != ':':
        return None

    # the braces and the commas inside quotes are a part of the argument
    depth = 0
    quote = ''
    for index in range(position + 1, len(text)):
        char = text[index]
        if quote:
            if char == quote:
                quote = ''
        elif char in ('"', "'", '`'):
            quote = char
        elif char == '{':
            depth += 1
        elif char == '}':
            if not depth:
                return index + 1, text[position + 1:index]
            depth -= 1

    return None


def _replace_rand_variables(text: str) -> str:
    """Replace the random variables of the text, the nested ones are replaced by the next pass."""
    result = ''
    position = 0

    while True:
        start = text.find(_rand_prefix, position)
        if start < 0:
            return result + text[position:]

        variable = _rand_variable(text, start)
        if variable is None:
            result += text[position:start + 1]
            position = start + 1
            continue

        end, argument = variable
        result += text[position:start] + _random_value(argument)
        position = end


def replace_random_keywords(text: str) -> str:
    """Replace the random variables in the text, the nested ones are replaced as well."""
    for _ in range(_rand_nesting_limit):
        replaced = _replace_rand_variables(text)
        if replaced == text:
            break
        text = replaced

    return text


def _format_token(char: str, length: int, moment: datetime) -> str:
    """Format a single token of the date and time pattern."""
    if char in 'yY':
        if length > 2:
            return f'{moment.year:04d}'
        return f'{moment.year % 100:02d}' if length == 2 else str(moment.year % 100)
    if char == 'M':
        if length == 1:
            return str(moment.month)
        if length == 2:
            return f'{moment.month:02d}'
        return f'{moment.month}月' if length == 3 else _month_names[moment.month - 1]
    if char in 'dD':
        if length == 1:
            return str(moment.day)
        if length == 2:
            return f'{moment.day:02d}'
        return _weekday_names[moment.weekday()] if length == 3 else _full_weekday_names[moment.weekday()]
    if char == 'H':
        return str(moment.hour) if length == 1 else f'{moment.hour:02d}'
    if char == 'h':
        hour = moment.hour % 12 or 12
        return str(hour) if length == 1 else f'{hour:02d}'
    if char == 'm':
        return str(moment.minute) if length == 1 else f'{moment.minute:02d}'
    if char == 's':
        return str(moment.second) if length == 1 else f'{moment.second:02d}'
    if char in 'tT':
        return '上午' if moment.hour < 12 else '下午'

    return char * length


def _format_datetime(pattern: str, moment: datetime) -> str:
    """Format the datetime with the Windows style pattern."""
    result = ''
    index = 0
    while index < len(pattern):
        char = pattern[index]
        length = 1
        while index + length < len(pattern) and pattern[index + length] == char:
            length += 1

        result += _format_token(char, length, moment)
        index += length

    return result


def _datetime_value(name: str, pattern: str | None) -> str:
    """Get the replacement content for a date or time variable."""
    moment = datetime.now()

    if name == 'date':
        return _format_datetime(pattern or 'YYYY年MM月dd日', moment)

    return _format_datetime(pattern or 'HH:mm:ss', moment)


def replace_datetime_keywords(text: str) -> str:
    """Replace the date and time variables in the text."""
    return _datetime_pattern.sub(lambda match: _datetime_value(match.group(1), match.group(2)), text)


async def parse_reply_content(reply: str, data: Message) -> list[_ContentElement]:
    """Parse reply content, handling date and time variables, random variables, image path, face variable, URL variable, page variable and nickname variable.
    
    Returns:
        list: the content in appearance order, each item is a (kind, content, options) tuple,
              the kind is 'text', 'image' or 'page'
    """
    # Handle the variables without network request first, the fetched content will not be parsed again
    reply = replace_random_keywords(reply)
    reply = replace_datetime_keywords(reply)

    elements: list[_ContentElement] = []
    position = 0

    for match in _content_pattern.finditer(reply):
        url = match.group('url')
        page = match.group('page')
        path = match.group('path')
        content = ''
        element: _ContentElement | None = None

        if url is not None:
            content, image = await fetch_url_content(url)
            if not content and not image:
                # keep the variable as is when the content is unavailable
                continue
            if image:
                element = ('image', image, ())
        elif page is not None:
            page_url, options = _page_element(page)
            element = ('page', page_url, options)
        elif path is not None:
            if not os.path.exists(path):
                # keep the content as is when the path is not a real file
                continue
            element = ('image', path, ())
        else:
            faces = get_face()
            if faces:
                element = ('image', random.choice(faces), ())
            else:
                print(f'[TalkingPlugin] No face image found in: {face_dir}')

        text = reply[position:match.start()] + content
        if text.strip():
            elements.append(('text', text, ()))
        if element:
            elements.append(element)
        position = match.end()

    tail = reply[position:]
    if tail.strip():
        elements.append(('text', tail, ()))

    # Replace nickname placeholder and restore the escaped braces
    return [(kind, _unescape_braces(content.replace('{nickname}', data.nickname)), options)
            for kind, content, options in elements]


class TalkPluginInstance(AmiyaBotPluginInstance):
    def install(self):
        if not os.path.exists(face_dir) and os.path.exists(f'{curr_dir}/face'):
            shutil.copytree(f'{curr_dir}/face', face_dir)


bot = TalkPluginInstance(
    name='自定义回复',
    version='1.8',
    plugin_id='amiyabot-talking',
    plugin_type='official',
    description='可以自定义一问一答的简单对话',
    document=f'{curr_dir}/README.md',
    instruction=f'{curr_dir}/README_USE.md',
    global_config_schema=f'{curr_dir}/config_schema.json',
    global_config_default=f'{curr_dir}/config_default.yaml',
)


async def check_talk(data: Message):
    configs: list = bot.get_config('configs')

    def set_reply(_item):
        return True, 1, [_item['reply'], _item['is_at']]

    for item in configs:
        direct = item.get('direct')
        if direct:
            if direct == '仅群聊' and data.is_direct:
                continue
            if direct == '仅私聊' and not data.is_direct:
                continue

        if item['keyword_type'] == '包含关键词':
            if item['keyword'] in data.text:
                return set_reply(item)
        if item['keyword_type'] == '等于关键词':
            if item['keyword'] == data.text:
                return set_reply(item)
        if item['keyword_type'] == '正则匹配':
            if re.search(re.compile(item['keyword']), data.text):
                return set_reply(item)


@bot.on_message(verify=check_talk, check_prefix=False, allow_direct=True)
async def _(data: Message):
    reply: str = data.verify.keypoint[0]
    is_at: bool = data.verify.keypoint[1]

    if os.path.exists(reply):
        return Chain(data, at=is_at).image(reply)

    elements = await parse_reply_content(reply, data)

    chain = Chain(data, at=is_at)
    for kind, content, options in elements:
        if kind == 'text':
            chain = chain.text(content)
        elif kind == 'image':
            chain = chain.image(content)
        else:
            render_time, width, height = options
            chain = chain.html(content, is_template=False,
                               render_time=render_time, width=width, height=height)

    return chain
