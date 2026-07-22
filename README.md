# laozhang-cli

`laozhang-cli` 是对 [api.laozhang.ai](https://api.laozhang.ai/) 文生图模型 API 的 Python CLI 封装。项目用于统一不同文生图模型的调用参数，并以 JSON 文件作为唯一的任务输入，以 JSON 作为命令输出，方便脚本、Agent 和自动化工作流集成。

> [!NOTE]
> 项目处于规划与开发阶段。CLI 的 API 调用形式参考 [`kilia/ai-ppt-html` 的 `app.js`](https://github.com/kilia/ai-ppt-html/blob/main/app.js)，具体模型支持范围及参数映射以实际实现为准。

## 设计目标

- 使用 Python 开发，提供一致、可脚本化的命令行接口。
- 所有任务参数通过一个 JSON 文件传入，不在命令行中逐项拼接模型参数。
- 屏蔽不同文生图模型在压缩率、文件格式、像素尺寸等参数上的差异。
- 使用人类易读的统一描述，例如 `"4K"` 分辨率和 `"16:9"` 画面比例。
- 命令执行结果始终输出 JSON，其中包含 HTTP 状态码、消息和本地图片路径。
- 默认将图片保存至 `output/`，并支持可选的 WebP 统一转换。

## 统一参数约定

CLI 对外只暴露一组模型无关的参数，再由模型适配器转换为各上游 API 所需的实际字段。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | :---: | --- | --- |
| `model` | string | 是 | — | api.laozhang.ai 支持的文生图模型名称 |
| `prompt` | string | 是 | — | 图片生成提示词 |
| `negative_prompt` | string | 否 | `null` | 负面提示词；不支持的模型将忽略该项 |
| `resolution` | string | 否 | `"2K"` | 统一分辨率描述，如 `"1K"`、`"2K"`、`"4K"` |
| `aspect_ratio` | string | 否 | `"1:1"` | 统一画面比例，如 `"1:1"`、`"4:3"`、`"3:2"`、`"16:9"`、`"9:16"` |
| `count` | integer | 否 | `1` | 生成图片数量，实际可用范围由模型决定 |
| `filename` | string | 否 | 当前时间戳 | 输出文件名，不含目录和扩展名 |
| `output_dir` | string | 否 | `"output"` | 图片输出目录 |
| `convert_to_webp` | boolean | 否 | `false` | 是否将非 WebP 返回图片转换为 WebP |

以下上游差异不作为公共输入参数：

- 图片压缩率；
- 上游返回文件格式；
- 模型专用的像素宽高表示。

适配器会根据 `resolution` 和 `aspect_ratio` 计算或选择模型支持的最接近尺寸。若模型无法精确满足请求，应在输出消息中说明实际采用的参数，而不是静默改变结果。

## 输入 JSON

示例 `request.json`：

```json
{
  "model": "your-image-model",
  "prompt": "A cinematic photograph of a futuristic city at sunrise",
  "negative_prompt": "blurry, low quality, watermark",
  "resolution": "4K",
  "aspect_ratio": "16:9",
  "count": 1,
  "filename": "futuristic-city",
  "output_dir": "output",
  "convert_to_webp": true
}
```

推荐的 JSON Schema（Draft 2020-12）：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["model", "prompt"],
  "properties": {
    "model": { "type": "string", "minLength": 1 },
    "prompt": { "type": "string", "minLength": 1 },
    "negative_prompt": { "type": ["string", "null"] },
    "resolution": {
      "type": "string",
      "enum": ["1K", "2K", "4K"],
      "default": "2K"
    },
    "aspect_ratio": {
      "type": "string",
      "enum": ["1:1", "4:3", "3:2", "16:9", "9:16"],
      "default": "1:1"
    },
    "count": { "type": "integer", "minimum": 1, "default": 1 },
    "filename": {
      "type": "string",
      "minLength": 1,
      "pattern": "^[^\\\\/:*?\"<>|]+$"
    },
    "output_dir": { "type": "string", "minLength": 1, "default": "output" },
    "convert_to_webp": { "type": "boolean", "default": false }
  }
}
```

API Key 等敏感信息不应写入任务 JSON。实现时建议通过环境变量（例如 `LAOZHANG_API_KEY`）读取。

## CLI 用法

规划中的调用方式：

```bash
python -m laozhang_cli --input request.json
```

标准输出只写入结果 JSON；运行日志和诊断信息应写入标准错误流，以便调用方可靠解析结果。

## 输出 JSON

成功示例：

```json
{
  "success": true,
  "http_status": 200,
  "message": "Image generated successfully",
  "images": [
    {
      "path": "output/futuristic-city.webp",
      "format": "webp"
    }
  ]
}
```

失败示例：

```json
{
  "success": false,
  "http_status": 400,
  "message": "Invalid aspect_ratio for the selected model",
  "images": []
}
```

`http_status` 表示上游 HTTP 返回代码；如果请求尚未发送（例如输入 JSON 校验失败），建议使用 `null`，并由进程退出码表示 CLI 执行失败。

## 文件保存规则

- 默认输出目录为 `output/`。
- 未指定 `filename` 时，使用执行时的本地时间戳，精确到秒：`YYYYMMDD_HHMMSS`。
- 指定 `filename` 时，仅传文件名主体，不包含目录或扩展名；扩展名由最终文件格式决定。
- 一次生成多张图片时，在文件名后追加从 `-01` 开始的序号，避免覆盖文件。
- 如目标文件已存在，实现应生成不冲突的名称，不应静默覆盖已有图片。

示例：

```text
output/20260722_153045.png
output/futuristic-city.webp
output/futuristic-city-01.webp
output/futuristic-city-02.webp
```

## WebP 转换

当 `convert_to_webp` 为 `true` 时：

1. 上游返回 WebP：直接保存，不重复压缩。
2. 上游返回其他格式：保持原图像素尺寸，使用质量参数 `80` 转换为 WebP。
3. 输出 JSON 中的路径和格式必须指向转换后的 `.webp` 文件。
4. 转换成功后默认只保留最终 WebP 文件；若转换失败，则返回失败结果，避免调用方误用未完成的产物。

“保持原图像素尺寸”表示 WebP 转换阶段不再缩放图片；`resolution` 和 `aspect_ratio` 只用于生成阶段的模型参数映射。

## 建议的退出码

| 退出码 | 含义 |
| ---: | --- |
| `0` | 生成并保存成功 |
| `2` | 输入文件读取或 JSON 校验失败 |
| `3` | API 请求失败或上游返回错误 |
| `4` | 图片下载、保存或格式转换失败 |

## License

项目暂未指定开源许可证。在添加许可证文件前，默认保留所有权利。
