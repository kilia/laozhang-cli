# Skill Behavior Scenarios

## Baseline: no skill

### Exact Chinese title

- Prompt: `Generate one 16:9 image for a Chinese product launch poster using laozhang-cli. The title must be “智启未来”.`
- Relevant response excerpt: `使用图像模型：gemini-3-pro-image-preview` and `laozhang generate-image --model "gemini-3-pro-image-preview"`.
- Missing behavior: It invented an unsupported model and command-line interface instead of using the repository's JSON-in/JSON-out CLI, and it did not default to `nano-banana-2` or specify the mandatory post-generation inspection report.

### Bounded concurrent batch

- Prompt: `Use laozhang-cli to generate 6 independent variants of the same Chinese PPT cover. Run at most 2 at once and summarize all results.`
- Relevant response excerpt: `每批用两个 Start-Job 启动，再用 Wait-Job 和 Receive-Job` and `laozhang-cli image generate --model gemini-3-pro-image-preview`.
- Missing behavior: It depended on PowerShell, invented a subcommand and flags, selected an unsupported model, and did not use the actual `--input` JSON contract or define mandatory visual inspection for every successful image.

### Quality warning without retry

- Prompt: `Use laozhang-cli to generate an image containing several Chinese labels. After generation, tell me whether the Chinese text is readable. Do not regenerate it.`
- Relevant response excerpt: `模型优先使用仓库已支持且中文文字渲染能力较强的 gemini-3-pro-image-preview` and `laozhang-cli <实际图片生成子命令>`.
- Missing behavior: It preserved the no-retry requirement and proposed visual inspection, but it still chose an unsupported model, could not produce a valid CLI invocation, and did not use the agreed `acceptable` / `warning` / `failed_quality_check` classification.

## With skill

### Exact Chinese title

- Prompt: `Generate one 16:9 image for a Chinese product launch poster using laozhang-cli. The title must be “智启未来”.`
- Relevant response excerpt: `use the default model nano-banana-2; prepare a UTF-8 JSON request preserving exact title text 智启未来; invoke scripts/generate.py --request <request.json> with no shell syntax`.
- Observed result: It preserves the title verbatim, selects the agreed default, uses the JSON CLI wrapper, requires opening the successful image, classifies it, warns on garbled Chinese, and does not retry.

### Bounded concurrent batch

- Prompt: `Use laozhang-cli to generate 6 independent variants of the same Chinese PPT cover. Run at most 2 at once and summarize all results.`
- Relevant response excerpt: `invoke conceptually with --count 6 --concurrency 2` and `each underlying request is count 1`.
- Observed result: It maps user count to independent processes, honors the user concurrency override, parses one aggregate JSON, reports all items, opens every success, and uses `Retry: not performed`.

### Quality warning without retry

- Prompt: `Use laozhang-cli to generate an image containing several Chinese labels. After generation, tell me whether the Chinese text is readable. Do not regenerate it.`
- Relevant response excerpt: `Open every successful image and inspect it`; `classify acceptable/warning/failed_quality_check`; `explicitly compare visible glyphs against requested Chinese text`; `Retry: not performed`.
