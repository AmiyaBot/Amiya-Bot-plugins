import asyncio
import json
import re
import time
import traceback
import threading

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
    from openai.types.beta.threads.text_content_block import TextContentBlock
    from openai.types.beta.threads.image_url_content_block import ImageURLContentBlock
    from openai.types.beta.threads.image_file_content_block import ImageFileContentBlock
    from openai.types.beta.threads.image_url_content_block_param import ImageURLContentBlockParam

    enabled = True
    log.info('OpenAI初始化完成')
except ModuleNotFoundError as e:
    log.info(
        f'未安装python库openai或版本低于1.0.0或未安装httpx，无法使用ChatGPT模型，错误消息：{e.msg}\n{traceback.format_exc()}'
    )
    enabled = False

logger = LoggerManager('BLM-GPTAssistant')


class ChatGPTAssistantAdapter(BLMAdapter):
    def __init__(self, plugin):
        super().__init__()
        self.plugin: AmiyaBotPluginInstance = plugin
        self.context_holder = {}
        self.query_times = []
        self.assistant_list_cache = []
        self.thread_cache = {}
        self.thread_assistant_map = {}

        # 定时任务更新assistant列表,每30分钟一次,立即执行第一次
        def wrapper():
            asyncio.run(self.__refresh_api_loop())

        threading.Thread(target=wrapper).start()

    async def __refresh_api_loop(self):
        while True:
            await self.__refresh_api()
            await asyncio.sleep(30 * 60)  # 等待指定的时间间隔

    async def __refresh_api(self):
        client = await self.get_client()

        unified_assistants = []

        async for assistant in client.beta.assistants.list():
            self.debug_log(f"assistant: {assistant}")
            unified_assistants.append(
                {"id": assistant.id, "name": assistant.name, "model": assistant.model, "vision": False}
            )

        self.assistant_list_cache = unified_assistants

    def debug_log(self, msg):
        show_log = self.plugin.get_config("show_log")
        if show_log == True:
            logger.info(f'{msg}')

    def get_config(self, key):
        chatgpt_config = self.plugin.get_config("GPTAssistant")
        if chatgpt_config and chatgpt_config["enable"] and key in chatgpt_config:
            return chatgpt_config[key]
        return None
    
    async def get_client(self):
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
        return client

    def assistant_list(self) -> List[dict]:
        enable_assistant = self.get_config("enable")
        if enable_assistant is None or enable_assistant != True:
            return []

        return self.assistant_list_cache

    async def assistant_thread_touch(self, thread_id: str, assistant_id: str):
        enable_assistant = self.get_config("enable")
        if enable_assistant is None or enable_assistant != True:
            self.debug_log(f"assistant disabled")
            return None
        
        if thread_id not in self.thread_assistant_map.keys():
            return None
        
        if assistant_id != self.thread_assistant_map[thread_id]:
            return None

        # client = await self.get_client()
        # thread = await client.beta.threads.retrieve(thread_id)
        # return thread.id

        timeout = self.get_config("thread_timeout")
        if timeout is None:
            timeout = 1800
        
        if timeout > 5 * 24 * 3600:
            timeout = 5 *24 * 3600

        if thread_id in self.thread_cache:
            if time.time() - self.thread_cache[thread_id] < timeout:
                return thread_id
            else:
                self.thread_cache.pop(thread_id, None)

        return None

    async def assistant_thread_create(self, assistant_id: str):
        enable_assistant = self.get_config("enable")
        if enable_assistant is None or enable_assistant != True:
            return None

        client = await self.get_client()

        thread = await client.beta.threads.create()

        # 记录时间
        self.thread_cache[thread.id] = time.time()

        self.thread_assistant_map[thread.id] = assistant_id

        return thread.id

    async def assistant_run(
        self,
        thread_id: str,
        assistant_id: str,
        messages: Union[dict, List[dict]],
        channel_id: Optional[str] = None,
        json_mode: Optional[bool] = False,
    ) -> Optional[str]:
        enable_assistant = self.get_config("enable")
        if enable_assistant is None or enable_assistant != True:
            return None

        client = await self.get_client()

        if isinstance(messages, dict):
            messages = [messages]

        for i in range(len(messages)):
            if isinstance(messages[i], dict):
                if "type" not in messages[i]:
                    raise ValueError("无效的messages")
                if messages[i]["type"] == "text":
                    self.debug_log(
                        f"Creating Text Message: thread_id = {thread_id}, role = {messages[i]['role']}, content = {messages[i]['text']}"
                    )

                    _ = await client.beta.threads.messages.create(
                        thread_id=thread_id, role=messages[i]["role"], content=messages[i]["text"]
                    )
                elif messages[i]["type"] == "image_url":
                    self.debug_log(
                        f"Creating ImageUrl Message: thread_id = {thread_id}, role = {messages[i]['role']}, content = {messages[i]['image_url']}"
                    )

                    part = ImageURLContentBlockParam()
                    part.image_url = messages[i]["image_url"]

                    _ = await client.beta.threads.messages.create(
                        thread_id=thread_id, role=messages[i]["role"], content=part
                    )
                else:
                    raise ValueError("无效的messages")
            else:
                raise ValueError("无效的messages")

        run = await client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=assistant_id,
        )

        if run.status == 'completed':
            self.thread_cache[thread_id] = time.time()
            current_run_id = run.id
            ret_str = ""
            # message是倒序的，发现不属于本次run的消息就停止
            # 用户提供的消息没有run id, 所以读到就会被打断
            async for message in client.beta.threads.messages.list(thread_id=thread_id):
                if message.run_id != current_run_id:
                    break

                self.debug_log(f"message: {message}")
                if message.role == "assistant":
                    for content in message.content:
                        ret_str += content.text.value
            
            # 填充用量数据
            if run.max_completion_tokens and run.max_prompt_tokens:
                AmiyaBotBLMLibraryTokenConsumeModel.create(
                    channel_id=channel_id,
                    model_name=assistant_id,
                    exec_id=run.id,
                    prompt_tokens=int(run.max_prompt_tokens),
                    completion_tokens=int(run.max_completion_tokens),
                    total_tokens=int(run.max_prompt_tokens+run.max_completion_tokens),
                    exec_time=datetime.now(),
                )
            
        else:
            self.debug_log(f"error: run not complete! {run.id}")
            return None

        # 稍微处理一下引用
        ret_str = re.sub(r'【\d+:\d+†\w+】', '', ret_str)

        if json_mode:
            json_obj = extract_json(ret_str)
            if json_obj is not None:
                ret_str = json.dumps(json_obj)
            else:
                ret_str = "[]"
        
        self.debug_log(f"assistant_run: {ret_str}")

        return ret_str
