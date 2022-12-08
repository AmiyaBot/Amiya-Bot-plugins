调用 OpenAI ChatGPT 智能回复普通对话。

在唤起机器人但不能触发其他任何功能时，将会进入此功能。可以在对话中附带 `chat` 关键词强制触发。

注意：仅支持代码部署使用，并需要使用境外手机号注册 [OpenAI](https://beta.openai.com/) 账户。

## 安装 OpenAI

```
pip install openai
```

## 配置

配置文件：resource/plugins/chatGPT/config.yaml

```yaml
api_key: openai 账户的 api key

# 模型配置
options:
    model: text-davinci-003
    temperature: 0
    max_tokens: 2048
    top_p: 1
    frequency_penalty: 0.0
    presence_penalty: 0.0

# 超过此字数，将转换为 markdown 发送
max_length: 300
```
