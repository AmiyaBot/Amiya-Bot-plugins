按照以下格式配置文件 `resource/plugins/talking/talking.ini`，**关键词不能重复**。

> 不校验前缀词。

```ini
[你好]
reply = 你好，{nickname}，我是阿米娅，请多多指教！

[用户发送的关键词]
reply = bot 回复的句子

...
```

配置修改马上生效，不需要重启 bot。
