import os
from typing import Any, Callable, Dict, List, Optional, Union

curr_dir = os.path.dirname(__file__)

dir_path = f"{curr_dir}/../../../../resource/blm_library/cache"
dir_path = os.path.abspath(dir_path)
if not os.path.exists(dir_path):
    os.makedirs(dir_path)


class BLMFunctionCall:
    functon_name: str
    function_schema: Union[str, dict]
    function: Callable[..., Any]


class BLMAdapter:
    def __init__(self):
        self.cache_dir = dir_path

    async def completion_flow(
        self,
        prompt: Union[str, List[str]],
        model: Optional[Union[str, dict]] = None,
        context_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> Optional[str]:
        ...

    async def chat_flow(
        self,
        prompt: Union[Union[str, dict], List[Union[str, dict]]],
        model: Optional[Union[str, dict]] = None,
        context_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        functions: Optional[List[BLMFunctionCall]] = None,
        json_mode: Optional[bool] = False,
    ) -> Optional[str]:
        ...

    async def assistant_flow(
        self,
        assistant: str,
        prompt: Union[str, List[str]],
        context_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> Optional[str]:
        ...

    async def assistant_create(
        self,
        name: str,
        instructions: str,
        model: Optional[Union[str, dict]] = None,
        functions: Optional[List[BLMFunctionCall]] = None,
        code_interpreter: bool = False,
        retrieval: Optional[List[str]] = None,
    ) -> str:
        ...

    def model_list(self) -> List[dict]:
        ...

    def get_model(self, model_name: str) -> dict:
        model_dict_list = self.model_list()
        for model_dict in model_dict_list:
            if model_dict["model_name"] == model_name:
                return model_dict

    def get_model_quota_left(self, model_name: str) -> int:
        ...

    def get_default_model(self) -> dict:
        ...

    def extract_json(self, string: str) -> List[Union[Dict[str, Any], List[Any]]]:
        ...
