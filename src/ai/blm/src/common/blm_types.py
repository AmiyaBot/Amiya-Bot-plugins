import os
from typing import Any, Callable, Dict, List, Optional, Union

curr_dir = os.path.dirname(__file__)

dir_path = f"{curr_dir}/../../../../resource/blm_library/cache"
dir_path = os.path.abspath(dir_path)
if not os.path.exists(dir_path):
    os.makedirs(dir_path)


class BLMFunctionCall:
    function_name: str
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
    ) -> Optional[str]: ...

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

    def assistant_list(self) -> List[dict]:
        ...

    def get_assistant(self, assistant_id: str) -> dict:
        ...

    async def assistant_thread_touch(
            self,
            thread_id: str,
            assistant_id: str
    ):
        ...

    async def assistant_thread_create(
            self,
            assistant_id: str      
        ):
        ...
    
    async def assistant_run(
        self,
        thread_id: str,
        assistant_id: str,
        messages: Union[dict, List[dict]],
        channel_id: Optional[str] = None,
        json_mode: Optional[bool] = False,
    ) -> Optional[str]: ...

    def model_list(self) -> List[dict]: ...

    def get_model(self, model_name: str) -> dict:
        model_dict_list = self.model_list()
        for model_dict in model_dict_list:
            if model_dict["model_name"] == model_name:
                return model_dict

    def get_model_quota_left(self, model_name: str) -> int: ...

    def get_default_model(self) -> dict: ...

    @property
    def amiyabot_function_calls(self) -> List[BLMFunctionCall]: ...
