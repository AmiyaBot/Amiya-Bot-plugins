import time
import traceback

from datetime import datetime

from typing import List, Optional, Union

from core import AmiyaBotPluginInstance, log

from amiyabot.log import LoggerManager

from ..common.database import AmiyaBotBLMLibraryTokenConsumeModel
from ..common.blm_types import BLMAdapter, BLMFunctionCall

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
                    "max-token": 4000,
                    "supported_feature": ["completion_flow", "chat_flow", "assistant_flow", "function_call"],
                }
            )
            model_list_response.append(
                {
                    "model_name": "gpt-4-1106-preview",
                    "type": "high-cost",
                    "max-token": 128000,
                    "supported_feature": ["completion_flow", "chat_flow", "assistant_flow", "function_call"],
                }
            )
        return model_list_response

    async def chat_flow(
        self,
        prompt: Union[str, List[str]],
        model: Optional[Union[str, dict]] = None,
        context_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        functions: Optional[List[BLMFunctionCall]] = None,
    ) -> Optional[str]:
        if not enabled:
            return None

        self.debug_log(f'chat_flow received: {prompt} {model} {context_id} {channel_id} {functions}')

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

        prompt = [{"role": "user", "content": command} for command in prompt]

        if context_id is not None:
            if context_id not in self.context_holder:
                self.context_holder[context_id] = []
            prompt = self.context_holder[context_id] + prompt

        combined_message = ''.join(obj['content'] for obj in prompt)

        try:
            completions = await client.chat.completions.create(model=model_info["model_name"], messages=prompt)

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
            all_contents = "\n".join([item["content"] for item in prompt])
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

        return f"{text}".strip()
