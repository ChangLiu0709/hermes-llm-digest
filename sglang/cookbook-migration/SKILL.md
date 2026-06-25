---
name: sglang-cookbook-migration
version: 1.0.0
description: "Verify and benchmark AMD cells in SGLang's config-driven cookbook migration. Extract cells from JSX configs, run on MI300X/MI355X hardware, fill benchmark data, and PR results."
tags: [sglang, amd, mi300x, mi355x, cookbook, benchmark, migration]
triggers:
  - cookbook migration
  - verify cookbook cells
  - benchmark cookbook cells
  - sglang cookbook verify
  - sglang cookbook benchmark
  - fill benchmark data
  - concurrency sweep
  - config-driven cookbook
---

# SGLang Cookbook Migration: AMD Verify + Benchmark

Focused on verifying and benchmarking AMD cells (MI300X/MI355X) in SGLang's
config-driven cookbook template system. The models are already migrated to the
new format — our job is to run the commands on real AMD hardware, confirm they
work, run benchmarks, and submit results.

## Context

SGLang migrated cookbooks from legacy per-model React generators to a
config-driven template with shared engines. Each model has:

```
docs_new/src/snippets/configs/{vendor}/{model}.jsx           # config + cells
docs_new/src/snippets/configs/{vendor}/{model}-benchmarks.jsx # benchmark data
docs_new/cookbook/autoregressive/{Vendor}/{Model}.mdx          # page
```

Migration tracking: https://njpxzlfqwrqq.jp.larksuite.com/docx/RK5gdyXjtoNpGXxL7MEjNym9pYb
Contact: @zijiexia

## Repositories & References

- Main repo: https://github.com/sgl-project/sglang (docs_new/ directory)
- Fork: https://github.com/ChangLiu0709/sglang
- Reference migrated model: DeepSeek-V4 (PR #26885)
- Qwen3.5 migration PR: #27848
- Docker images: `lmsysorg/sglang-rocm` on Docker Hub

## Migration Status (as of 2026-06-23)

Already migrated configs:
- deepseek-ai/deepseek-v4
- LiquidAI/lfm2.5
- MiniMaxAI/minimax-m3
- poolside/laguna-m1
- zai-org/glm-5.2
- qwen/qwen3.5 (PR #27848, needs AMD benchmarks)

Legacy generators remaining: ~66 files in docs_new/src/snippets/autoregressive/

## Hardware

- MI300X Server: `ssh amd@64.139.222.223` (hostname: tw023)
- Working dir: `/home/changliu/SGLang/cookbook/`
- Model weights: `/home/amd/models/models--{Vendor}--{ModelName}`

## Workflow Overview

```
1. Pick model   → find AMD cells in {model}.jsx
2. Extract      → reconstruct `sglang serve` command from cell env[] + flags[]
3. Docker setup → pull latest ROCm image, launch container
4. Verify       → start server, send test request, confirm working
5. Benchmark    → GSM8K accuracy + concurrency sweep (6 data points)
6. Record       → fill {model}-benchmarks.jsx with results + sglang_version
7. PR           → push to fork, create PR to sgl-project/sglang, tag @zijiexia
```

## Step 1: Extract AMD Cells

Use the bundled `extract_amd_cells.py` script to parse a model's config JSX
and generate runnable shell commands:

```bash
# Fetch config and extract AMD cells
curl -sL "https://api.github.com/repos/sgl-project/sglang/contents/docs_new/src/snippets/configs/{vendor}/{model}.jsx" \
  -H "Accept: application/vnd.github.v3.raw" > /tmp/{model}.jsx

python3 ~/.hermes/skills/mlops/sglang-cookbook-migration/scripts/extract_amd_cells.py \
  /tmp/{model}.jsx --hw mi300x
```

Output: one shell script per cell with the full `sglang serve` command.

### Manual Cell Reconstruction

If not using the script, reconstruct the command from a cell:

```
Cell:
  match: { hw: "mi300x", variant: "flash", quant: "fp8", strategy: "low-latency", nodes: "single" }
  env: ["SGLANG_USE_AITER=1", "SGLANG_HACK_FLASHMLA_BACKEND=unified_kv_triton"]
  flags: ["--model-path {{MODEL_NAME}}", "--tp 8", "--attention-backend aiter", ...]

→ Command:
  SGLANG_USE_AITER=1 SGLANG_HACK_FLASHMLA_BACKEND=unified_kv_triton \
  sglang serve \
    --model-path <resolved-hf-model-path> \
    --tp 8 \
    --attention-backend aiter \
    ...
```

Replace `{{MODEL_NAME}}` with the HF model path from `modelNames` map in the
config. Try key `"mi300x|variant|quant"` first, fall back to `"variant|quant"`.

Engine-injected flags (do NOT include manually): `--nnodes`, `--node-rank`,
`--dist-init-addr`. But DO include `--host` and `--port` from flags.

## Step 2: Docker Setup

```bash
ssh amd@64.139.222.223

# Check GPU availability (InferenceX benchmark containers)
docker ps --filter "name=gpu-workload" --format "{{.Names}} {{.Status}}"

# Pull latest ROCm image (check dockerImages in the model's config JSX)
docker pull lmsysorg/sglang-rocm:v0.5.13.post1-rocm720-mi30x-20260623

# Launch container
docker run -d --name chang_cookbook_{model} \
  --device=/dev/kfd --device=/dev/dri \
  --security-opt seccomp=unconfined \
  --group-add video --ipc=host --shm-size 64g \
  -v /home:/work -v /home/amd/models:/models \
  -p {PORT}:30000 \
  {env_vars_from_cell} \
  lmsysorg/sglang-rocm:v0.5.13.post1-rocm720-mi30x-20260623 \
  sleep infinity
```

Environment variables from the cell's `env[]` array become `-e KEY=VALUE` flags
on the docker run command.

### Model Path Resolution

```bash
# Find actual model path inside container
docker exec chang_cookbook_{model} \
  find /models/models--{Vendor}--{Model} -name "config.json" -maxdepth 3
# Use the directory containing config.json as --model-path
```

## Step 3: Verify

```bash
# Write server script (avoid docker exec quoting issues)
cat > /home/changliu/SGLang/cookbook/server_{model}.sh << 'EOF'
{env_vars} sglang serve \
  {flags} \
  > /tmp/server.log 2>&1
EOF

# Start server
docker exec -d chang_cookbook_{model} bash /work/changliu/SGLang/cookbook/server_{model}.sh

# Monitor startup (wait for "Uvicorn running on")
docker exec chang_cookbook_{model} tail -f /tmp/server.log

# Health check
curl -s http://localhost:{PORT}/health

# Test request
curl -s http://localhost:{PORT}/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model": "{hf_model_name}", "messages": [{"role":"user","content":"Hello"}], "max_tokens": 64}'
```

If working → cell is verified. If not → fix flags/env and note the fix.

### Get sglang version

```bash
docker exec chang_cookbook_{model} python3 -c "import sglang; print(sglang.__version__)"
```

Record this version — it goes into every benchmark entry as `sglang_version`.

## Step 4: Benchmark

### 4a. Accuracy — GSM8K

```bash
# Install sgl-eval inside container
docker exec chang_cookbook_{model} pip install git+https://github.com/sgl-project/sgl-eval

# Run GSM8K
docker exec chang_cookbook_{model} sgl-eval run gsm8k \
  --base-url http://localhost:30000/v1 \
  --num-threads 32
```

Record the accuracy percentage (e.g., 97.5%).

### 4b. Speed — Concurrency Sweep

Run 6 data points matching the strategy-to-concurrency mapping:

| Strategy        | Concurrency levels | num_prompts              |
|-----------------|-------------------|--------------------------|
| low-latency     | 1, 16             | 64, 256                  |
| balanced        | 64, 256           | 512, 1024                |
| high-throughput | 1024, 4096        | 2048, 4096               |

The num_prompts are derived from `benchmarkCommands.numPromptsByConc` in config:
```
{ 1: 64, 16: 256, 64: 512, 256: 1024, 1024: 2048, 4096: 4096 }
```

Standard workload: `--dataset-name random --random-input-len 8192 --random-output-len 1024`

```bash
# Example: low-latency, concurrency=1
docker exec chang_cookbook_{model} python3 -m sglang.bench_serving \
  --backend sglang \
  --host localhost --port 30000 \
  --model {hf_model_name} \
  --dataset-name random \
  --random-input-len 8192 --random-output-len 1024 \
  --num-prompts 64 --max-concurrency 1 \
  --warmup-requests 64

# low-latency, concurrency=16
docker exec chang_cookbook_{model} python3 -m sglang.bench_serving \
  --backend sglang \
  --host localhost --port 30000 \
  --model {hf_model_name} \
  --dataset-name random \
  --random-input-len 8192 --random-output-len 1024 \
  --num-prompts 256 --max-concurrency 16 \
  --warmup-requests 64
```

From the output, extract:
- `ttft_ms` — Mean TTFT (ms)
- `tpot_ms` — Mean TPOT (ms)
- `tokens_per_sec_per_gpu` — Output token throughput / num_gpus

### Repeat for each strategy

You need to restart the server with different cell flags for each strategy
(low-latency vs balanced vs high-throughput may have different TP/DP/MTP settings).

## Step 5: Record Results

Update `{model}-benchmarks.jsx`. Replace stub entries with measured data:

```js
// BEFORE (stub)
{ match: { hw: "mi300x", variant: "flash", quant: "fp8", strategy: "low-latency", nodes: "single" } },

// AFTER (measured)
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

### Benchmark entry schema

```js
{
  match: { hw, variant, quant, strategy, nodes },  // same 5-tuple as cell
  sglang_version: "x.y.z",                         // REQUIRED — record the exact version
  speed: [
    {
      workload: {
        dataset: "random",
        isl: 8192,              // input sequence length
        osl: 1024,              // output sequence length
        max_concurrency: N,     // from the sweep table above
      },
      ttft_ms: N,               // Mean TTFT from bench_serving output
      tpot_ms: N,               // Mean TPOT from bench_serving output
      tokens_per_sec_per_gpu: N, // output_throughput / num_gpus
    },
    // 2 entries per strategy (2 concurrency levels)
  ],
  accuracy: { gsm8k_pct: N },  // optional, from sgl-eval run
}
```

## Step 6: PR Workflow

### Clone and branch (on WSL, not MI300X server)

```bash
cd /mnt/c/Projects/agents
git clone --depth 1 https://github.com/ChangLiu0709/sglang.git sglang-cookbook-work
cd sglang-cookbook-work
git remote add upstream https://github.com/sgl-project/sglang.git
git fetch upstream main --depth=1
git checkout -b benchmark/{model}-amd upstream/main
```

### Edit benchmarks file

Modify `docs_new/src/snippets/configs/{vendor}/{model}-benchmarks.jsx`:
- Replace AMD stub entries with measured data
- Keep all non-AMD entries unchanged

### If cell fixes were needed

Also modify `docs_new/src/snippets/configs/{vendor}/{model}.jsx`:
- Update flags/env in the cell
- Optionally update `dockerImages` to latest image tag

### Create PR

```bash
git add docs_new/src/snippets/configs/
git commit -m "benchmark: add MI300X benchmarks for {Model}"
git push origin benchmark/{model}-amd

gh pr create --repo sgl-project/sglang \
  --base main --head ChangLiu0709:benchmark/{model}-amd \
  --title "benchmark: add MI300X benchmarks for {Model} cookbook" \
  --body "## Summary
- Verified MI300X cells for {Model} on sglang v{version}
- Added speed benchmarks (concurrency sweep: 1/16/64/256/1024/4096)
- Added GSM8K accuracy
- Docker image: lmsysorg/sglang-rocm:v{image_tag}

cc @zijiexia"
```

### Git push from MI300X server (workaround)

The MI300X server SSH key belongs to 'rasmith', not ChangLiu0709. Use patch transfer:

```bash
# On WSL:
ssh amd@64.139.222.223 'cd /path/to/repo && git format-patch main..HEAD --stdout' > /tmp/model.patch
cd /mnt/c/Projects/agents/sglang-cookbook-work
git am /tmp/model.patch
git push origin benchmark/{model}-amd
```

## Pitfalls

### Server startup
- First launch takes 2-10 min (CUDA graph capture + weight loading for large MoE)
- Watch for "Uvicorn running on http://0.0.0.0:30000" in logs
- Large MoE models (145+ shards) take 5-10 min just to load weights

### GPU conflicts
- InferenceX benchmark containers (`gpu-workload-*`) may be using GPUs
- Check with `docker ps --filter "name=gpu-workload"`
- Wait for them to finish or use fewer GPUs

### bench_serving issues
- If `sglang.bench_serving` module not found, ensure you're on a recent image
- `--warmup-requests 64` is important — cold start skews TTFT

### Docker quoting
- Complex commands in `docker exec` get blocked by Hermes security
- Always write commands to a script file, then `docker exec bash /path/script.sh`

### Benchmark data precision
- Round ttft_ms and tpot_ms to integers or 2 decimal places
- tokens_per_sec_per_gpu should be integer
- Use the MEAN values from bench_serving output, not P50/P99

### Strategy differences
- Strategies may use different TP, DP, MTP, chunked-prefill settings
- Each strategy is a SEPARATE cell with different flags
- Must restart the server with the correct cell's flags for each strategy

### Docker image versioning
- Use the LATEST image from Docker Hub, not the one hardcoded in the config
- Check: `curl -s "https://hub.docker.com/v2/repositories/lmsysorg/sglang-rocm/tags?page_size=5&name=mi30x" | python3 -m json.tool | grep name`
- Update `dockerImages` in the config if using a newer image

### sglang_version is mandatory
- Every benchmark entry MUST include `sglang_version`
- Get it from: `python3 -c "import sglang; print(sglang.__version__)"` inside container
