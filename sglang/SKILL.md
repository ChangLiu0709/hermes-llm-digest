---
name: sglang-auto-cookbook
version: 1.1.0
description: Automatically add AMD GPU (MI300X/MI325X/MI355X) support to SGLang Cookbook models — detect, test on real hardware, modify codebase, create PRs.
tags: [sglang, amd, mi300x, mi355x, cookbook, gpu, rocm]
triggers:
  - add AMD support to sglang cookbook
  - auto-cookbook
  - test model on MI300X
  - sglang cookbook AMD
  - align sglang cookbook with InferenceX PR
  - update cookbook from InferenceX
---

# SGLang Auto-Cookbook: AMD GPU Support Pipeline

Automates end-to-end addition of AMD GPU (MI300X, MI325X, MI355X) support for new models in the SGLang Cookbook.

## Trigger Conditions

- User asks to add AMD GPU support for a new model in SGLang Cookbook
- User asks to check which cookbook models lack AMD support
- User asks to test a model on MI300X server
- Periodic scan for new cookbook models without AMD support
- User asks to align cookbook with an InferenceX PR (update existing model, not add new one)
- User asks to scan InferenceX for recent AMD PRs (triggers automated Mode 1 scan)

## Repositories

- Upstream: https://github.com/sgl-project/sgl-cookbook
- Fork: https://github.com/ChangLiu0709/sgl-cookbook
- Docs site: https://docs.sglang.io/cookbook/intro
- Docker Hub: https://hub.docker.com/r/lmsysorg/sglang/tags?name=rocm

## Hardware

- MI300X Server: `ssh amd@64.139.222.223` (hostname: tw023)
- Working dir: /home/changliu/SGLang/cookbook/
- Auto-generated scripts: /home/changliu/SGLang/cookbook/auto-generated/{ModelName}/
- Model weights: /home/amd/models/models--{Vendor}--{ModelName}
- Fork clone: /home/changliu/SGLang/cookbook/sgl-cookbook (origin=fork, upstream=sgl-project)

## GPU Mapping

- NVIDIA H200 commands → adapt for MI300X / MI325X
- NVIDIA B200 commands → adapt for MI355X

## Pipeline Steps

### 1. Detection

Scrape https://docs.sglang.io/cookbook/intro sidebar for all model pages. For each, check the ConfigGenerator JS file in the repo for `mi300x`/`mi325x`/`mi355x` in the hardware items. Models without these entries need AMD support.

### 2. Environment Setup

```bash
ssh amd@64.139.222.223
mkdir -p /home/changliu/SGLang/cookbook/auto-generated/{ModelName}/patches

# Download model weights
huggingface-cli download {Vendor}/{ModelName} \
  --local-dir /home/amd/models/models--{Vendor}--{ModelName}

# Pull latest ROCm docker image (check Docker Hub for latest tag)
docker pull lmsysorg/sglang:v0.5.11-rocm720-mi30x

# Launch container (include env vars for MLA-based models)
docker run -d --name chang_sglang_{model} \
  --device=/dev/kfd --device=/dev/dri \
  --security-opt seccomp=unconfined \
  --group-add video --ipc=host --shm-size 64g \
  -v /home:/work -v /home/amd/models:/models \
  -p {PORT}:30000 \
  -e SGLANG_USE_AITER=0 \
  -e USE_ROCM_AITER_ROPE_BACKEND=0 \
  -e SGLANG_ROCM_FUSED_DECODE_MLA=false \
  lmsysorg/sglang:v0.5.11-rocm720-mi30x \
  sleep infinity
```

### 3. Script Creation

**server.sh** — Adapt NVIDIA commands with AMD flags:
```bash
sglang serve \
  --model-path /models/models--{Vendor}--{ModelName}/snapshots/{hash}/ \
  {model_specific_args} \
  --attention-backend triton \
  --mem-frac 0.95
```

**client.sh** — For autoregressive models:
```bash
python3 -m sglang.bench_serving \
  --backend sglang --dataset-name random \
  --num-prompts 100 --random-input 1024 --random-output 512
```

For diffusion models:
```bash
python3 -m sglang.multimodal_gen.benchmarks.bench_serving \
  --backend sglang-{image|video} --dataset vbench \
  --task text-to-{image|video} --num-prompts 1 --max-concurrency 1
```

### 4. Testing

```bash
docker exec -it chang_sglang_{model} bash
cd /work/changliu/SGLang/cookbook/auto-generated/{ModelName}
bash server.sh
# In another terminal:
bash client.sh
```

If attention backend errors occur, try in order:
1. `--attention-backend triton` (primary for MI300X)
2. `--attention-backend aiter` (only if model doesn't use MLA)
3. Remove `--attention-backend` flag entirely
4. `--disable-cuda-graph` (REQUIRED for FP8 models — Triton AMD can't compile FP8 matmul kernels)
5. Adjust `--tp` value (some models OOM on tp=1)
6. Set env vars: `SGLANG_USE_AITER=0`, `USE_ROCM_AITER_ROPE_BACKEND=0`, `SGLANG_ROCM_FUSED_DECODE_MLA=false` (critical for MLA models)

Save any SGLang bug fix patches to `patches/` directory.

### 5. Codebase Modifications

```bash
cd /home/changliu/SGLang/cookbook/sgl-cookbook
git fetch upstream && git checkout main && git merge upstream/main && git push origin main
git checkout -b {model-name-lowercase}
```

Modify these files:

**A. ConfigGenerator** (`src/components/{type}/{Model}ConfigGenerator/index.js`):
- Add `mi300x`, `mi325x`, `mi355x` to hardware items array
- Add model configs with tp values
- Add AMD-specific flags in generateCommand
- For large models needing multi-node: add distributed command generation (see PR #212)

**B. Cookbook markdown** (`docs/{type}/{Vendor}/{Model}.md`):
- Add AMD docker pull commands
- Replace `python -m sglang.launch_server` with `sglang serve`

**C. YAML configs** (`data/models/{src,generated}/v{ver}/{model}.yaml`):
- Add MI355X (and MI300X/MI325X) configuration blocks

### 6. PR Creation

```bash
git add . && git commit -m "Add support of MI300X/MI325X/MI355X for the {Model} cookbook"
git push origin {branch}

gh pr create --repo sgl-project/sgl-cookbook \
  --base main --head ChangLiu0709:{branch} \
  --title "Add support of MI300X/MI325X/MI355X for the {Model} cookbook" \
  --body "- Added the support of MI300X/MI325X/MI355X in the {Model} cookbook.
- Verified the command on AMD GPUs."
```

Reference format: PR #212 (https://github.com/sgl-project/sgl-cookbook/pull/212)

## AMD-Specific Engine Flags

```
--attention-backend triton          # Primary choice; fallback: aiter or omit
--model-loader-extra-config '{"enable_multithread_load": "true", "num_threads": 64}'
--mem-frac 0.95                     # Maximize GPU memory usage
```

### Critical Environment Variables for MLA Models on MI300X

Models using Multi-head Latent Attention (MLA) — DeepSeek-style architectures including GLM-4.7-Flash, MiMo-V2-Flash, DeepSeek V3.x — MUST set these env vars on the MI300X docker container:

```bash
-e SGLANG_ROCM_FUSED_DECODE_MLA=false   # Disable buggy fused MLA decode path on ROCm
-e SGLANG_USE_AITER=0                    # Disable aiter (crashes with KeyError on rope_scaling)
-e USE_ROCM_AITER_ROPE_BACKEND=0         # Disable aiter rotary embedding backend
```

**Root cause**: The fused MLA ROCm path (`forward_mla_fused_rope_rocm.py`) has a bug where it tries to unpack a `ForwardMetadata` object as a tuple. The aiter rope backend crashes with `KeyError: 'original_max_position_embeddings'` for models that don't have that field in rope_scaling config.

Without these vars, MLA models crash immediately or during first inference. Non-MLA models (standard transformer attention) may work without them.

### transformers Version Compatibility (v0.5.11-rocm720-mi30x)

The sglang v0.5.11 ROCm image ships with **transformers 5.6.0**. Several 2026 models require newer versions:

| Model | Error | Root Cause |
|-------|-------|------------|
| Mistral-Small-4-119B | `MistralCommonBackend does not implement add_special_tokens` | Pixtral tokenizer needs transformers ≥5.7 |
| Intern-S1-FP8 | `InternS1Tokenizer has no attribute _update_trie` | Custom tokenizer API change |
| DeepSeek-V3.2 | `PreTrainedConfig has no attribute max_position_embeddings` | Config format change |

**DO NOT** just `pip install --upgrade transformers` inside the container — this fixes the tokenizer error but introduces NEW errors in sglang's MLA forward code (version mismatch between sglang code and transformers API). These models need a new sglang ROCm image release.

## Aligning Cookbook with InferenceX PRs

### Automated Scanning (Mode 1a — recommended first step)

Run the scanner script to find AMD-related InferenceX PRs from the last 7 days that haven't been reflected in the cookbook yet:

```bash
# Using the skill's bundled script
python3 ~/.hermes/skills/mlops/sglang-auto-cookbook/scripts/scan_inferencex_prs.py \
  --days 7 --cookbook-path /mnt/c/Projects/agents/sgl-cookbook

# Or if the cookbook isn't cloned locally (uses GitHub API, slower):
python3 ~/.hermes/skills/mlops/sglang-auto-cookbook/scripts/scan_inferencex_prs.py --days 7
```

The script:
1. Lists all PRs in SemiAnalysisAI/InferenceX from the last N days
2. Filters for AMD-related PRs (mi300x/mi325x/mi355x in title or branch)
3. Skips infrastructure-only PRs (runner changes, reverts, monitoring)
4. Checks which PRs modify benchmark `.sh` files (the actual server commands)
5. Cross-references each model+GPU combo against the cookbook's ConfigGenerator
6. Reports which model+GPU combos are missing from the cookbook

Output example:
```
ACTIONABLE: 2 benchmark(s) need cookbook alignment

  Model: Qwen36 | GPU: mi355x | Status: CLOSED
  InferenceX PR: #1556 - fix: correct Qwen3.5 MI355X MTP benchmark setup
  Benchmark: benchmarks/single_node/qwen3.5_fp4_mi355x_mtp.sh

  Model: DeepSeekR1 | GPU: mi355x | Status: MERGED
  InferenceX PR: #1521 - Add dsr1-fp8-mi355x-sglang-mtp single-node MTP recipe
  Benchmark: benchmarks/single_node/dsr1_fp8_mi355x_mtp.sh
```

The MODEL_NAME_MAP dict in the script maps InferenceX model slugs to cookbook ConfigGenerator names. When a new model appears in InferenceX that isn't in the map, the script reports it as UNKNOWN — add the mapping to the script.

### Manual alignment for a specific PR (Mode 1b)

When aligning a specific InferenceX PR (either found by the scanner or given by the user):

### 1. Read the InferenceX PR diff
```bash
curl -sL "https://github.com/SemiAnalysisAI/InferenceX/pull/{PR_NUM}.diff"
# Also read the full benchmark script:
curl -sL "https://raw.githubusercontent.com/SemiAnalysisAI/InferenceX/{branch}/benchmarks/single_node/{model}_{gpu}.sh"
# And the config YAML:
curl -sL "https://raw.githubusercontent.com/SemiAnalysisAI/InferenceX/{branch}/.github/configs/amd-master.yaml" | sed -n '/{config-key}:/,/^[a-z]/p'
```

### 2. Clone fork locally on WSL (no MI300X server needed for config-only changes)
```bash
cd /mnt/c/Projects/agents && git clone --depth 1 https://github.com/ChangLiu0709/sgl-cookbook.git
cd sgl-cookbook
git remote add upstream https://github.com/sgl-project/sgl-cookbook.git
git fetch upstream --depth=1
git checkout main && git merge upstream/main && git push origin main
git checkout -b {branch-name}
```

### 3. Modify files (same 3-file pattern as new models)
- ConfigGenerator JS, documentation markdown, YAML configs

### 4. Create draft PR
```bash
gh pr create --repo sgl-project/sgl-cookbook \
  --base main --head ChangLiu0709:{branch} \
  --title "{title}" --body "{body}" --draft
```

### Key differences from new-model workflow
- No hardware testing needed (InferenceX already verified)
- Can work entirely from WSL (no SSH to MI300X server)
- Focus on updating existing entries, not adding new hardware items
- Reference the InferenceX PR number in the cookbook PR body

## Batch Scanning for Missing AMD Support

To find ALL cookbook models missing MI300X support at once:

```bash
# List all ConfigGenerators
find src/components/autoregressive -name "index.js" -path "*ConfigGenerator*" | sort

# Find which ones have mi300x
grep -rl "mi300x" src/components/autoregressive/

# Diff to find gaps (models with NO mi300x entry)
```

### Models NOT applicable for MI300X (skip these):
- **Nemotron / NemotronSuper** — NVIDIA proprietary (B200/H200 only)
- **DeepSeekMathV2** — Blackwell-only (B200/B300)
- **Ling25 / Ring25** — 1T params, needs multi-node (GB200/GB300)
- Any model already covered by a pending PR

### Some models have MI355X but NOT MI300X
- DeepSeek V3.2 — has MI355X, missing MI300X (tp=8 needed)
- MiMo-V2-Flash — has MI355X (tp=4), missing MI300X

## Batch Testing on MI300X Server

### GPU Availability Detection
The server runs InferenceX benchmark containers named `gpu-workload-{0-7}-{timestamp}`. Check before launching:
```bash
docker ps --filter "name=gpu-workload" --format "{{.Names}} {{.Status}}"
# Count busy GPUs:
docker ps --filter "name=gpu-workload" --format "." | wc -l
```
These benchmarks typically run 30-60+ minutes. Wait for them to finish before testing.

### Wait-for-GPUs Pattern
```bash
while true; do
    BUSY=$(docker ps --filter "name=gpu-workload" --format "." | wc -l)
    FREE=$((8 - BUSY))
    [ "$FREE" -ge "$NEEDED" ] && break
    sleep 60
done
```

### Model Path Resolution (HF Cache Layout)
Models on the server are in HF cache format. Resolve the actual path:
```bash
find /home/amd/models/models--{Vendor}--{Model} -name "config.json" -maxdepth 3
# Typical result: /home/amd/models/models--X--Y/snapshots/{hash}/config.json
# Use the directory containing config.json as --model-path inside docker
```

### Sequential Test Script Pattern
For batch testing, launch containers with `sleep infinity`, then `docker exec -d` to start the server, poll health endpoint, send test request, capture result, cleanup. See `references/batch-test-pattern.md`.

## AMD MI300X Environment Variables (Critical)

For MLA-based models (GLM family, DeepSeek family, MiMo) on MI300X, these environment variables are critical:
- `SGLANG_USE_AITER=0` — Disables aiter backend which crashes on MLA rope
- `USE_ROCM_AITER_ROPE_BACKEND=0` — Disables aiter rope backend
- `SGLANG_ROCM_FUSED_DECODE_MLA=false` — Disables fused MLA decode path that has ForwardMetadata unpacking bug

Without these, MLA models crash with either `KeyError: 'original_max_position_embeddings'` in aiter rope, or `TypeError: cannot unpack non-iterable ForwardMetadata object` in fused MLA decode.

FP8 models (MiMo-V2-Flash, etc.) fail with `PassManager::run failed` on fp8_kernel.py — this is a Triton AMD compiler limitation with FP8 matmul kernels on MI300X as of sglang v0.5.11. **Workaround**: add `--disable-cuda-graph` to the server command. This bypasses Triton compilation of FP8 kernels at a performance cost, but the model runs correctly. `--cuda-graph-max-bs` alone does NOT help — the error occurs on the very first graph.

Models requiring transformers >= 5.7 (Mistral-Small-4, Intern-S1, DeepSeek V3.2) will fail on the v0.5.11-rocm720-mi30x image which ships transformers 5.6.0.

## Pitfalls (General)
- Model weights can be 50-200+ GB — check disk space first
- Use `sglang serve` not `python -m sglang.launch_server` (deprecated)
- Container naming: `chang_sglang_{model}` to identify yours
- Fork remote is "origin", upstream is "upstream"
- SGLang patches go to sgl-project/sglang separately, not in cookbook PRs
- Some ConfigGenerators use a base component pattern (import from `../../base/ConfigGenerator`), others are self-contained — read the existing file before modifying

## Pitfalls Discovered in Practice (v1.1)

### Model Path Resolution
- HF cache-style dirs (models--X--Y) have files under `snapshots/{hash}/`, NOT at the top level. The `--model-path` must point to the dir containing `config.json`.
- BUT: when using `huggingface_hub.snapshot_download(local_dir=...)`, files land DIRECTLY in the target dir (no snapshots/ subdir). So the path depends on how the model was downloaded.
- Always verify: `ls {model_path}/config.json` inside the container before launching.

### huggingface-cli Broken on Server
- `huggingface-cli` on the MI300X server has an ImportError (`HF_HUB_ENABLE_HF_TRANSFER`). Use Python API instead:
  ```
  python3 -c 'from huggingface_hub import snapshot_download; snapshot_download("Vendor/Model", local_dir="/home/amd/models/models--Vendor--Model")'
  ```

### Git Push from MI300X Server
- The SSH key on the server belongs to 'rasmith', NOT ChangLiu0709. Cannot push to the fork via SSH.
- HTTPS push also fails — no `gh` CLI installed, no credential helper.
- **Workaround**: Make changes + commit on the server, `git format-patch main..{branch} --stdout` to extract the patch, pipe it to WSL, `git am` it in a local shallow clone, push from WSL where `gh` is authenticated.
  ```bash
  # On WSL:
  ssh amd@64.139.222.223 'cd /home/changliu/SGLang/cookbook/sgl-cookbook && git format-patch main..{branch} --stdout' > /tmp/model.patch
  cd /tmp && git clone --depth 1 https://github.com/ChangLiu0709/sgl-cookbook.git fork
  cd fork && git checkout -b {branch} && git am /tmp/model.patch
  git push origin {branch}
  ```

### sglang.bench_serving Missing Module
- In SGLang v0.5.10, `python3 -m sglang.bench_serving` fails with `ModuleNotFoundError: No module named 'sglang.benchmark.datasets'`. Use simple curl-based chat tests as fallback for verification.

### Server Startup Time
- First launch takes 2-3 min for CUDA graph capture + aiter JIT kernel compilation. This is normal — watch for "Uvicorn running on http://0.0.0.0:30000" in logs.
- `rocm-smi` produces no output on the host; it only works inside Docker containers.
- Large MoE models (145+ shards) take 5-10 min just to load weights. Don't assume crash if health check fails at 60s.

### Process Detection in Docker
- `docker exec container pgrep -f sglang` is UNRELIABLE during model weight loading — processes may briefly not match or docker exec may timeout.
- Better approach: use `docker exec container ps aux --no-header` and check for zombie `<defunct>` processes (confirms crash) vs active processes (still loading).
- Best approach: redirect server output to `/tmp/server.log` inside the container, then `docker exec container tail /tmp/server.log` to check actual progress.

### Container Launch Pattern (recommended)
- Launch with `sleep infinity`, then `docker exec -d` to start the server. This lets you inspect/restart the server without recreating the container.
- Write server launch commands to a bash script on the host (mounted via `-v /home:/work`), then `docker exec -d container bash /work/path/script.sh`.
- Complex quoting in `docker exec` commands gets blocked by Hermes security. Always use script files instead.

### MiMo-V2-Flash on MI300X
- OOMs on tp=1 (292GB FP8 MoE model, 192GB GPU = not enough). Use **tp=2** (confirmed working).
- Requires `--disable-cuda-graph` — without it, FP8 Triton kernel compilation fails with `PassManager::run failed` on `fp8_kernel.py`. This is the Triton AMD compiler unable to handle FP8 matmul kernels.
- `--disable-cuda-graph` has a performance penalty but is the only way to run FP8 models on MI300X with sglang v0.5.11.
- The existing MI355X config uses tp=4; MI300X uses tp=2.

### ConfigGenerator JS Escaping
- The JS files use `\\\n` (literal backslash-backslash-backslash-n) for line continuations in generated commands. When patching, fetch the ORIGINAL file from the upstream repo via `gh api` and apply minimal changes to preserve escaping. Do NOT rewrite the entire file — escaping errors are easy to introduce.
- **CRITICAL**: The Hermes `patch` tool DOUBLES backslashes on every application. NEVER use `patch` on ConfigGenerator JS files that contain `\\\n` sequences. Instead, use `write_file` to write the complete file content. The `patch` tool will turn `\\\n` into `\\\\\\n` silently, breaking the generated commands.
- If you accidentally corrupt escaping with `patch`, `git checkout -- {file}` to revert and then use `write_file` for the whole file.

### Extraneous Files
- `git add -A` on the server can pick up untracked files (e.g., `data/scripts/run_npm_in_schema.sh`). Always review `git diff --cached --stat` before committing and `git reset HEAD` any unwanted files.

### SSH Output Buffering for Long-Running Scripts
- Running `ssh host 'bash -s' < script.sh` in background mode produces NO output until the script finishes — stdout is fully buffered with no PTY.
- **Workaround**: Copy the script to the server, have it write to a log file, then `tail` the log separately:
  ```bash
  # Copy script
  cat local_script.sh | ssh amd@64.139.222.223 'cat > /path/remote_script.sh'
  # Run in background
  terminal(background=true): ssh amd@64.139.222.223 'bash /path/remote_script.sh'
  # Monitor from separate command
  ssh amd@64.139.222.223 'tail -20 /path/logfile.log'
  ```
- NEVER rely on background SSH process output for monitoring — always use a server-side log file.

### npm install / build on WSL
- `npm install` in the sgl-cookbook repo can take 5+ minutes on WSL and may timeout. For config-only PRs (no new React components), skip the local build and let the PR's CI handle verification.
- If build verification is needed, try `npm run build` only after a successful `npm install`; do NOT block the PR on local build if it's timing out.

## Completed Models Log

| Model | PR | Date | Notes | Reference |
|-------|-----|------|-------|-----------|
| Ring-2.5-1T | #212 | 2026-04 | Multi-node MI300X, single MI355X | — |
| Qwen3.6 | #268 | 2026-05-11 | tp=1 all AMD GPUs, both FP8+BF16 | references/qwen36-run.md |
| GLM-5-FP8 (MI355X) | #269 | 2026-05-14 | FP8 tp=4 on MI355X, aligned with InferenceX #1375 | references/glm5-fp8-mi355x.md |
| GLM-4.7-Flash (MI300X) | #270 | 2026-05-14 | tp=1, env vars required for MLA compat | references/batch-amd-may2026.md |
| MiMo-V2-Flash (MI300X) | #271 | 2026-05-14 | tp=2, --disable-cuda-graph for FP8 Triton compat | references/batch-amd-may2026.md |

See `references/` for per-model session logs with exact commands and paths.
- `references/batch-test-pattern.md` — Reusable template for batch-testing multiple models on MI300X
- `references/batch-amd-may2026.md` — Status of May 2026 batch AMD support campaign (5 models)
