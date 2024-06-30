import asyncio
import functools
import json
from typing import Any, Dict, List, Optional, Union

from core import AmiyaBotPluginInstance, Requirement
from core.plugins.customPluginInstance.amiyaBotPluginInstance import CONFIG_TYPE, DYNAMIC_CONFIG_TYPE

from ..common.blm_types import BLMAdapter, BLMFunctionCall
from ..common.database import AmiyaBotBLMLibraryTokenConsumeModel, AmiyaBotBLMLibraryMetaStorageModel

from ..chat_gpt.chat_gpt_adapter import ChatGPTAdapter

from ..ernie.ernie_adapter import ERNIEAdapter

from ..ernie.qianfan_adapter import QianFanAdapter

from .extract_json import extract_json

from ..functions.core import parse_docstring


class BLMLibraryPluginInstance(AmiyaBotPluginInstance, BLMAdapter):
    def __init__(
        self,
        name: str,
        version: str,
        plugin_id: str,
        plugin_type: str = None,
        description: str = None,
        document: str = None,
        priority: int = 1,
        instruction: str = None,
        requirements: Union[List[Requirement], None] = None,
        channel_config_default: CONFIG_TYPE = None,
        channel_config_schema: DYNAMIC_CONFIG_TYPE = None,
        global_config_default: CONFIG_TYPE = None,
        global_config_schema: DYNAMIC_CONFIG_TYPE = None,
        deprecated_config_delete_days: int = 7,
    ):
        super().__init__(
            name,
            version,
            plugin_id,
            plugin_type,
            description,
            document,
            priority,
            instruction,
            requirements,
            channel_config_default,
            channel_config_schema,
            global_config_default,
            global_config_schema,
            deprecated_config_delete_days,
        )
        self.adapters: List[BLMAdapter] = []
        self.model_map: Dict[str, BLMAdapter] = {}
        self.assistant_map: Dict[str, BLMAdapter] = {}
        self.thread_map: Dict[str, BLMAdapter] = {}
        self.functions_registry: Dict[str, BLMFunctionCall] = {}

    def install(self):
        AmiyaBotBLMLibraryTokenConsumeModel.create_table(safe=True)
        AmiyaBotBLMLibraryMetaStorageModel.create_table(safe=True)

        # 读取配置文件来确定各个模型是不是启用
        chatgpt_config = self.get_config("ChatGPT")
        if chatgpt_config and chatgpt_config["enable"]:
            self.adapters.append(ChatGPTAdapter(self))
        ernie_config = self.get_config("ERNIE")
        if ernie_config and ernie_config["enable"]:
            self.adapters.append(ERNIEAdapter(self))
        qianfan_config = self.get_config("QianFan")
        if qianfan_config and qianfan_config["enable"]:
            self.adapters.append(QianFanAdapter(self))

        self.model_list()

    def register_blm_function(self, func) -> callable:
        """
        装饰器：注册函数以供AI调用。
        如果一个函数含有类似本函数的doc格式，则该装饰器会自动解析其docstring并生成BLMFunctionCall。
        该BLMFunctionCall会被注册到BLMPluginInstance的amiyabot_function_calls中。
        调用ChatFlow或AssistantFlow时，可以用 functions=blm_instance.amiyabot_function_calls 来使其感知到这些函数。

        :param func: 在这里描述参数的功能，AI会以纯文本形式来理解并尝试提供参数。AI并不一定会严格按照参数类型来传递数据，此处你需要做防御性处理。
        :type func: callable

        :return: 在这里描述函数返回值的含义。AI实际上是将该返回值json化后当做文本解析，因此返回值的格式并不重要。他的内容（包括字段名）很重要。
        :rtype: callable

        """

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # 解析函数的docstring来生成JSON schema
        schema = parse_docstring(func)

        # 在全局集合中保存函数引用和其JSON schema
        func_call = BLMFunctionCall()
        func_call.function_name = func.__name__
        func_call.function_schema = schema
        func_call.function = func
        self.functions_registry[func.__name__] = func_call

        return wrapper

    def model_list(self) -> List[dict]:
        # 返回的同时，构造ModelMap，方便后续的模型调用
        model_list = []
        for adapter in self.adapters:
            adapter_models = adapter.model_list()
            model_list.extend(adapter_models)
            for model in adapter_models:
                self.model_map[model["model_name"]] = adapter
        return model_list

    def get_model(self, model_name: str) -> dict:
        model_dict_list = self.model_list()
        for model_dict in model_dict_list:
            if model_dict["model_name"] == model_name:
                return model_dict

    def get_model_quota_left(self, model_name: str) -> int:
        adapter = self.model_map[model_name]
        if not adapter:
            return 0
        return adapter.get_model_quota_left(model_name)

    def get_default_model(self) -> dict:
        default_model = self.get_config("default_model")
        if default_model:
            return self.get_model(default_model)
        else:
            return None

    # 以下是对外提供的接口, 通过model_name来确定调用哪个模型

    async def completion_flow(
        self,
        prompt: Union[str, List[str]],
        model: Optional[Union[str, dict]] = None,
        context_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> Optional[str]:
        if model is None:
            model = self.get_default_model()

        if isinstance(model, dict):
            model = model["model_name"]

        adapter = self.model_map[model]
        if not adapter:
            return None
        return await adapter.completion_flow(prompt, model, context_id, channel_id)

    async def chat_flow(
        self,
        prompt: Union[Union[str, dict], List[Union[str, dict]]],
        model: Optional[Union[str, dict]] = None,
        context_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        functions: Optional[List[BLMFunctionCall]] = None,
        json_mode: Optional[bool] = False,
    ) -> Optional[str]:
        if model is None:
            model = self.get_default_model()

        if isinstance(model, dict):
            model = model["model_name"]

        adapter = self.model_map[model]
        if not adapter:
            return None
        return await adapter.chat_flow(prompt, model, context_id, channel_id, functions, json_mode)

    def assistant_list(self) -> List[dict]:
        # 返回的同时，构造ModelMap，方便后续的模型调用
        assistant_list = []
        for adapter in self.adapters:
            adapter_models = adapter.assistant_list()
            assistant_list.extend(adapter_models)
            for assistant in adapter_models:
                self.assistant_map[assistant["id"]] = adapter
        return assistant_list

    async def assistant_thread_create(self, assistant_id: str):
        self.assistant_list()

        if assistant_id not in self.assistant_map.keys():
            return

        adapter = self.assistant_map[assistant_id]
        if not adapter:
            return None
        thread_id = await adapter.assistant_thread_create(assistant_id)
        self.thread_map[thread_id] = adapter
        return thread_id

    async def assistant_thread_touch(self, thread_id: str, assistant_id: str):
        self.assistant_list()

        if assistant_id not in self.assistant_map.keys():
            return

        adapter = self.assistant_map[assistant_id]
        if not adapter:
            return None
        return await adapter.assistant_thread_touch(thread_id, assistant_id)

    async def assistant_run(
        self,
        thread_id: str,
        assistant_id: str,
        messages: Union[dict, List[dict]],
        channel_id: Optional[str] = None,
    ) -> Optional[str]:
        self.assistant_list()
        if assistant_id not in self.assistant_map.keys():
            return

        adapter = self.assistant_map[assistant_id]
        if not adapter:
            return None

        return await adapter.assistant_run(thread_id, assistant_id, messages, channel_id)

    @property
    def amiyabot_function_calls(self) -> List[BLMFunctionCall]:

        # 从functions_registry扁平化返回数据
        function_calls = []
        for func_name, func in self.functions_registry.items():
            function_calls.append(func)

        return function_calls

    def extract_json(self, string: str) -> List[Union[Dict[str, Any], List[Any]]]:
        return extract_json(string)


# 测试用main
