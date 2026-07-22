---
name: generating-images-with-laozhang-cli
description: Use when Codex is asked to create, render, or batch-generate images with laozhang-cli, especially for concurrent variants, Chinese text, nano-banana or GPT Image models, or post-generation visual quality checks.
---

# Generating Images with Laozhang CLI

## Core contract

Use the bundled Python orchestrator for every generation. Keep API keys in the CLI checkout's `.env`; never place credentials in requests, commands, logs, or reports. The orchestrator makes one independent `laozhang-cli` call per image and never retries.

## Workflow

1. Read [references/request-format.md](references/request-format.md) when selecting non-default fields or diagnosing a failure.
2. Create a UTF-8 JSON request template. Preserve user-supplied display text verbatim. Default to `nano-banana-2`, `2K`, `16:9`, WebP conversion, and one image unless the user specifies otherwise.
3. Run `scripts/generate.py` with an argument list. Pass `--count` for independent variants and `--concurrency` for the simultaneous-process limit. Default concurrency is 4; honor a positive user override. Do not compose Bash, PowerShell, pipes, or redirection.
4. Parse the single aggregate JSON object. Report every failed item and continue with successful items. Make no second generation call for a failed or visually defective item unless the user later requests it.
5. Open every successful image with the local image-viewing tool. Never infer quality from HTTP success, filenames, or metadata alone.
6. Classify each image as `acceptable`, `warning`, or `failed_quality_check`. Check that it opens, broadly matches the requested composition, is not blank/truncated/corrupt, and renders requested text visibly.
7. For Chinese text, explicitly compare visible glyphs with the requested text. Name the affected file when text is garbled, distorted, invented, missing, or unreadable. Large areas of corrupted Chinese text require `failed_quality_check`.
8. Return the report contract below. Quality findings are advisory: keep the files and do not retry.

## Invocation

```text
python <skill-dir>/scripts/generate.py --request <request.json> --count 4 --concurrency 4 --output-dir <absolute-output-dir> --filename cover
```

The request's `count` is ignored for batching; the orchestrator forces every underlying CLI request to `count: 1`.

## Report contract

```text
Generation: <requested> requested, <succeeded> succeeded, <failed> failed, <elapsed>s
Files:
- <absolute path> — acceptable|warning|failed_quality_check — <specific visual finding>
Generation errors:
- item <index> — exit <code>, HTTP <status|null> — <message>
Retry: not performed
```

Include every successful path and every failed item. Omit `Generation errors` only when none failed.

## Common mistakes

- Do not invent subcommands such as `generate-image`; the real CLI accepts only `--input <json>`.
- Do not use upstream model IDs. Supported public model names are `nano-banana-2`, `nano-banana-pro`, and `gpt-image-2`.
- Do not use one CLI request with `count > 1` for an independent batch.
- Do not describe an image as acceptable before opening it.
