import json
from typing import Any, Dict, List, Union


def extract_json(string: str) -> List[Union[Dict[str, Any], List[Any]]]:

    if string is None:
        return None

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
        if (open_curly_brackets == 1 and open_square_brackets == 0 and start_index is None) or (
            open_square_brackets == 1 and open_curly_brackets == 0 and start_index is None
        ):
            start_index = index

        # Check when to stop capturing the string
        if open_curly_brackets == 0 and open_square_brackets == 0 and start_index is not None:
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
        if isinstance(json_objects[0], list):
            return json_objects[0]

    return json_objects


if __name__ == "__main__":
    # 直接调用ExtractJson

    str_to_test = """
```json
[
    {
        "reply": "博士，这张图片上画了一个很可爱的人物，她看起来很友好和欢快。不论遇到什么困难，我们都应该保持这份乐观的心态，这样对罗德岛的每一位成员都是一种激励。",
        "mental": "努力传达正能量，同时暗示维持士气的重要性。",
        "activity": "注视着图片，想象着背后可能的积极故事。",
        "role": "阿米娅",
        "corelation_on_topic": 1.0,
        "corelation_on_conversation": 1.0
    }
]
```
"""

    print(extract_json(str_to_test))
