# Benchmark Entry Schema Reference

## Speed Benchmark Entry (with data)

```js
{
  match: { hw: "mi300x", variant: "flash", quant: "fp8", strategy: "low-latency", nodes: "single" },
  sglang_version: "0.5.13.post1",
  speed: [
    { workload: { dataset: "random", isl: 8192, osl: 1024, max_concurrency: 1 },
      ttft_ms: 87, tpot_ms: 3.68, tokens_per_sec_per_gpu: 65 },
    { workload: { dataset: "random", isl: 8192, osl: 1024, max_concurrency: 16 },
      ttft_ms: 290, tpot_ms: 6.21, tokens_per_sec_per_gpu: 489 },
  ],
  accuracy: { gsm8k_pct: 97.5 },
},
```

## Stub Entry (no data yet)

```js
{ match: { hw: "mi300x", variant: "flash", quant: "fp8", strategy: "low-latency", nodes: "single" } },
```

## Concurrency Sweep Mapping

The concurrency levels are tied to strategies:

| Strategy        | max_concurrency | num_prompts |
|-----------------|-----------------|-------------|
| low-latency     | 1               | 64          |
| low-latency     | 16              | 256         |
| balanced        | 64              | 512         |
| balanced        | 256             | 1024        |
| high-throughput | 1024            | 2048        |
| high-throughput | 4096            | 4096        |

Source: `benchmarkCommands.numPromptsByConc` in config JSX:
```js
numPromptsByConc: { 1: 64, 16: 256, 64: 512, 256: 1024, 1024: 2048, 4096: 4096 }
```

## Speed Benchmark Command Template

```bash
python3 -m sglang.bench_serving \
  --backend sglang \
  --host localhost --port 30000 \
  --model <MODEL_NAME> \
  --dataset-name random \
  --random-input-len 8192 --random-output-len 1024 \
  --num-prompts <NUM_PROMPTS> --max-concurrency <MAX_CONCURRENCY> \
  --warmup-requests 64
```

## Accuracy Benchmark Commands

### GSM8K
```bash
pip install git+https://github.com/sgl-project/sgl-eval
sgl-eval run gsm8k \
  --base-url http://localhost:30000/v1 \
  --num-threads 32
```

### GPQA Diamond (optional, for reasoning models)
```bash
sgl-eval run gpqa \
  --model <MODEL_NAME> --api-key <api-key> \
  --n-repeats 16 --max-tokens 200000 \
  --temperature 1.0 --top-p 1.0 --thinking \
  --out-dir /sgl-workspace/logs \
  --base-url http://localhost:30000/v1
```

## Extracting Metrics from bench_serving Output

The output looks like:
```
============ Serving Benchmark Result ============
Backend:                                 sglang
Max request concurrency:                 1
Total input tokens:                      524288
Total generated tokens:                  65536
Request throughput (req/s):              0.27
Output token throughput (tok/s):         271.95
Mean TTFT (ms):                          87.42
Mean TPOT (ms):                          3.68
==================================================
```

Map to benchmark fields:
- `ttft_ms` ← Mean TTFT (ms) — round to integer or 2 decimals
- `tpot_ms` ← Mean TPOT (ms) — round to 2 decimals
- `tokens_per_sec_per_gpu` ← Output token throughput / num_gpus — round to integer

## File Locations

Config: `docs_new/src/snippets/configs/{vendor}/{model}.jsx`
Benchmarks: `docs_new/src/snippets/configs/{vendor}/{model}-benchmarks.jsx`
