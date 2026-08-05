# nano-banana-pro concurrency=20 (2K / 16:9)

Date: 2026-08-05

## Setup

- Model: `nano-banana-pro`
- Resolution: `2K` (actual output `2752x1536`)
- Aspect ratio: `16:9`
- Concurrency / requests: **20**
- Prompt (same lemon prompt as the nano-banana-2 ladder):

```text
system: Create a clean, simple illustration. No text overlays, no watermarks.
prompt: A single bright yellow lemon on a white ceramic plate, soft natural light, photorealistic
```

## Results

| metric | value |
| --- | ---: |
| succeeded / requested | 20/20 (100%) |
| level wall (s) | 28.657 |
| throughput (rps) | 0.6979 |

### Latency — wall seconds (successful calls)

| min | p50 | p90 | p95 | p99 | max | mean |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 23.564 | 25.75 | 26.747 | 27.168 | 28.356 | 28.653 | 25.664 |

### Latency — CLI `elapsed_seconds`

| min | p50 | p90 | p95 | p99 | max | mean |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 23.288 | 25.198 | 26.259 | 26.848 | 27.957 | 28.234 | 25.245 |

## Sample

![sample](./samples/sample_01.webp)

Per-call timings: [`summary.json`](./summary.json)
