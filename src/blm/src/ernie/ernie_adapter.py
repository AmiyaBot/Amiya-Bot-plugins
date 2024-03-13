import asyncio
from datetime import datetime
import json
import time
from typing import List, Optional, Union

from core import AmiyaBotPluginInstance
from core.util.threadPool import run_in_thread_pool

from amiyabot.log import LoggerManager
from amiyabot.network.httpRequests import http_requests

from ..common.blm_types import BLMAdapter, BLMFunctionCall
from ..common.database import AmiyaBotBLMLibraryMetaStorageModel, AmiyaBotBLMLibraryTokenConsumeModel

from ..common.extract_json import extract_json

logger = LoggerManager('BLM-ERNIE')


class ERNIEAdapter(BLMAdapter):
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
        model_config = self.plugin.get_config("ERNIE")
        if model_config and model_config["enable"] and key in model_config:
            return model_config[key]
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
                "model_name": "ERNIE-Bot",
                "type": "low-cost",
                "max_token": 4000,
                "max-token": 4000,
                "supported_feature": ["completion_flow", "chat_flow","json_mode"],
            },
            {
                "model_name": "ERNIE-Bot-turbo",
                "type": "low-cost",
                "max_token": 4000,                
                "max-token": 4000,
                "supported_feature": ["completion_flow", "chat_flow","json_mode"],
            },
        ]

        disable_high_cost = self.get_config("disable_high_cost")
        use_4_as_low_cost = self.get_config("use_4_as_low_cost")
        ernie_4_cost = "high-cost"
        if use_4_as_low_cost == True:
            ernie_4_cost = "low-cost"
        if disable_high_cost != True:
            model_list_response.append(
                {
                    "model_name": "ERNIE-Bot 4.0",
                    "type": ernie_4_cost,
                    "max_token": 4000,
                    "max-token": 4000,
                    "supported_feature": ["completion_flow", "chat_flow","json_mode"],
                }
            ),
            {
                "model_name": "ERNIE-Bot-8K",
                "type": ernie_4_cost,
                "max_token": 8000,                
                "max-token": 8000,
                "supported_feature": ["completion_flow", "chat_flow","function_call","json_mode"],
            },
        return model_list_response

    async def __get_access_token(self, channel_id):
        appid = self.get_config("app_id")

        access_token_key = "ernie_access_token_" + appid

        access_token_meta = AmiyaBotBLMLibraryMetaStorageModel.get_or_none(
            AmiyaBotBLMLibraryMetaStorageModel.key == access_token_key
        )
        if access_token_meta is not None:
            self.debug_log(f"app id already exists! Load existing access token")
            try:
                access_token_json = json.loads(access_token_meta.meta_str)
            except Exception as e:
                self.debug_log(f"fail to load access token, error: {e}")
                access_token_json = {}
        else:
            self.debug_log(f"app id first time!")
            access_token_json = {}

        if "access_token" in access_token_json and "expire_time" in access_token_json:
            if access_token_json["expire_time"] > time.time():
                return access_token_json["access_token"]
            else:
                self.debug_log(f"access token expired!")

        self.debug_log(f"get new access token")

        api_key = self.get_config("api_key")
        secret_key = self.get_config("secret_key")

        url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={api_key}&client_secret={secret_key}"

        # post request
        access_token_response_str = await http_requests.post(url)

        try:
            access_token_response_json = json.loads(access_token_response_str)
            if "error" in access_token_response_json:
                self.debug_log(f"fail to get access token, error: {access_token_response_json['error']}")
                return None
            else:
                access_token = access_token_response_json["access_token"]
                expire_time = time.time() + access_token_response_json["expires_in"] - 3600 * 24 * 10  # 提前10天
                access_token_meta = AmiyaBotBLMLibraryMetaStorageModel.get_or_none(
                    AmiyaBotBLMLibraryMetaStorageModel.key == access_token_key
                )
                if access_token_meta:
                    access_token_meta.meta_str = json.dumps({"access_token": access_token, "expire_time": expire_time})
                    access_token_meta.save()
                    self.debug_log(f"update access token: {access_token_meta.meta_str}")
                else:
                    access_token_meta = AmiyaBotBLMLibraryMetaStorageModel(
                        key=access_token_key,
                        meta_str=json.dumps({"access_token": access_token, "expire_time": expire_time}),
                    )
                    access_token_meta.save()
                return access_token
        except Exception as e:
            self.debug_log(f"fail to get access token, error: {e}")
            return None

    def __pick_prompt(self, prompts: list, max_chars=4000) -> list:
        text_counter = ""

        for i in range(1, len(prompts) + 1):
            context = prompts[-i]
            text_counter = context["content"] + text_counter
            if len(text_counter) > max_chars:
                return prompts[-i + 1 :]

        return prompts

    async def chat_flow(
        self,
        prompt: Union[str, List[str]],
        model: Optional[Union[str, dict]] = None,
        context_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        functions: Optional[List[BLMFunctionCall]] = None,
        json_mode: Optional[bool] = False,
    ) -> Optional[str]:
        access_token = await self.__get_access_token(channel_id)

        if not access_token:
            return None

        model_info = self.get_model(model)

        if isinstance(prompt, str):
            prompt = [prompt]
        
        if isinstance(prompt, dict):
            prompt = [prompt]

        def prompt_filter(item):
            if not model_info["supported_feature"].__contains__("vision"):
                if isinstance(item,dict) and item["type"] == "image_url":
                    self.debug_log(f"image_url not supported in {model_info['model_name']}")
                    return False
            return True

        prompt = list(filter(prompt_filter, prompt))

        for i in range(len(prompt)):
            if isinstance(prompt[i], str):
                prompt[i] = prompt[i]
            elif isinstance(prompt[i], dict):
                if "type" not in prompt[i]:
                    raise ValueError("无效的prompt")
                if prompt[i]["type"] == "text":
                    prompt[i] = prompt[i]["text"]
                else:
                    raise ValueError("无效的prompt")
            else:
                raise ValueError("无效的prompt")

        # 百度对Message的要求比较奇葩
        # 必须为奇数个成员，成员中message的role必须依次为user、assistant
        # 所以用户的提交必须合并

        big_prompt = "\n".join(prompt)

        if json_mode:
            big_prompt = big_prompt + "\n" + "(Important!!)Please output the result in json format. (重要!!) 请以json格式输出结果。"

        prompt = [{"role": "user", "content": big_prompt}]

        if context_id is not None:
            if context_id not in self.context_holder:
                self.context_holder[context_id] = []
            prompt = self.context_holder[context_id] + prompt

        # 以防万一，进行一个检查，如果prompt列表不是 user 和 assistant 交替出现，
        # 那么就从集合抽出有问题的项目并报日志

        expected_roles = ['user', 'assistant']

        # 当列表中至少有两个元素时循环检查
        while len(prompt) > 1:
            # 检查列表中的每个元素
            for i in range(len(prompt) - 1):
                # 如果当前元素和下一个元素的角色相同或者不符合期望的顺序
                if prompt[i]['role'] == prompt[i + 1]['role'] or prompt[i]['role'] != expected_roles[i % 2]:
                    self.debug_log(f"prompt list order error, remove prompt: {prompt[i]}")
                    del prompt[i]
                    break
            else:
                # 如果所有元素都符合条件，则退出循环
                break

        # 百度的API不需要检测字数，但是为了减少网络流量，这里限制到4000个字。
        # 从后向前计算content的累计字数，砍掉超过4000字的部分，直到字数小于4000

        prompt = self.__pick_prompt(prompt, 4000)

        if len(prompt) % 2 != 1:
            self.debug_log(f"prompt list is not odd, prompt: {prompt}")
            # 移除第一个元素，使其变为奇数
            del prompt[0]

        # Post调用

        model_url_map = {
            "ERNIE-Bot 4.0": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions_pro",
            "ERNIE-Bot": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions",
            "ERNIE-Bot-turbo": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/eb-instant",
            "ERNIE-Bot-8K": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/ernie_bot_8k",
        }

        if model not in model_url_map:
            self.debug_log(f"model {model} not supported")
            return None

        url = model_url_map[model] + "?access_token=" + access_token

        headers = {"Content-Type": "application/json"}

        data = {"messages": [{"role": prompt[i]["role"], "content": prompt[i]["content"]} for i in range(len(prompt))]}

        response_str = await http_requests.post(url, headers=headers, payload=data)

        try:
            response_json = json.loads(response_str)

            if "error_code" in response_json:
                self.debug_log(f"fail to chat, error: {response_json['error_msg']} \n {response_str}")
                return None

            # 校验和取值

            result = response_json["result"]
            usage = response_json["usage"]
            id = response_json["id"]
            _ = usage["prompt_tokens"]
            _ = usage["completion_tokens"]
            _ = usage["total_tokens"]
        except Exception as e:
            self.debug_log(f"fail to chat, error: {e} \n response: {response_str}")
            return None

        combined_message = '\n'.join(obj['content'] for obj in prompt)

        self.debug_log(f'ERNIE Raw: \n{combined_message}\n------------------------\n{result}')

        # 出于调试目的，写入请求数据
        formatted_file_timestamp = time.strftime('%Y%m%d', time.localtime(time.time()))
        sent_file = f'{self.cache_dir}/ERNIE.{channel_id}.{formatted_file_timestamp}.txt'
        with open(sent_file, 'a', encoding='utf-8') as file:
            file.write('-' * 20)
            formatted_timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
            file.write(f'{formatted_timestamp}')
            file.write('-' * 20)
            file.write('\n')
            file.write(f'{combined_message}')
            file.write('\n')
            file.write('-' * 20)
            file.write('\n')
            file.write(f'{result}')
            file.write('\n')

        AmiyaBotBLMLibraryTokenConsumeModel.create(
            channel_id=channel_id,
            model_name=model,
            exec_id=id,
            prompt_tokens=int(usage['prompt_tokens']),
            completion_tokens=int(usage['completion_tokens']),
            total_tokens=int(usage['total_tokens']),
            exec_time=datetime.now(),
        )

        if context_id is not None:
            prompt.append({"role": "assistant", "content": result})
            self.context_holder[context_id] = prompt

        ret_str = f"{result}".strip()

        if json_mode:
            json_obj = extract_json(ret_str)
            if json_obj is not None:
                ret_str = json.dumps(json_obj)
            else:
                ret_str = None

        return ret_str
