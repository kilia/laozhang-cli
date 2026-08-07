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
| `system_prompt` | string \| object | 是 | — | 定义生图角色、视觉风格和通用规则；支持内联文本或外部文件引用 |
| `prompt` | string \| object | 是 | — | 指定当前图片的具体内容；支持内联文本或外部文件引用 |
| `negative_prompt` | string \| object \| null | 否 | `null` | 指定不希望出现的内容；支持内联文本或外部文件引用，不支持该能力的模型将忽略此项 |
| `resolution` | string | 否 | `"2K"` | 统一分辨率描述，如 `"1K"`、`"2K"`、`"4K"` |
| `quality` | string | 否 | `high` | 生成质量，可选 `high`、`medium` 或 `low`；仅 `gpt-image-2` 生效，Nano Banana 模型忽略此参数 |
| `aspect_ratio` | string | 否 | `"16:9"` | 统一画面比例，如 `"1:1"`、`"4:3"`、`"3:4"`、`"16:9"`、`"9:16"` |
| `count` | integer | 否 | `1` | 生成图片数量，实际可用范围由模型决定 |
| `filename` | string | 否 | 当前时间戳 | 输出文件名，不含目录和扩展名 |
| `output_dir` | string | 否 | `"output"` | 图片输出目录 |
| `convert_to_webp` | boolean | 否 | `true` | 是否将非 WebP 返回图片转换为 WebP；默认启用 |

以下上游差异不作为公共输入参数：

- 图片压缩率；
- 上游返回文件格式；
- 模型专用的像素宽高表示。

适配器会根据 `resolution` 和 `aspect_ratio` 计算或选择模型支持的最接近尺寸。若模型无法精确满足请求，应在输出消息中说明实际采用的参数，而不是静默改变结果。

其中 `quality` 只接受 `high`、`medium` 和 `low`。对 `nano-banana-2` 与 `nano-banana-pro`，该参数不会传给上游 API；对 `gpt-image-2`，默认值为 `high`。

## 输入 JSON

三个提示词参数都接受以下两种形式：

```json
"直接填写的提示词"
```

或者引用 UTF-8 编码的外部文本文件（通常使用 `.md` 文件）：

```json
{ "file": "prompts/style.md" }
```

文件路径相对于输入 JSON 文件所在目录解析。文件引用适合复用角色、风格和负面约束，避免在多个任务中重复输入相同内容。文件内容读取后与内联字符串等价；一个字段不能同时使用内联文本和文件引用。
模型 API 没有独立的 system role 时，适配器按以下顺序构造最终提示词：

```text
{system_prompt}

{prompt}

需要避免的内容：
{negative_prompt}
```

`negative_prompt` 为 `null` 或未提供时，省略最后一段。三个字段在输入 JSON 中保持独立，拼接仅发生在模型适配器构造上游请求时。

示例 `request.json`：

```json
{
  "model": "your-image-model",
  "system_prompt": {
    "file": "prompts/cinematic-style.md"
  },
  "prompt": "A futuristic city at sunrise, viewed from above",
  "negative_prompt": {
    "file": "prompts/negative.md"
  },
  "resolution": "4K",
  "aspect_ratio": "16:9",
  "count": 1,
  "quality": "high",
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
  "$defs": {
    "promptValue": {
      "oneOf": [
        { "type": "string", "minLength": 1 },
        {
          "type": "object",
          "additionalProperties": false,
          "required": ["file"],
          "properties": {
            "file": { "type": "string", "minLength": 1 }
          }
        }
      ]
    }
  },
  "required": ["model", "system_prompt", "prompt"],
  "properties": {
    "model": { "type": "string", "minLength": 1 },
    "system_prompt": { "$ref": "#/$defs/promptValue" },
    "prompt": { "$ref": "#/$defs/promptValue" },
    "negative_prompt": {
      "oneOf": [
        { "$ref": "#/$defs/promptValue" },
        { "type": "null" }
      ],
      "default": null
    },
    "resolution": {
      "type": "string",
      "enum": ["1K", "2K", "4K"],
      "default": "2K"
    },
    "aspect_ratio": {
      "type": "string",
      "enum": ["1:1", "4:3", "3:4", "16:9", "9:16"],
      "default": "16:9"
    },
    "quality": {
      "type": "string",
      "enum": ["high", "medium", "low"],
      "default": "high"
    },
    "count": { "type": "integer", "minimum": 1, "default": 1 },
    "filename": {
      "type": "string",
      "minLength": 1,
      "pattern": "^[^\\\\/:*?\"<>|]+$"
    },
    "output_dir": { "type": "string", "minLength": 1, "default": "output" },
    "convert_to_webp": { "type": "boolean", "default": true }
  }
}
```

API Key 等敏感信息不应写入任务 JSON，统一从项目根目录的 `.env` 文件读取。

## API 访问协议

CLI 使用 `POST` 请求访问 api.laozhang.ai。所有模型统一使用以下请求头：

```http
Authorization: Bearer ${LAOZHANG_KEY}
Content-Type: application/json
```

模型适配器负责将公共 JSON 参数转换为不同的上游协议：

| CLI 模型 | API 地址 | 上游模型 | 协议 |
| --- | --- | --- | --- |
| `gpt-image-2` | `https://api.laozhang.ai/v1/images/generations` | `gpt-image-2-vip` | OpenAI Images 格式 |
| `nano-banana-2` | `https://api.laozhang.ai/v1beta/models/gemini-3.1-flash-image:generateContent` | URL 内指定 | Gemini `generateContent` 格式 |
| `nano-banana-pro` | `https://api.laozhang.ai/v1beta/models/gemini-3-pro-image:generateContent` | URL 内指定 | Gemini `generateContent` 格式 |

GPT Image 请求体结构：

```json
{
  "model": "gpt-image-2-vip",
  "prompt": "最终拼接后的提示词",
  "size": "3840x2160",
  "quality": "high",
  "output_format": "webp"
}
```

`quality` 支持 `high`、`medium` 和 `low`；Nano Banana 请求不使用该参数。

Nano Banana 请求体结构：

```json
{
  "contents": [
    {
      "parts": [
        { "text": "最终拼接后的提示词" }
      ]
    }
  ],
  "generationConfig": {
    "responseModalities": ["IMAGE"],
    "imageConfig": {
      "aspectRatio": "16:9",
      "imageSize": "4K"
    }
  }
}
```

### 分辨率映射

Nano Banana 直接使用 `resolution` 的 `1K`、`2K`、`4K` 描述。GPT Image 需要将分辨率和画面比例转换为具体像素：

| 分辨率 | `16:9` | `4:3` | `1:1` | `3:4` | `9:16` |
| --- | --- | --- | --- | --- | --- |
| `1K` | `1024x576` | `1024x768` | `1024x1024` | `768x1024` | `576x1024` |
| `2K` | `2048x1152` | `2048x1536` | `2048x2048` | `1536x2048` | `1152x2048` |
| `4K` | `3840x2160` | `3840x2880` | `3840x3840` | `2880x3840` | `2160x3840` |

### 上游响应兼容

适配器必须兼容 URL 和 Base64 两类图片响应：

- GPT Image：读取 `data[0].b64_json`，不存在时读取 `data[0].url`。
- Nano Banana：读取 `candidates[0].content.parts[].inlineData.data`，同时兼容 `inline_data`、`mimeType` 和 `mime_type` 字段名。
- URL 响应需要继续下载图片；Base64 响应需要解码后保存。
- 上游错误消息依次从 `error.message`、`message` 或原始响应文本中提取，并连同 HTTP 状态码写入 CLI 输出 JSON。

GPT Image 可以直接请求 PNG、JPEG 或 WebP。Nano Banana 的参考调用没有向 `imageConfig` 传递输出格式，因此 CLI 不应假设其返回特定格式。所有非 WebP 结果仍按照本项目的 WebP 转换规则在本地统一处理。
## Python 环境与依赖

项目默认使用 [uv](https://docs.astral.sh/uv/) 管理 Python 版本、虚拟环境、项目依赖和锁文件。依赖声明保存在 `pyproject.toml`，解析后的精确版本保存在 `uv.lock`；`uv.lock` 应提交到版本控制，以保证不同环境中的安装结果可复现。

项目已包含 `socksio` 运行时依赖，用于启用 `httpx` 的 SOCKS5 支持。需要通过 SOCKS5 代理访问上游 API 时，在 `.env` 中设置 `LAOZHANG_PROXY`，例如 `socks5://127.0.0.1:7890`；不设置时使用直连或系统代理环境变量。


首次获取项目后同步环境：

```bash
uv sync
```

新增运行时依赖时使用 `uv add`，不要直接修改项目虚拟环境：

```bash
uv add Pillow
```

运行 CLI 时使用 `uv run`。该命令会在执行前检查锁文件和项目环境是否与 `pyproject.toml` 同步：

```bash
uv run python -m laozhang_cli --input request.json
```

## CLI 用法

规划中的调用方式：

```bash
uv run python -m laozhang_cli --input request.json
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

项目使用 [Pillow](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#webp) 处理图片读取和 WebP 编码。Pillow 官方支持读写 WebP，并通过底层 `libwebp` 完成编码；通过 uv 安装即可：

```bash
uv add Pillow
```

高质量有损 WebP 转换采用以下参数：

```python
from PIL import Image

with Image.open(source_path) as image:
    image.save(target_path, "WEBP", quality=80, method=6)
```

- `quality=80`：项目约定的有损压缩质量；这也是 Pillow 的 WebP 默认质量。
- `method=6`：使用 Pillow 支持的最高编码工作量，以较慢的编码速度换取更好的压缩效果。
- 不传入新的尺寸，保持原图像素宽高不变。
- 带透明通道的图片保留透明度；如需保留完全透明像素下隐藏的 RGB 值，可额外使用 `exact=True`。

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

## API Key 配置

CLI 所需的 Key 存放在项目根目录的 `.env` 文件中：

```dotenv
LAOZHANG_KEY=your-real-api-key
# 可选：通过 SOCKS5 代理访问上游 API
# LAOZHANG_PROXY=socks5://127.0.0.1:7890
```

复制示例文件并填写真实 Key：

```bash
cp .env.sample .env
```

`.env` 已加入 `.gitignore`，请勿提交包含真实 Key 的配置文件。`.env.sample` 仅用于说明所需的环境变量，不应包含任何有效凭据。
## 示例调用

### Nano Banana 2：直接使用内联 system prompt

`examples/ppt.json` 使用 `nano-banana-2`，分辨率为 `2K`、画面比例为 `16:9`：

```bash
uv run python -m laozhang_cli --input examples/ppt.json
```

成功时，命令输出包含生成耗时和本地图片路径：

```json
{
  "success": true,
  "http_status": 200,
  "message": "Image generated successfully",
  "elapsed_seconds": 17.985,
  "images": [
    {"path": "output/20260722_172125.webp", "format": "webp"}
  ]
}
```

### GPT Image 2：从外部文件引用 system prompt

`examples/ppt-gpt.json` 将 system prompt 独立保存于 `examples/prompts/ppt-gpt-system.md`，JSON 中使用相对路径引用：

```json
"system_prompt": {"file": "prompts/ppt-gpt-system.md"}
```

运行示例：

```bash
uv run python -m laozhang_cli --input examples/ppt-gpt.json
```

### Codex Skill：并发生成 4 张图片

仓库提供 `generating-images-with-laozhang-cli` Skill，用于让 Agent 通过统一的 Python 编排器生成、汇总并检查图片。Skill 的设计原则、目录结构、分发边界和验收标准见[《Repository, PyPI, and Agent Skill Standardization》设计文档](docs/superpowers/specs/2026-07-24-repository-pypi-skill-standardization-design.md)。

Skill 目录遵循 Agent Skill 的渐进式披露结构：

```text
.codex/skills/generating-images-with-laozhang-cli/
├── SKILL.md                         # 触发条件、核心契约和执行流程
├── agents/openai.yaml               # Agent 界面元数据
├── references/request-format.md     # 请求字段和模型差异
└── scripts/
    ├── generate.py                  # 批量编排器
    └── install.py                   # Skill 安装器
```

使用仓库内的纯 Python Skill 安装器和编排器；默认模型为 `nano-banana-2`，默认并发上限为 4：

```text
python .codex/skills/generating-images-with-laozhang-cli/scripts/install.py --cli-root .
python .codex/skills/generating-images-with-laozhang-cli/scripts/generate.py --request request.json --count 4 --concurrency 4 --output-dir output
```

Skill 遵循以下执行契约：

- 每张图片使用一个独立的 CLI 请求，批量任务使用正整数并发上限。
- 汇总所有成功和失败结果；失败项不会触发自动重试。
- 每张成功图片都必须实际打开检查，报告可接受、警告或质量检查失败，并特别检查中文文字是否清晰。
- API Key 只从 CLI checkout 的 `.env` 读取，不写入请求、命令、日志、报告或已安装的 Skill 文件。
- 安装器只复制 `SKILL.md`、`agents/`、`references/` 和 `scripts/`，排除 `.env`、`config.json`、`__pycache__` 及其他运行产物。

Windows、macOS 和 Linux 均使用 Python 文件/进程 API，不依赖 PowerShell、Bash 或 WSL.

所有示例都要求项目根目录存在 `.env`，并配置有效的 `LAOZHANG_KEY`。不要将真实 key 写入 JSON、示例文件或日志。

## Multi-image editing

Add a non-empty `reference_images` path array to the request JSON to enter image-editing mode. Relative paths are resolved from the request JSON directory, and array order is preserved as image 1, image 2, and so on.

```json
{
  "model": "nano-banana-2",
  "system_prompt": "Use the supplied reference images and preserve important visual details.",
  "prompt": "Use the subject from image 1 and the composition from image 2 to create a new image.",
  "reference_images": [
    "images/image_1.jpg",
    "images/image_2.jpg"
  ],
  "resolution": "2K",
  "aspect_ratio": "1:1",
  "filename": "edited-image",
  "output_dir": "output",
  "convert_to_webp": true
}
```

Run it through the existing CLI interface:

```bash
uv run python -m laozhang_cli --input examples/image-edit.json
```

- `gpt-image-2` posts every reference as a repeated `image` multipart field to `/v1/images/edits`.
- `nano-banana-2` and `nano-banana-pro` append references as ordered Gemini `inline_data` parts.
- Omitting `reference_images` keeps the existing text-to-image behavior.
- Missing, unreadable, or empty reference images return input error exit code 2 before any upstream request.
- Raw upstream protocol samples are kept in `examples/reference/` for GPT Image, Nano Banana 2, and Nano Banana Pro.
