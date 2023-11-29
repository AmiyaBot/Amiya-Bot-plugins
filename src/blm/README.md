# 大语言模型库

为其他插件提供大语音模型（ChatGPT，文心一言等）调用库。
如果您有什么使用上的问题，欢迎在最下方的链接处反馈。

# 使用方法

## 我是兔兔用户

当你安装了需要该Lib的插件的时候，该插件会因为依赖关系，自动被下载，因此一般情况下你应该不需要手动安装这个插件。

使用时，请在该插件的全局配置项中，填入你的大语言模型相关的密钥和连接。

* `默认模型` : 有时候，其他插件没有提供模型的选项，此时调用本插件时，默认为其提供的模型。如果你配置了文心一言或者ChatGPT等配置后发现这里没有选项，请保存配置然后刷新Console再试。

有些配置项需要重启兔兔以后才能生效，比如切换文心一言或ChatGPT的状态等，如遇到问题，请重启兔兔。

该lib需要OpenAI Python库>=1.0.0版本，您的机器上可能安装了旧版的库，请进行升级。
如果您遇到了：ImportError: cannot import name 'AsyncOpenAI' from 'openai' 等错误，那就是因为您没有lib或lib过低。

### 我是ChatGPT用户

如果你是ChatGPT用户，那你首先需要科学上网，然后你还需要通过代码部署兔兔，并安装openai库，要求版本>=1.0.0

```
pip install openai>=1.0.0
```

此外，OpenAI会时不时更新他们的API策略，所以如果发现插件不能工作，可以先考虑升级OpenAI运行库，方式如下：

```
pip install --upgrade openai
```

然后，您需要使用境外手机号注册 [OpenAI](https://beta.openai.com/) 账户以获取ApiKey。

接下来前往插件配置页面填写插件配置：

* `api_key` :由OpenAI提供给您，必须要给出API_KEY才能使用该插件。
* `url` :
  如果你使用反向代理，那么这里可以通过给出base_url来指定openai调用时的基础Url，该url应该以http开头，结尾不包含斜杠，例如（https://api.openai.com/v1），该参数默认值为空。
* `proxy` :如果你没有全局代理，那么你可以指定proxy参数来给他配置一个http或https代理，socks代理不支持。
* `禁用GPT-4` 开启该开关后，不再向其他插件提供ERNIE-4模型，如果其他插件尝试调用该模型，则会报错。
* `GPT-4限额` 使用GPT-4模型时的平均每小时调用次数，设为0表示不限。

### 我是文心一言用户

请前往 [百度智能云千帆大模型平台](https://console.bce.baidu.com/qianfan/overview) 注册并为 `ERNIE-Bot 4.0`
等模型 [开通按量付费](https://console.bce.baidu.com/qianfan/ais/console/onlineService)，需在平台充值以保证使用。

在 [应用接入](https://console.bce.baidu.com/qianfan/ais/console/applicationConsole/application) 界面创建应用并在插件配置内填写
app_id，API Key 和 Secret Key。

* `app_id` `api_key` `secret_key` :由百度智能云提供给您，必须要填写才能使用该插件。
* `禁用ERNIE-4` 开启该开关后，不再向其他插件提供ERNIE-4模型，如果其他插件尝试调用该模型，则会报错。
* `ERNIE-4限额` 使用ERNIE-4模型时的平均每小时调用次数，设为0表示不限。
* `ERNIE-4视为经济性` 将ERNIE-4输出为经济型模型，方便钱包比较充裕的用户万事万物都用文心一言4

不同模型的收费规则和效果不同，请查看百度智能云控制台，需先为模型开启按量付费，否则对应模型不可用，调用时会报错。

## 我是兔兔开发者

下面这些函数可以让你调用大语言模型，同时还不必关心模型种类和配置细节。

```python
from core import bot as main_bot

blm_library = main_bot.plugins['amiyabot-blm-library']

if blm_library is not None:
    answer = await blm_library.chat_flow('今天的天气怎么样？')
    ...

```

本插件提供的函数如下：

```python

class BLMFunctionCall:
    functon_name:str
    function_schema:Union[str,dict]
    function:Callable[..., Any]

async def chat_flow(
    prompt: Union[str, list],
	model : Optional[Union[str, dict]] = None,
    context_id: Optional[str] = None,
    channel_id: Optional[str] = None,
    functions: Optional[list[BLMFunctionCall]] = None
    ) -> Optional[str]:
    ...

# 下版本支持
async def assistant_flow(
	assistant: str,
    prompt: Union[str, list],
    context_id: Optional[str] = None
    ) -> Optional[str]:
    ...

# 下版本支持
async def assistant_create(
    name:str,
    instructions:str,
    model: Optional[Union[str, dict]] = None,
    functions: Optional[list[BLMFunctionCall]] = None,
    code_interpreter:bool = false,
    retrieval: Optional[List[str]] = None
    ) -> str:
    ...

def model_list() -> List[dict]:
    ...

def get_model(self,model_name:str) -> dict:
    ...

def get_model_quota_left(self,model_name:str) -> int:
    ...

def get_default_model(self) -> dict:
    ...

async def extract_json(content:str):
    ...

```

### chat_flow

Chat工作流，以一问一答的形式，与AI进行交互。

参数列表：

| 参数名        | 类型                              | 释义                                                     | 默认值     |
|------------|---------------------------------|--------------------------------------------------------|---------|
| prompt     | Union[str, list]                | 要提交给模型的Prompt                                          | 无(不可为空) |
| model      | Union[str,dict]                 | 选择的模型，既可以是模型的名字，也可以是model_list或get_model返回的dict        | None    |
| context_id | Optional[str]                   | 如果你需要保持一个对话，请每次都传递相同的context_id，传递None则表示不保存本次Context。 | None    |
| channel_id | Optional[str]                   | 该次Prompt的ChannelId                                     | None    |
| functions  | Optional[list[BLMFunctionCall]] | FunctionCall功能，需要模型支持才能生效                              | None    |

> model可以是字符串，也可以是model_list或get_model返回的dict。在dict的情况下，会访问dict的“model_name”属性来获取模型名称。

> 如果model不存在，会直接返回None。如果传入的model为空，会访问配置项中的‘默认模型’并选择那个模型。

> 关于channel_id，其实本插件并不需要一个channel
> id，该参数的唯一目的是为了保存token调用量。我建议插件调用时，能传递channel_id的场景尽量传递，无法获取ChannelId的时候也最好传递自己插件的名字等，用于在计费的时候区分。

> functions函数是用于FunctionCall功能，需要模型支持。在model_list中，supported_feature带有"function_call"
> 的模型支持这个功能。目前仅ChatGPT支持该功能，具体的功能说明请看[这个文档](https://platform.openai.com/docs/guides/function-calling)
> 。（该功能本版本未实现对接，下个版本会实现对接。）

返回值说明:

| 类型            | 释义                                    |
|---------------|---------------------------------------|
| Optional[str] | 返回模型生成的文本结果。如果模型不存在或prompt为空，则返回None。 |

### model_list

获取可用的Model的列表。

参数说明:

无参数

返回值说明:

| 类型         | 释义                     |
|------------|------------------------|
| List[dict] | 返回可用模型的列表，每个模型以字典形式表示。 |

返回值为一个字典数组，范例如下：

```python
[
    {"model_name":"gpt-3.5-turbo","type":"low-cost","max-token":2000,"supported_feature":["completion_flow","chat_flow","assistant_flow","function_call"]},
    {"model_name":"gpt-4","type":"high-cost","max-token":4000,"supported_feature":["completion_flow","chat_flow","assistant_flow","function_call"]]},
    {"model_name":"ernie-3.5","type":"low-cost","max-token":4000,"supported_feature":["completion_flow","chat_flow"]},
    {"model_name":"ernie-4","type":"high-cost","max-token":4000,"supported_feature":["completion_flow","chat_flow"]},
]
```

具体返回值会根据用户的配置来确定。如果用户没有配置启动文心一言或者
该函数可以用来配合动态配置文件Schema功能，让其他插件可以在自己的插件配置项中展示并让用户选择Model。
该函数可在函数定义阶段就可用，但是考虑到加载顺序问题，建议不要早于load函数中调用。

返回字典格式说明：

| 参数名               | 类型   | 释义                                              |
|-------------------|------|-------------------------------------------------|
| model_name        | str  | 模型的名称                                           |
| type              | str  | 模型的类型，如"low-cost"或"high-cost"                   |
| max-token         | int  | 模型单次请求支持的最大token数，注意诸如function call等功能也会消耗token |
| supported_feature | list | 模型支持的特性列表                                       |

*
*请不要在代码中hardcode模型的名称，在当前版本中，系统会返回诸如ernie-4这样的模型名，但是在未来版本，本插件会支持用户配置两个ChatGPT，三个文心一言这样的设置。届时在返回模型时，就会出现“ERNIE-4(
UserDefinedName)”这样的结果。你的HardCode就会失效。**

### get_model

根据字符串形式的模型名称，返回对应模型的info dict。

参数说明：

| 参数名        | 类型  | 释义       | 默认值 |
|------------|-----|----------|-----|
| model_name | str | 模型的字符串名称 | 无   |

返回值说明：

| 类型   | 释义               |
|------|------------------|
| dict | 返回对应模型名称的info字典。 |

### get_model_quota_left

因为模型的调用配额是可以分开配置的，因此这里可以根据模型名称，查询该模型的配额，开发者可以据此推断模型的行为。

参数说明：

| 参数名        | 类型  | 释义       | 默认值 |
|------------|-----|----------|-----|
| model_name | str | 模型的字符串名称 | 无   |

返回值说明：

| 类型  | 释义                               |
|-----|----------------------------------|
| int | 返回模型的剩余配额数量。 对于无限配额的模型，会返回100000 |

### get_default_model

前面说过，如果不提供模型，那么会调用用户配置的默认模型，该函数就会返回这个默认模型的info dict，让开发者知道用户配置的默认模型是什么。

参数说明：

无参数

返回值说明：

| 类型   | 释义                  |
|------|---------------------|
| dict | 返回用户配置的默认模型的info字典。 |

### extract_json

将字符串转为json的帮助函数。使用正则表达式，从一个字符串中提取出一个json数组或者json对象。
和AI其实没什关系，但是是一个很好用的帮助函数。用于处理诸如：

```
好的，输出的json是：
{
    ...
}

```

这样的返回。

参数说明：

| 参数名     | 类型  | 释义              | 默认值 |
|---------|-----|-----------------|-----|
| content | str | 需要转换为json的字符串内容 | 无   |

返回值说明：

| 类型                      | 释义                             |
|-------------------------|--------------------------------|
| Union[dict, list, None] | 从字符串中提取的json对象、数组或在无法提取时为None。 |

## Typing

如果你想在你的Python开发时获得ide提示支持，你可以将文件`src/blm/src/common/blm_types.py`复制出来放到你的项目文件夹下然后引用里面的type：

```Python
from .yourpath.blm_types import BLMAdapter
from core import bot as main_bot

blm_library:BLMAdapter = main_bot.plugins['amiyabot-blm-library']
```

这样就可以获得Typing的支持。

# 消耗计算

对于有需要的用户，该Lib会统计每次发送请求时，消耗掉的API Token数量，并且可以分频道计算。
您可以打开amiya_plugin数据库并访问amiyabot-blm-library-token-consume表来查询和统计。

如果您使用收费token，并有分频道计费的需求，可以通过这个数据来实现。

下面给大家一个SQL，可以用来计算花了多少钱，token_cost单位为美元。

```SQL
SELECT
	cast( `consume`.`exec_time` AS date ) AS `exec_date`,
	`consume`.`channel_id` AS `channel_id`,
	`consume`.`model_name` AS `model_name`,
	sum( `consume`.`total_tokens` ) AS `sum(total_tokens)`,
	sum((
		CASE

				WHEN ( `consume`.`model_name` = 'gpt-3.5-turbo' ) THEN
				(( `consume`.`total_tokens` * 0.002 ) / 1000 )
				WHEN ( `consume`.`model_name` = 'gpt-4' ) THEN
				((( `consume`.`prompt_tokens` * 0.03 ) + ( `consume`.`completion_tokens` * 0.06 )) / 1000 ) ELSE 0
			END
			)) AS `token_cost`
	FROM
		`amiyabot-blm-library-token-consume` `consume`
	GROUP BY
		`consume`.`model_name`,
		`consume`.`channel_id`,
		cast( `consume`.`exec_time` AS date )
	ORDER BY
	`exec_date`,
	`consume`.`channel_id`
```

# 备注

Logo是用StableDiffusion插件跑出来的。

![兔妈点评](https://raw.githubusercontent.com/AmiyaBot/Amiya-Bot-plugins/master/src/blm/images/chino_logo_comment.png)

反反复复改了几版以后，文档可能有错误，如果文档和代码不一致，请以代码为准。

# 版本信息

| 版本  | 变更     |
|-----|--------|
| 1.0 | 初版登录商店 |
