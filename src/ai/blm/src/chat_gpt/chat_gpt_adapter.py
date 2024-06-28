import asyncio
import json
import time
import traceback

from datetime import datetime

from typing import List, Optional, Union

from core import AmiyaBotPluginInstance, log

from amiyabot.log import LoggerManager

from ..common.database import AmiyaBotBLMLibraryTokenConsumeModel
from ..common.blm_types import BLMAdapter, BLMFunctionCall
from ..common.extract_json import extract_json

enabled = False
try:
    import httpx
    from openai import AsyncOpenAI, BadRequestError, RateLimitError

    enabled = True
    log.info('OpenAI初始化完成')
except ModuleNotFoundError as e:
    log.info(f'未安装python库openai或版本低于1.0.0或未安装httpx，无法使用ChatGPT模型，错误消息：{e.msg}\n{traceback.format_exc()}')
    enabled = False

logger = LoggerManager('BLM-ChatGPT')


class ChatGPTAdapter(BLMAdapter):
    def __init__(self, plugin):
        super().__init__()
        self.plugin: AmiyaBotPluginInstance = plugin
        self.context_holder = {}
        self.query_times = []

    def debug_log(self, msg):
        show_log = self.plugin.get_config("show_log")
        if show_log == True:
            logger.info(f'{msg}')

    def get_config(self, key):
        chatgpt_config = self.plugin.get_config("ChatGPT")
        if chatgpt_config and chatgpt_config["enable"] and key in chatgpt_config:
            return chatgpt_config[key]
        return None

    def __quota_check(self, peek: bool = False) -> int:
        query_per_hour = self.get_config('high_cost_quota')

        if query_per_hour is None or query_per_hour <= 0:
            return 100000

        current_time = time.time()
        hour_ago = current_time - 3600  # 3600秒代表一小时

        # 移除一小时前的查询记录
        self.query_times = [t for t in self.query_times if t > hour_ago]

        current_query_times = len(self.query_times)

        if current_query_times < query_per_hour:
            # 如果过去一小时内的查询次数小于限制，则允许查询
            if not peek:
                self.query_times.append(current_time)
            self.debug_log(f"quota check success, query times: {current_query_times} > {query_per_hour}")
            return query_per_hour - current_query_times
        else:
            # 否则拒绝查询
            self.debug_log(f"quota check failed, query times: {current_query_times} >= {query_per_hour}")
            return 0

    def get_model_quota_left(self, model_name: str) -> int:
        model_info = self.get_model(model_name)
        if model_info is None:
            return 0
        if model_info["type"] == "low-cost":
            return 100000000
        if model_info["type"] == "high-cost":
            # 根据__quota_check来计算
            return self.__quota_check(peek=True)
        return 0

    def model_list(self) -> List[dict]:
        model_list_response = [
            {
                "model_name": "gpt-3.5-turbo",
                "type": "low-cost",
                "max_token": 2000,                    
                "max-token": 2000,
                "supported_feature": ["completion_flow", "chat_flow", "assistant_flow", "function_call"],
            },
        ]
        disable_high_cost = self.get_config("disable_high_cost")
        # self.debug_log(f"disable_high_cost: {disable_high_cost}")
        if disable_high_cost != True:
            model_list_response.append(
                {
                    "model_name": "gpt-4",
                    "type": "high-cost",
                    "max_token": 4000,                    
                    "max-token": 4000,
                    "supported_feature": ["completion_flow", "chat_flow", "assistant_flow", "function_call"],
                }
            )
            model_list_response.append(
                {
                    "model_name": "gpt-4-1106-preview",
                    "type": "high-cost",
                    "max_token": 128000,                    
                    "max-token": 128000,
                    "supported_feature": ["completion_flow", "chat_flow", "assistant_flow", "function_call","json_mode"],
                }
            )
            model_list_response.append(
                {
                    "model_name": "gpt-4-vision-preview",
                    "type": "high-cost",
                    "max_token": 4096,                    
                    "max-token": 4096,
                    "supported_feature": ["completion_flow", "chat_flow", "assistant_flow","vision"],
                }
            )
            model_list_response.append(
                {
                    "model_name": "gpt-4-turbo",
                    "type": "high-cost",
                    "max_token": 128000,                    
                    "max-token": 128000,
                    "supported_feature": ["completion_flow", "chat_flow", "assistant_flow", "function_call","vision","json_mode"],
                }
            )
            model_list_response.append(
                {
                    "model_name": "gpt-4o",
                    "type": "high-cost",
                    "max_token": 128000,                    
                    "max-token": 128000,
                    "supported_feature": ["completion_flow", "chat_flow", "assistant_flow", "function_call","vision","json_mode"],
                }
            )
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
        if not enabled:
            return None

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
                self.debug_log(f"quota check failed, fallback to gpt-3.5-turbo {quota}")
                model_info = self.get_model("gpt-3.5-turbo")

        proxy = self.get_config('proxy')
        async_httpx_client = None
        if proxy is not None and proxy != "":
            if proxy.startswith("https://"):
                proxies = {"http://": proxy, "https://": proxy}
                async_httpx_client = httpx.AsyncClient(proxies=proxies)
            elif proxy.startswith("http://"):
                proxies = {"http://": proxy}
                async_httpx_client = httpx.AsyncClient(proxies=proxies)
            else:
                raise ValueError("无效的代理URL")

        base_url = self.get_config('url')
        client = AsyncOpenAI(api_key=self.get_config('api_key'), base_url=base_url, http_client=async_httpx_client)

        self.debug_log(f"url: {base_url} proxy: {proxy} model: {model_info}")

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
                    prompt[i] = {"role": "user", "content": [{"type": "image_url", "image_url":{"url": prompt[i]["url"]}}]}
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
                exec_prompt.append({"role": "assistant", "content": "(Important!!)Please output the result in pure json format. (重要!!) 请以纯json字符串格式输出结果。"})

        # combine text message for debuging
        combined_message = ""
        for item in exec_prompt:
            if isinstance(item["content"] , str):
                combined_message += item["content"]+"\n"
            else:
                if item["content"][0]["type"] == "text":
                    combined_message += item["content"][0]["text"]+"\n"
                elif item["content"][0]["type"] == "image_url":
                    combined_message += f'<img src="{item["content"][0]["image_url"]["url"]}"/>'
        
        try:
            call_param = {}
            call_param["model"]=model_info["model_name"]
            call_param["messages"]=exec_prompt

            if json_mode:
                if model_info["supported_feature"].__contains__("json_mode"):
                    call_param["response_format"] = {"type": "json_object"}

            if model_info["model_name"] == "gpt-4-vision-preview":
                # 特别的，为vision指定一个4096的max_tokens
                call_param["max_tokens"] = 4096
            
            if  model_info["supported_feature"].__contains__("function_call") and functions is not None and len(functions) > 0:
                # tools = [
                #     {
                #         "type": "function",
                #         "function": {
                #             "name": "get_current_weather",
                #             "description": "Get the current weather in a given location",
                #             "parameters": {
                #                 "type": "object",
                #                 "properties": {
                #                     "location": {
                #                         "type": "string",
                #                         "description": "The city and state, e.g. San Francisco, CA",
                #                     },
                #                     "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                #                 },
                #                 "required": ["location"],
                #             },
                #         },
                #     }
                # ]
                tools = []
                for function in functions:
                    tools.append({
                        "type": "function",
                        "function": function.function_schema
                    })
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
                        func_call = next((func for func in functions if func.function_schema["name"] == function_name), None)
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
                            self.debug_log(f"function response: 参数错误，请更换参数后重试。Invalid Parameters。Please change your parameter and try again.")
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
            self.debug_log(f'Chatgpt Raw: \n{combined_message}')
            return None
        except BadRequestError as e:
            self.debug_log(f"BadRequestError: {e}")
            self.debug_log(f'Chatgpt Raw: \n{combined_message}')
            return None
        except Exception as e:
            self.debug_log(f"Exception: {e}")
            self.debug_log(f'Chatgpt Raw: \n{combined_message}')
            return None

        text: str = completions.choices[0].message.content
        # role: str = completions.choices[0].message.role

        self.debug_log(f'{model_info["model_name"]} Raw: \n{combined_message}\n------------------------\n{text}')

        # 出于调试目的，写入请求数据
        formatted_file_timestamp = time.strftime('%Y%m%d', time.localtime(time.time()))
        sent_file = f'{self.cache_dir}/CHATGPT.{channel_id}.{formatted_file_timestamp}.txt'
        with open(sent_file, 'a', encoding='utf-8') as file:
            file.write('-' * 20)
            formatted_timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
            file.write(f'{formatted_timestamp} {model_info["model_name"]}')
            file.write('-' * 20)
            file.write('\n')
            all_contents = combined_message
            file.write(f'{all_contents}')
            file.write('\n')
            file.write('-' * 20)
            file.write('\n')
            file.write(f'{text}')
            file.write('\n')

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

            if model_info["supported_feature"].__contains__("json_mode"):
                return ret_str
            else:
                self.debug_log(f"json_mode not supported in {model_info['model_name']}, extracting from:\n{text}")
                json_obj = extract_json(ret_str)
                if json_obj is not None:
                    ret_str = json.dumps(json_obj)
                else:
                    ret_str = None
                return ret_str
        else:
            return ret_str
