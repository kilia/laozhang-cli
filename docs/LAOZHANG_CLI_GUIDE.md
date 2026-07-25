# laozhang-cli 调用与代理配置指南

本文记录在 macOS 上通过本地代理调用 `laozhang-cli` 的可复用流程。以下目录和用户名均为虚构示例，示例工作目录为：

```text
/Users/example-user/Projects/laozhang-cli
```

## 1. 准备环境

项目要求 Python 3.11 或更高版本，并使用 `uv` 管理环境。

```bash
uv --version
uv sync --locked
```

如果仓库没有锁文件，可改用：

```bash
uv sync
```

## 2. 安全配置 Token

在项目根目录创建 `.env`：

```dotenv
LAOZHANG_KEY=在这里填写实际Token
```

不要把 Token 写进请求 JSON、命令、日志或本文档。确认 `.gitignore` 至少包含：

```gitignore
.env
output/
```

收紧文件权限并验证 Git 忽略状态：

```bash
chmod 600 .env
git check-ignore -v .env
git status --short --ignored .env
```

预期看到类似结果：

```text
.gitignore:...:.env .env
!! .env
```

## 3. 配置本地代理

本文使用本机无认证代理：

```text
socks5://localhost:7890
```

先确认端口正在监听：

```bash
nc -vz -w 5 localhost 7890
```

### 推荐方式：HTTP CONNECT

当前项目依赖的 `httpx` 默认没有安装 SOCKS 可选依赖。已确认本机 `7890` 端口也支持 HTTP CONNECT，因此推荐为 CLI 设置：

```bash
export HTTP_PROXY="http://localhost:7890"
export HTTPS_PROXY="http://localhost:7890"
unset ALL_PROXY
```

验证 API 连通性：

```bash
curl --proxy http://localhost:7890 --connect-timeout 15 -o /dev/null -sS -w 'HTTP %{http_code}, TLS %{time_appconnect}s, total %{time_total}s\n' https://api.laozhang.ai/v1/models
```

未携带 Token 时返回 `HTTP 401` 是正常现象，说明 DNS、TCP 和 TLS 已打通。

### 可选方式：原生 SOCKS5

`curl` 可直接使用代理端 DNS 解析：

```bash
curl --proxy socks5h://localhost:7890 --connect-timeout 15 -o /dev/null -sS -w 'HTTP %{http_code}\n' https://api.laozhang.ai/v1/models
```

如果希望 `laozhang-cli` 本身使用 `ALL_PROXY=socks5h://...`，需要先给 `httpx` 安装 SOCKS 支持：

```bash
uv add 'httpx[socks]'
export ALL_PROXY="socks5h://localhost:7890"
```

否则会出现：

```text
ImportError: Using SOCKS proxy, but the 'socksio' package is not installed
```

不想修改项目依赖时，直接使用前面的 HTTP CONNECT 方式即可。

## 4. 创建请求 JSON

示例文件 `requests/example.json`：

```json
{
  "model": "gpt-image-2",
  "system_prompt": "创作一幅高质量、富有想象力且适合儿童观看的电影感科幻插画。人物动作自然，画面中不要出现文字、水印或标志。",
  "prompt": "在火星上奔跑的孪生兄妹，他们刚幼儿园毕业，来火星过暑假",
  "negative_prompt": "恐怖、危险、受伤、成人化、人物畸形、多余肢体、模糊、低清晰度、文字、水印、标志",
  "resolution": "4K",
  "aspect_ratio": "16:9",
  "count": 1,
  "filename": "mars-twins-gpt-image-2-4k",
  "output_dir": "output",
  "convert_to_webp": true
}
```

支持的三个模型：

```text
gpt-image-2
nano-banana-2
nano-banana-pro
```

常用公共参数：

| 参数 | 可用值或说明 |
| --- | --- |
| `resolution` | `1K`、`2K`、`4K` |
| `aspect_ratio` | `1:1`、`4:3`、`3:4`、`16:9`、`9:16` |
| `count` | 正整数，实际限制取决于模型 |
| `filename` | 不含目录和扩展名；每次应使用新名称，避免混淆 |
| `output_dir` | 默认 `output` |
| `convert_to_webp` | 推荐设为 `true` |

提示词也可以引用相对于请求 JSON 所在目录的 UTF-8 文件：

```json
{
  "system_prompt": {"file": "prompts/style.md"},
  "prompt": {"file": "prompts/content.md"},
  "negative_prompt": {"file": "prompts/negative.md"}
}
```

## 5. 调用单个模型

进入项目根目录后执行：

```bash
HTTP_PROXY=http://localhost:7890 HTTPS_PROXY=http://localhost:7890 ALL_PROXY= uv run python -m laozhang_cli --input requests/example.json
```

成功输出示例：

```json
{
  "success": true,
  "http_status": 200,
  "message": "Image generated successfully",
  "elapsed_seconds": 45.476,
  "images": [
    {
      "path": "output/mars-twins-gpt-image-2-4k.webp",
      "format": "webp"
    }
  ]
}
```

退出码约定：

| 退出码 | 含义 |
| ---: | --- |
| `0` | 生成并保存成功 |
| `2` | JSON 读取或参数校验失败 |
| `3` | API 请求或上游响应失败 |
| `4` | 图片下载、保存或格式转换失败 |

## 6. 并行调用三个模型

先为三个模型分别创建请求文件，并确保 `model` 与 `filename` 不同，例如：

```text
requests/mars-twins-gpt-image-2-4k.json
requests/mars-twins-nano-banana-2-4k.json
requests/mars-twins-nano-banana-pro-4k.json
```

使用后台任务并行生成：

```bash
HTTP_PROXY=http://localhost:7890 HTTPS_PROXY=http://localhost:7890 ALL_PROXY= uv run python -m laozhang_cli --input requests/mars-twins-gpt-image-2-4k.json > /tmp/gpt-image-2-result.json &
HTTP_PROXY=http://localhost:7890 HTTPS_PROXY=http://localhost:7890 ALL_PROXY= uv run python -m laozhang_cli --input requests/mars-twins-nano-banana-2-4k.json > /tmp/nano-banana-2-result.json &
HTTP_PROXY=http://localhost:7890 HTTPS_PROXY=http://localhost:7890 ALL_PROXY= uv run python -m laozhang_cli --input requests/mars-twins-nano-banana-pro-4k.json > /tmp/nano-banana-pro-result.json &
wait
cat /tmp/gpt-image-2-result.json /tmp/nano-banana-2-result.json /tmp/nano-banana-pro-result.json
```

每个进程都会消耗一次对应模型额度。并行调用前应确认三个请求的输出文件名互不相同。

仓库中已有本次验证成功的请求，可直接复用：

```bash
HTTP_PROXY=http://localhost:7890 HTTPS_PROXY=http://localhost:7890 ALL_PROXY= uv run python -m laozhang_cli --input requests/mars-twins-gpt-image-2-4k.json
HTTP_PROXY=http://localhost:7890 HTTPS_PROXY=http://localhost:7890 ALL_PROXY= uv run python -m laozhang_cli --input requests/mars-twins-nano-banana-2-4k.json
HTTP_PROXY=http://localhost:7890 HTTPS_PROXY=http://localhost:7890 ALL_PROXY= uv run python -m laozhang_cli --input requests/mars-twins-nano-banana-pro-4k.json
```

## 7. 检查输出尺寸

使用 Pillow 检查生成文件的实际格式和像素：

```bash
uv run python -c 'from PIL import Image; from pathlib import Path; [(lambda im: print(p, im.size, im.format))(Image.open(p)) for p in sorted(Path("output").glob("*.webp"))]'
```

模型可能返回最接近请求规格的尺寸，而不是三个模型完全一致。例如本次 `4K + 16:9` 实测：

```text
gpt-image-2       3840×2160
nano-banana-2     5504×3072
nano-banana-pro   5504×3072
```

因此应以最终文件的实际像素为准。

## 8. 常见故障

### `API request failed` 且没有 HTTP 状态码

通常表示请求未到达 API，优先检查 DNS、TLS 和代理：

```bash
curl -o /dev/null -sS -w 'HTTP %{http_code}, remote %{remote_ip}, TLS %{time_appconnect}s\n' --connect-timeout 10 https://api.laozhang.ai
curl --proxy http://localhost:7890 -o /dev/null -sS -w 'HTTP %{http_code}, remote %{remote_ip}, TLS %{time_appconnect}s\n' --connect-timeout 15 https://api.laozhang.ai
```

若直连报 `SSL_ERROR_SYSCALL`、代理返回 `200` 或 `/v1/models` 返回 `401`，说明应通过代理调用。

### SOCKS 模式提示缺少 `socksio`

原因是 `httpx` 未安装 SOCKS 可选依赖。两种解决办法：

```bash
uv add 'httpx[socks]'
```

或者不修改依赖，使用已经验证可用的 HTTP CONNECT：

```bash
HTTP_PROXY=http://localhost:7890 HTTPS_PROXY=http://localhost:7890 ALL_PROXY= uv run python -m laozhang_cli --input requests/example.json
```

### 返回 HTTP 401

表示 API 已经可达，但 Token 缺失或无效。检查项目根目录 `.env` 中是否存在：

```dotenv
LAOZHANG_KEY=实际Token
```

不要在排查时输出完整 Token。

### 返回 HTTP 400

通常是模型名称、分辨率、比例或请求字段不被上游接受。先使用已验证模型和公共参数，再检查 CLI 输出中的 `message`。

### 文件生成成功但构图不理想

模型输出具有随机性。优化 `system_prompt`、`negative_prompt` 后，用新 `filename` 重新生成。即使提示词要求不出现文字，模型仍可能自行加入胸章、路牌或伪文字，生成后应人工检查。

## 9. 一次性快速流程

在项目根目录依次执行：

```bash
uv sync --locked
chmod 600 .env
nc -vz -w 5 localhost 7890
curl --proxy http://localhost:7890 --connect-timeout 15 -o /dev/null -sS -w 'HTTP %{http_code}\n' https://api.laozhang.ai/v1/models
HTTP_PROXY=http://localhost:7890 HTTPS_PROXY=http://localhost:7890 ALL_PROXY= uv run python -m laozhang_cli --input requests/mars-twins-gpt-image-2-4k.json
```

代理测试返回 `401`、CLI 返回 `"success": true` 即表示完整链路正常。
