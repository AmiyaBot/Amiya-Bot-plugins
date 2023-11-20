
import json
from typing import Any, Dict, List, Union


def extract_json(string: str) -> List[Union[Dict[str, Any], List[Any]]]:
    json_strings = []
    json_objects = []
    
    # We need additional variables to handle arrays
    open_curly_brackets = 0
    open_square_brackets = 0
    start_index = None

    for index, char in enumerate(string):
        if char == '{':
            open_curly_brackets += 1
        elif char == '}':
            open_curly_brackets -= 1
        elif char == '[':
            open_square_brackets += 1
        elif char == ']':
            open_square_brackets -= 1
        else:
            continue

        # Check when to start capturing the string
        if (open_curly_brackets == 1 and open_square_brackets == 0 and start_index is None) or \
        (open_square_brackets == 1 and open_curly_brackets == 0 and start_index is None):
            start_index = index

        # Check when to stop capturing the string
        if (open_curly_brackets == 0 and open_square_brackets == 0 and start_index is not None):
            json_strings.append(string[start_index : index + 1])
            start_index = None

    for json_str in json_strings:
        try:
            json_object = json.loads(json_str)
            json_objects.append(json_object)
        except json.JSONDecodeError as e:
            pass
            

    # 如果是一个数组的数组,就拆出来
    if len(json_objects) == 1:
        if isinstance(json_objects[0],list):
            return json_objects[0]

    return json_objects

if __name__ == "__main__":
    # 直接调用ExtractJson

    str_to_test = """
[
{"prompt":"a character with pink hair and green eyes, magical atmosphere, fantasy setting, (flowing hair:1.3), (glowing eyes:1.2), (soft colors:1.5), dream-like, ethereal, (pastel colors:1.3)","style":"Anime"},

{"prompt":"portrait of a person with pink hair and green eyes, vibrant atmosphere, urban setting, (long hair:1.3), (intense gaze:1.2), (neon lights:1.5), modern, neon aesthetic, (bold colors:1.3)","style":"Photographic"},

{"prompt":"a girl with pink hair and green eyes, nature-inspired, tranquil atmosphere, forest setting, (flowing hair:1.3), (gentle gaze:1.2), (soft tones:1.5), whimsical, enchanting, (natural colors:1.3)","style":"Watercolor"},

{"prompt":"a character with pink hair and green eyes, futuristic atmosphere, sci-fi setting, (short hair:1.3), (intense look:1.2), (metallic elements:1.5), cyberpunk, futuristic aesthetic, (cool colors:1.3)","style":"3D_Model"}
]
"""

    print(extract_json(str_to_test))