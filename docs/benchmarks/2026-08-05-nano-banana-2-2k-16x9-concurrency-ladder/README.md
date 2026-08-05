# nano-banana-2 concurrency ladder (2K / 16:9)

Date: 2026-08-05

## Setup

- Model: `nano-banana-2`
- Resolution: `2K`
- Aspect ratio: `16:9` (actual output `2752x1536`)
- Concurrency ladder: `4, 8, 12, 16, 20, 24, 30`
- Requests per level: equal to concurrency (total **114** calls)
- Prompt (reused from prior 3-model comparison):

```text
system: Create a clean, simple illustration. No text overlays, no watermarks.
prompt: A single bright yellow lemon on a white ceramic plate, soft natural light, photorealistic
```

Latency metrics below are **per-call wall-clock seconds for successful calls**.
Throughput is `succeeded / level_wall_seconds`.

## Results

| concurrency | ok/req | success | wall(s) | throughput (rps) | p50 | p90 | p95 | p99 | min | max | mean |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 4/4 | 100.0% | 34.465 | 0.1161 | 27.436 | 32.537 | 33.5 | 34.27 | 26.607 | 34.463 | 28.986 |
| 8 | 8/8 | 100.0% | 68.074 | 0.1175 | 62.824 | 67.746 | 67.905 | 68.033 | 28.258 | 68.065 | 52.991 |
| 12 | 12/12 | 100.0% | 41.735 | 0.2875 | 30.957 | 39.372 | 40.49 | 41.484 | 25.07 | 41.733 | 32.092 |
| 16 | 16/16 | 100.0% | 32.612 | 0.4906 | 29.044 | 30.875 | 31.41 | 32.358 | 23.729 | 32.595 | 28.489 |
| 20 | 20/20 | 100.0% | 38.815 | 0.5153 | 28.939 | 36.563 | 38.474 | 38.728 | 21.586 | 38.791 | 29.301 |
| 24 | 24/24 | 100.0% | 60.734 | 0.3952 | 32.995 | 57.062 | 60.628 | 60.69 | 22.491 | 60.708 | 37.595 |
| 30 | 1/30 | 3.3% | 34.645 | 0.0289 | 34.617 | 34.617 | 34.617 | 34.617 | 34.617 | 34.617 | 34.617 |

## Overall (successful calls only)

- total requested: 114
- succeeded: 85
- failed: 29
- success rate: 74.56%
- total wall: 311.091s
- latency wall seconds: min=21.586 p50=30.734 p90=47.907 p95=60.804 p99=67.682 max=68.065 mean=34.161

## Notes

- Concurrency **4–24** completed with **100% success**.
- Peak throughput was around **concurrency=20 (0.515 rps)**; concurrency=16 was close.
- Concurrency **30** mostly failed with HTTP **403** (`user quota is not enough` / `用户额度不足`) after account balance was exhausted — not an API concurrency failure.
- Raw per-call timings: [`results.json`](./results.json). Aggregates: [`summary.json`](./summary.json).
- One sample image per concurrency level is in [`samples/`](./samples/).

## Sample images

| concurrency | sample |
| ---: | --- |
| 4 | ![c4](./samples/sample_c04.webp) |
| 8 | ![c8](./samples/sample_c08.webp) |
| 12 | ![c12](./samples/sample_c12.webp) |
| 16 | ![c16](./samples/sample_c16.webp) |
| 20 | ![c20](./samples/sample_c20.webp) |
| 24 | ![c24](./samples/sample_c24.webp) |
| 30 | ![c30](./samples/sample_c30.webp) |
