### 配置

图像识别需要额外支持。

> CQ-Http

如果你使用的是 CQ-Http 适配器，直接使用即可。

> 百度智能云

如果不是 CQ-Http 适配器，在 控制台 >> 插件管理 >> 插件配置 内填写 `百度智能云配置` 开启图像识别

如控制台内 `从此处读取百度OCR配置` 未开启，则读取 resource/plugins/baiduCloud.yaml 中的配置

```yaml
enable: true
appId: 21*****7
apiKey: MM************GnL5
secretKey: XR*********************U7UM
```

使用 CQ-Http 适配器也可以同时开启 `百度智能云`，会优先使用百度 OCR。

> PaddleOCR

如果以上没有结果且 python 环境安装了 PaddleOCR，则调用 PaddleOCR 继续尝试识别。

> [Windows.Media.Ocr.Cli](https://github.com/zh-h/Windows.Media.Ocr.Cli)

如果以上没有结果且为 windows 系统，则调用 Windows.Media.Ocr.Cli 继续尝试识别（内置，不需要安装）。
