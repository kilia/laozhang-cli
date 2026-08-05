# Concurrency=20 comparison (2K / 16:9)

Date: 2026-08-05

Same lemon prompt across all three models. Concurrent requests = 20.

| model | ok/req | wall(s) | throughput (rps) | p50 | p95 | mean | pixels |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| nano-banana-pro | 20/20 | 28.657 | **0.6979** | **25.75** | **27.168** | **25.664** | 2752×1536 |
| nano-banana-2 | 20/20 | 38.815 | 0.5153 | 28.939 | 38.474 | 29.301 | 2752×1536 |
| gpt-image-2 | 20/20 | 99.782 | 0.2004 | 94.907 | 99.443 | 84.724 | 2048×1152 |

## Details

- [nano-banana-2 ladder (4→30)](./2026-08-05-nano-banana-2-2k-16x9-concurrency-ladder/)
- [nano-banana-pro @20](./2026-08-05-nano-banana-pro-2k-16x9-concurrency-20/)
- [gpt-image-2 @20](./2026-08-05-gpt-image-2-2k-16x9-concurrency-20/)
