import asyncio
from datetime import datetime
import json
import time
import traceback
from typing import List, Optional, Union

from openai import AsyncOpenAI, BadRequestError, RateLimitError

from core import AmiyaBotPluginInstance
from core.util.threadPool import run_in_thread_pool

from amiyabot.log import LoggerManager
from amiyabot.network.httpRequests import http_requests

from ..common.blm_types import BLMAdapter, BLMFunctionCall
from ..common.database import AmiyaBotBLMLibraryMetaStorageModel, AmiyaBotBLMLibraryTokenConsumeModel
from ..common.quota_check import QuotaController

from ..common.extract_json import extract_json

logger = LoggerManager('DEEPSEEK')


class DeepSeekAdapter(BLMAdapter):
    def __init__(self, plugin):
        super().__init__()
        self.plugin: AmiyaBotPluginInstance = plugin
        self.context_holder = {}
        self.quota_checker : QuotaController = QuotaController(logger,plugin)

    def debug_log(self, msg):
        show_log = self.plugin.get_config("show_log")
        if show_log == True:
            logger.info(f'{msg}')

    def get_config(self, key):
        model_config = self.plugin.get_config("DeepSeek")
        if model_config and model_config["enable"] and key in model_config:
            return model_config[key]
        return None

    def get_model_quota_left(self, model_name: str) -> int:
        # 根据__quota_check来计算
        return self.quota_checker.check(peek=True)

    def model_list(self) -> List[dict]:
        model_list_response = [
            {
                "display_name": "DeepSeek-V3",
                "model_name": "deepseek-chat",
                "type": "low-cost",
                "max_token": 4000,
                "max-token": 4000,
                "supported_feature": ["completion_flow", "chat_flow", "json_mode"],
            },
            {
                "display_name": "DeepSeek-R1",
                "model_name": "deepseek-reasoner",
                "type": "low-cost",
                "max_token": 4000,
                "max-token": 4000,
                "supported_feature": ["completion_flow", "chat_flow"],
            }
        ]
        return model_list_response

    async def chat_flow(
        self,
        prompt: Union[Union[str, dict], List[Union[str, dict]]],
        model: Optional[Union[str, dict]] = None,
        context_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        functions: Optional[List[BLMFunctionCall]] = None,
        json_mode: Optional[bool] = False,
    ) -> Optional[str]:

        # self.debug_log(f'chat_flow received: {prompt} {model} {context_id} {channel_id} {functions}')
        self.debug_log(f'chat_flow received prompt: {prompt}')
        self.debug_log(f'chat_flow received model: {model}')
        self.debug_log(f'chat_flow received context_id: {context_id}')
        self.debug_log(f'chat_flow received channel_id: {channel_id}')
        self.debug_log(f'chat_flow received functions: {functions}')
        self.debug_log(f'chat_flow received json_mode: {json_mode}')

        model_info = self.get_model(model)
        if model_info is None:
            self.debug_log('model not found')
            return None

        self.debug_log(f'model info: {model_info}')

        if not model_info["supported_feature"].__contains__("chat_flow"):
            self.debug_log('model not supported chat_flow')
            return None
        if model_info["type"] == "high-cost":
            quota = self.__quota_check()
            if quota <= 0:
                self.debug_log('quota not enough')
                return None

        client = AsyncOpenAI(api_key=self.get_config('api_key'), base_url="https://api.deepseek.com")

        self.debug_log(f"model: {model_info}")

        if isinstance(prompt, str):
            prompt = [prompt]

        if isinstance(prompt, dict):
            prompt = [prompt]

        # prompt = [{"role": "user", "content": command} for command in prompt]
        for i in range(len(prompt)):
            if isinstance(prompt[i], str):
                prompt[i] = {"role": "user", "content": [{"type": "text", "text": prompt[i]}]}
            elif isinstance(prompt[i], dict):
                if "type" not in prompt[i]:
                    raise ValueError("无效的prompt")
                if prompt[i]["type"] == "text":
                    prompt[i] = {"role": "user", "content": [{"type": "text", "text": prompt[i]["text"]}]}
                elif prompt[i]["type"] == "image_url":
                    prompt[i] = {
                        "role": "user",
                        "content": [{"type": "image_url", "image_url": {"url": prompt[i]["url"]}}],
                    }
                else:
                    raise ValueError("无效的prompt")
            else:
                raise ValueError("无效的prompt")

        if context_id is not None:
            if context_id not in self.context_holder:
                self.context_holder[context_id] = []
            prompt = self.context_holder[context_id] + prompt

        def prompt_filter(item):
            if not model_info["supported_feature"].__contains__("vision"):
                if isinstance(item["content"], dict) and item["content"][0]["type"] == "image_url":
                    self.debug_log(f"image_url not supported in {model_info['model_name']}")
                    return False          
            return True

        prompt = list(filter(prompt_filter, prompt))

        exec_prompt = [] + prompt

        if not model_info["supported_feature"].__contains__("vision"):
            # 扁平化prompt的content为str
            for i in range(len(exec_prompt)):
                if isinstance(exec_prompt[i]["content"], list):
                    exec_prompt[i]["content"] = exec_prompt[i]["content"][0]["text"]
                elif isinstance(exec_prompt[i]["content"], dict):
                    exec_prompt[i]["content"] = exec_prompt[i]["content"]["text"]
                elif isinstance(exec_prompt[i]["content"], str):
                    pass

        if json_mode:
            if not model_info["supported_feature"].__contains__("json_mode"):
                # 非原生支持json_mode时需要拼接prompt
                exec_prompt.append(
                    {
                        "role": "assistant",
                        "content": "(Important!!)Please output the result in pure json format. (重要!!) 请以纯json字符串格式输出结果。",
                    }
                )

        # deepseek-reasoner does not support successive user or assistant message
        if model_info["model_name"] == "deepseek-reasoner":
            # 连续的user或者assistant消息会被合并
            formated_exec_prompt = []
            for i in range(len(exec_prompt)):
                if i == 0:
                    formated_exec_prompt.append(exec_prompt[i])
                else:
                    if exec_prompt[i]["role"] == exec_prompt[i - 1]["role"]:
                        formated_exec_prompt[-1]["content"] += "\n" + exec_prompt[i]["content"]
                    else:
                        formated_exec_prompt.append(exec_prompt[i])
            
            exec_prompt = formated_exec_prompt

        try:
            call_param = {}
            call_param["model"] = model_info["model_name"]
            call_param["messages"] = exec_prompt

            if json_mode:
                if model_info["supported_feature"].__contains__("json_mode"):
                    call_param["response_format"] = {"type": "json_object"}

            if (
                model_info["supported_feature"].__contains__("function_call")
                and functions is not None
                and len(functions) > 0
            ):
                tools = []
                for function in functions:
                    tools.append({"type": "function", "function": function.function_schema})
                call_param["tools"] = tools
                # tool_choice="auto",
                call_param["tool_choice"] = "auto"
                self.debug_log(f"append tools: {tools}")

            while True:
                completions = await client.chat.completions.create(**call_param)

                response_message = completions.choices[0].message
                tool_calls = response_message.tool_calls

                if tool_calls is not None and len(tool_calls) > 0:
                    self.debug_log(f"tool_calls: {tool_calls}")

                    call_param["messages"].append(response_message)

                    for tool_call in tool_calls:
                        function_name = tool_call.function.name
                        func_call = next(
                            (func for func in functions if func.function_schema["name"] == function_name), None
                        )
                        func_response = None
                        if func_call is not None:
                            function_args = json.loads(tool_call.function.arguments)
                            # 如果func_call是async
                            if asyncio.iscoroutinefunction(func_call.function):
                                func_response = await func_call.function(**function_args)
                            else:
                                func_response = func_call.function(**function_args)

                            if func_response is not None:
                                if not isinstance(func_response, str):
                                    func_response = json.dumps(func_response)
                        else:
                            self.debug_log(f"function {function_name} not found")

                        if func_response is not None:
                            self.debug_log(f"function response: {func_response}")
                            call_param["messages"].append(
                                {
                                    "tool_call_id": tool_call.id,
                                    "role": "tool",
                                    "name": function_name,
                                    "content": func_response,
                                }
                            )
                        else:
                            self.debug_log(
                                f"function response: 参数错误，请更换参数后重试。Invalid Parameters。Please change your parameter and try again."
                            )
                            call_param["messages"].append(
                                {
                                    "tool_call_id": tool_call.id,
                                    "role": "tool",
                                    "name": function_name,
                                    "content": "参数错误，请更换参数后重试。Invalid Parameters。Please change your parameter and try again.",
                                }
                            )

                    self.debug_log(f"Resend request。")
                    continue

                break

        except RateLimitError as e:
            self.debug_log(f"RateLimitError: {e}")
            self.debug_log(f"Exception traceback:\n{traceback.format_exc()}")
            self.debug_log(f'DEEPSEEK Raw Request: \n{exec_prompt}')
            return None
        except BadRequestError as e:
            self.debug_log(f"BadRequestError: {e}")
            self.debug_log(f"Exception traceback:\n{traceback.format_exc()}")
            self.debug_log(f'DEEPSEEK Raw Request: \n{exec_prompt}')
            return None
        except Exception as e:
            self.debug_log(f"Exception: {e}")
            self.debug_log(f"Exception traceback:\n{traceback.format_exc()}")
            self.debug_log(f'DEEPSEEK Raw Request: \n{exec_prompt}')
            return None

        text: str = completions.choices[0].message.content
        # 判断是否有reasoning_content这个属性
        reason_text : str= None
        if hasattr(completions.choices[0].message, "reasoning_content"):
            reason_text = completions.choices[0].message.reasoning_content
            self.debug_log(f'Reasoning Content{reason_text}')
        else:
            self.debug_log('No Reasoning Content')
        # role: str = completions.choices[0].message.role

        self.debug_log(f'{model_info["model_name"]} Raw: \n{exec_prompt}\n------------------------\n{completions.choices[0].message}')

        id = completions.id
        usage = completions.usage

        if channel_id is None:
            channel_id = "-"

        AmiyaBotBLMLibraryTokenConsumeModel.create(
            channel_id=channel_id,
            model_name=model_info["model_name"],
            exec_id=id,
            prompt_tokens=int(usage.prompt_tokens),
            completion_tokens=int(usage.completion_tokens),
            total_tokens=int(usage.total_tokens),
            exec_time=datetime.now(),
        )

        if context_id is not None:
            prompt.append({"role": "assistant", "content": text})
            self.context_holder[context_id] = prompt

        ret_str = f"{text}".strip()

        # 确认模型是否支持json_mode
        if json_mode:
            self.debug_log(f"json_mode enabled in {model_info['model_name']}")

            if not model_info["supported_feature"].__contains__("json_mode"):
                self.debug_log(f"json_mode not supported in {model_info['model_name']}, extracting from:\n{text}")
                json_obj = extract_json(ret_str)
                if json_obj is not None:
                    ret_str = json.dumps(json_obj)
                else:
                    ret_str = None
            
            if self.get_config("deep_think") == True:
                self.debug_log(f'deep_think enabled: {reason_text}')
                if reason_text is not None:
                    ret_str["reasoning_content"] = reason_text

            return ret_str
        else:
            if self.get_config("deep_think") == True:
                self.debug_log(f'deep_think enabled: {reason_text}')
                if reason_text is not None:                
                    ret_str = f"({reason_text.strip()})\n{ret_str}"

            return ret_str

