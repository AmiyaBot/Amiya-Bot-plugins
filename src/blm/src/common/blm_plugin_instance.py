import asyncio
import json
from typing import Any, Dict, List, Optional, Union

from core import AmiyaBotPluginInstance,Requirement
from core.plugins.customPluginInstance.amiyaBotPluginInstance import CONFIG_TYPE,DYNAMIC_CONFIG_TYPE

from ..common.blm_types import BLMAdapter, BLMFunctionCall
from ..chat_gpt.chat_gpt_adapter import ChatGPTAdapter 
from ..ernie.ernie_adapter import ERNIEAdapter 
from ..common.database import AmiyaBotBLMLibraryTokenConsumeModel,AmiyaBotBLMLibraryMetaStorageModel

from .extract_json import extract_json

class BLMLibraryPluginInstance(AmiyaBotPluginInstance,BLMAdapter):
    def __init__(self, name: str, 
                 version: str, 
                 plugin_id: str, 
                 plugin_type: str = None, 
                 description: str = None, 
                 document: str = None, 
                 priority: int = 1, 
                 instruction: str = None, 
                 requirements: Union[List[Requirement],None] = None,
                 channel_config_default: CONFIG_TYPE = None,
                 channel_config_schema: DYNAMIC_CONFIG_TYPE = None, 
                 global_config_default: CONFIG_TYPE = None, 
                 global_config_schema: DYNAMIC_CONFIG_TYPE = None, 
                 deprecated_config_delete_days: int = 7):
        super().__init__(name, version, plugin_id, plugin_type, description, document, priority, instruction, requirements, channel_config_default, channel_config_schema, global_config_default, global_config_schema, deprecated_config_delete_days)
        self.adapters: List[BLMAdapter] = []
        self.model_map: Dict[str,BLMAdapter] = {}

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
        
        self.model_list()

    def model_list(self) -> List[dict]:  
        # 返回的同时，构造ModelMap，方便后续的模型调用
        model_list = []
        for adapter in self.adapters:
            adapter_models = adapter.model_list()
            model_list.extend(adapter_models)
            for model in adapter_models:
                self.model_map[model["model_name"]] = adapter
        return model_list
    
    def get_model(self,model_name:str)->dict:
        model_dict_list = self.model_list()
        for model_dict in model_dict_list:
            if model_dict["model_name"] == model_name:
                return model_dict

    def get_model_quota_left(self,model_name:str) -> int:
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
            
        if isinstance(model,dict):
            model = model["model_name"]

        adapter = self.model_map[model]
        if not adapter:
            return None
        return await adapter.completion_flow(prompt, model, context_id, channel_id)

    async def chat_flow(  
        self,  
        prompt: Union[str, List[str]],  
        model: Optional[Union[str, dict]] = None,
        context_id: Optional[str] = None,  
        channel_id: Optional[str] = None,
        functions: Optional[List[BLMFunctionCall]] = None,  
    ) -> Optional[str]:
        if model is None:
            model = self.get_default_model()

        if isinstance(model,dict):
            model = model["model_name"]
            
        adapter = self.model_map[model]
        if not adapter:
            return None
        return await adapter.chat_flow(prompt, model, context_id, channel_id, functions)

    async def assistant_flow(  
        self,  
        assistant: str,  
        prompt: Union[str, List[str]],  
        context_id: Optional[str] = None,        
        channel_id: Optional[str] = None,
    ) -> Optional[str]:
        if model is None:
            model = self.get_default_model()

        if isinstance(model,dict):
            model = model["model_name"]

        adapter = self.model_map[assistant]
        if not adapter:
            return None
        return await adapter.assistant_flow(assistant, prompt, context_id, channel_id)
    
    async def assistant_create(  
        self,  
        name: str,  
        instructions: str,  
        model: Optional[Union[str, dict]]= None,
        functions: Optional[List[BLMFunctionCall]] = None,  
        code_interpreter: bool = False,  
        retrieval: Optional[List[str]] = None,  
    ) -> str:
        
        if model is None:
            model = self.get_default_model()
        if isinstance(model,dict):
            model = model["model_name"]
            
        adapter = self.model_map[model]
        if not adapter:
            return None
        return await adapter.assistant_create(name, instructions, model, functions, code_interpreter, retrieval)
    
    def extract_json(self, string: str) -> List[Union[Dict[str, Any], List[Any]]]:
        return extract_json(string)
    
# 测试用main
