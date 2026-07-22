# Request and Result Reference

## Request template

The UTF-8 JSON root must be an object. `system_prompt` and `prompt` are required. `model` may be omitted because the orchestrator defaults it to `nano-banana-2`.

| Field | Values | Default |
| --- | --- | --- |
| `model` | `nano-banana-2`, `nano-banana-pro`, `gpt-image-2` | `nano-banana-2` |
| `system_prompt` | non-empty string or `{"file": "relative/path.md"}` | required |
| `prompt` | non-empty string or `{"file": "relative/path.md"}` | required |
| `negative_prompt` | string, file object, or `null` | `null` |
| `resolution` | `1K`, `2K`, `4K` | `2K` |
| `aspect_ratio` | `1:1`, `4:3`, `3:4`, `16:9`, `9:16` | `16:9` |
| `filename` | safe stem without path or extension | timestamp |
| `output_dir` | directory path | `output` |
| `convert_to_webp` | boolean | `true` |

Prompt file paths are resolved relative to the template file by `laozhang-cli`. Absolute prompt file paths also work. Keep exact Chinese text in the prompt without rewriting it.

Example:

```json
{
  "model": "nano-banana-2",
  "system_prompt": "Create a clean commercial poster. Render supplied text exactly.",
  "prompt": "主标题：智启未来",
  "negative_prompt": "garbled text, invented glyphs, watermark",
  "resolution": "2K",
  "aspect_ratio": "16:9",
  "convert_to_webp": true
}
```

Do not add `LAOZHANG_KEY`. The CLI reads it from the checkout's `.env`.

## Orchestrator arguments

```text
python scripts/generate.py --request REQUEST [--count N] [--concurrency N]
                           [--output-dir DIR] [--filename STEM] [--cli-root DIR]
```

- `--count`: number of independent single-image CLI processes; default 1.
- `--concurrency`: maximum simultaneous processes; default 4, any positive integer allowed.
- `--output-dir`: override the template output directory. Prefer an absolute path.
- `--filename`: override the filename stem. Batch suffixes such as `-01` are automatic.
- `--cli-root`: explicit checkout. Resolution order is this flag, `LAOZHANG_CLI_HOME`, installed `config.json`, then repository ancestry.

The orchestrator uses Python process APIs only. It requires `uv` on `PATH` and never invokes a shell.

## Aggregate result

Stdout contains one JSON object with `success`, `requested`, `succeeded`, `failed`, `concurrency`, `elapsed_seconds`, and ordered `items`. Each item contains `index`, `exit_code`, `success`, `http_status`, `message`, `elapsed_seconds`, and `images`. Image paths are absolute.

Overall `success` is false for partial success. Successful items remain available for visual inspection.

## Exit codes and common failures

| Code | Meaning |
| ---: | --- |
| 0 | Every requested image succeeded |
| 1 | Generation, orchestration, configuration, or partial failure |
| 2 | Orchestrator argument error |

Underlying item exit codes preserve the CLI meanings: 2 input validation, 3 API/upstream failure, and 4 download/storage/conversion failure.

Common messages:

- `LAOZHANG_KEY is not configured`: add the key to the CLI checkout's `.env`.
- `could not find a valid laozhang-cli checkout`: pass `--cli-root`, set `LAOZHANG_CLI_HOME`, or reinstall the personal skill.
- `uv executable was not found`: install `uv` and make it available on `PATH`.
- `laozhang-cli returned invalid JSON`: inspect the sanitized diagnostic and CLI environment; do not retry automatically.
