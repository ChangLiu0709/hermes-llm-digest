# Benchmark Entry Schema Reference

## Speed Benchmark Entry (with data)

```js
{
  match: { hw: "mi300x", variant: "4b", quant: "bf16", strategy: "low-latency", nodes: "single" },
  sglang_version: "0.5.13.post1",
  speed: [
    { workload: { dataset: "random", isl: 1024, osl: 1024, max_concurrency: 1 },
      ttft_ms: 108, tpot_ms: 2.36, tokens_per_sec_per_gpu: 380 },
    { workload: { dataset: "random", isl: 1024, osl: 1024, max_concurrency: 16 },
      ttft_ms: 178, tpot_ms: 5.61, tokens_per_sec_per_gpu: 2578 },
  ],
},
```

Note: ISL/OSL values are per-model (see "ISL/OSL Values" section below).

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

## ISL/OSL Values — Per-Model, Not Fixed

ISL and OSL come from template placeholders `{{ISL}}` and `{{OSL}}` in the config's
`benchmarkCommands.speed` template. They are rendered by the engine per-model page.
**Always check the live cookbook page** to see what ISL/OSL the engine defaults to.

Known values:
- Qwen3.5: ISL=1024, OSL=1024
- Kimi-K2.6: ISL=1000, OSL=1000
- DeepSeek-V4 (reference model): ISL=8192, OSL=1024

The `numPromptsByConc` also varies per model config. Examples:
- Our sweep: `{ 1: 64, 16: 256, 64: 512, 256: 1024, 1024: 2048, 4096: 4096 }`
- Qwen3.5 PR: `{ 1: 10, 100: 1000 }` (simpler, only 2 data points)
- Kimi-K2.6 PR: `{ 1: 10, 16: 80, 64: 320, 100: 500 }` (4 data points)

**User decision (2026-07-06)**: Keep our larger sweep table and `--warmup-requests 64`
for more comprehensive data. The PR configs use simpler sweeps and no warmup, but
our richer data is preferred. Always match the model's ISL/OSL from the live page.

Key differences from PR configs:
| Parameter         | Our run                              | PR config (typical)     |
|-------------------|--------------------------------------|-------------------------|
| numPromptsByConc  | {1:64, 16:256, 64:512, ...4096:4096} | {1:10, 100:1000}        |
| Concurrency levels| 1, 16, 64, 256, 1024, 4096           | 1, 100                  |
| --warmup-requests | 64                                   | (not set)               |
| ISL/OSL           | From live page (match PR)            | Template vars {{ISL}}/{{OSL}} |

## Three-Phase Workflow: Verify → Sweep → GSM8K

The AMD contributor workflow has three distinct phases after Docker setup:

### Phase 1: Verify Command
- Start server with reconstructed cell command
- Health check: `curl /v1/models`
- Quality check: send chat completion, verify coherent output (not garbled)
- Record sglang version via `pip show sglang`

### Phase 2: Concurrency Sweep (speed benchmarks)
- Run 6 data points across 3 strategies (low-latency, balanced, high-throughput)
- Use `--warmup-requests 64` for stable results
- ISL/OSL from live page (NOT from config JSX which has template placeholders)
- ~30 min total for all 6 points
- Each strategy may need different server config (TP/DP/MTP) — restart as needed

### Phase 3: GSM8K Accuracy (optional)
- Run in background — hours for thinking models (even with --no-thinking)
- Always use `--max-tokens 8192` to prevent infinite generation hangs
- Use `--num-threads 4` for speed (~30 min) vs `--num-threads 1` (~5 hours)
- Accuracy is model-level, not strategy-level — run once per model
- Cannot cross-check against official numbers — GSM8K is saturated, modern models don't report it
- Submit speed benchmarks first, add accuracy in follow-up commit

## Speed Benchmark Command Template

```bash
python3 -m sglang.bench_serving \
  --backend sglang \
  --host localhost --port 30000 \
  --model <MODEL_NAME> \
  --dataset-name random \
  --random-input-len <ISL> --random-output-len <OSL> \
  --num-prompts <NUM_PROMPTS> --max-concurrency <MAX_CONCURRENCY> \
  --warmup-requests 64
```

## Accuracy Benchmark Commands

**Accuracy is OPTIONAL** — benchmark entries without an `accuracy` field render as
"pending" on the live page. This is acceptable for initial PRs; accuracy can be added
in a follow-up commit once the eval finishes.

**GSM8K on thinking/reasoning models is extremely slow.** Models like Qwen3.5-4B
generate very long chain-of-thought responses for each question. With 1319 GSM8K
questions and `--num-threads 32`, expect **6-10+ hours** on MI300X. The ETA shown
early in the run (e.g. "8:32:24") is roughly accurate. Plan accordingly:
- Start GSM8K as a background job (`docker exec -d`)
- Let it run overnight
- Submit the PR with speed benchmarks first, add accuracy later
- Accuracy is model-dependent, not strategy-dependent — only need to run once per
  model (EAGLE vs non-EAGLE gives the same accuracy)

### GSM8K
```bash
pip install git+https://github.com/sgl-project/sgl-eval
sgl-eval run gsm8k \
  --base-url http://localhost:30000/v1 \
  --num-threads 4 \
  --no-thinking \
  --max-tokens 8192
```

**IMPORTANT — Common mistakes:**
- The CLI is `sgl-eval run gsm8k`, NOT `python3 -m sglang.bench_llm_correctness` (that module doesn't exist in sgl-eval).
- Use `--no-thinking` for models with thinking/reasoning mode (Qwen3.5, etc.) to prevent extremely long chain-of-thought responses that make each question take minutes.
- **Always set `--max-tokens 8192`** — without it, some questions cause infinite generation that freezes the eval for hours. Too low (2048) causes 80%+ truncation and artificially low accuracy.
- `--num-threads 4` is the recommended balance — fast throughput (~30 min for 1319 questions) while preventing server contention. With `--max-tokens` set, multi-threading is safe since infinite hangs are prevented.
- `--num-threads 1` works but is very slow (~5 hours). `--num-threads 32` may cause request timeouts on single-GPU or EAGLE setups.

### Cross-Checking GSM8K Accuracy

**GSM8K is considered a saturated benchmark** — many modern model releases (including
Qwen3.5, Qwen3.6) do NOT report GSM8K scores. They use harder math benchmarks like
HMMT Feb/Nov 25, LiveCodeBench, OJBench instead.

When validating a GSM8K score, you likely cannot cross-check against official numbers.
Reasonable ranges for non-thinking mode:
- 4B models: 70-80% (our Qwen3.5-4B measured 73.46% with 48.52% truncation)
- 7-9B models: 80-90%
- 27B+ models: 90%+

Thinking mode scores are typically 5-15% higher than non-thinking for the same model.
High truncation rates (>40%) indicate the `--max-tokens` may still be too low —
accuracy would improve with a higher cap, but diminishing returns set in.

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
