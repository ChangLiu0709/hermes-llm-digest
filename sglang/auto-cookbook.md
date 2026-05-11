# Auto-Cookbook: AMD GPU Support for SGLang Cookbook

## Overview

This skill automates the end-to-end process of adding AMD GPU (MI300X, MI325X, MI355X) support
to new model pages in the SGLang Cookbook. It detects new models, tests them on real AMD hardware,
modifies the cookbook codebase, and creates upstream PRs.

## Repositories

| Repository | URL | Purpose |
|---|---|---|
| Upstream | https://github.com/sgl-project/sgl-cookbook | Official SGLang Cookbook |
| Fork | https://github.com/ChangLiu0709/sgl-cookbook | Working fork for PRs |
| Cookbook Docs | https://docs.sglang.io/cookbook/intro | Published cookbook site |
| Docker Hub | https://hub.docker.com/r/lmsysorg/sglang/tags?name=rocm | ROCm SGLang images |

## Hardware

| Resource | Details |
|---|---|
| MI300X Server | ssh amd@64.139.222.223 (hostname: tw023) |
| Working Directory | /home/changliu/SGLang/cookbook/ |
| Auto-Generated Scripts | /home/changliu/SGLang/cookbook/auto-generated/{ModelName}/ |
| Existing Manual Scripts | /home/changliu/SGLang/cookbook/scripts/{ModelName}/ |
| Local Model Storage | /home/amd/models/ |
| Model Folder Naming | models--{Vendor}--{ModelName} (e.g., models--Qwen--Qwen-Image) |
| Cloned Fork Repo | /home/changliu/SGLang/cookbook/sgl-cookbook |
| Fork Git Remotes | origin = ChangLiu0709/sgl-cookbook, upstream = sgl-project/sgl-cookbook |
| SGLang Bug Patches | /home/changliu/SGLang/cookbook/auto-generated/{ModelName}/patches/ |

## GPU Mapping (NVIDIA to AMD)

When adapting NVIDIA commands for AMD GPUs:

- **NVIDIA H200** commands → use for **MI300X / MI325X** (similar VRAM class)
- **NVIDIA B200** commands → use for **MI355X** (next-gen class)

If a cookbook page only has H200 commands, use those as the base for MI300X/MI325X configs.
If a cookbook page has B200 commands, use those as the base for MI355X configs.

## Docker Image Convention

Latest ROCm images follow this naming pattern:
```
lmsysorg/sglang:v{VERSION}-rocm{ROCM_VERSION}-mi30x   # for MI300X/MI325X
lmsysorg/sglang:v{VERSION}-rocm{ROCM_VERSION}-mi35x   # for MI355X
```

Check https://hub.docker.com/r/lmsysorg/sglang/tags?name=rocm for the latest tags.
As of May 2026, the latest are:
- lmsysorg/sglang:v0.5.11-rocm720-mi30x
- lmsysorg/sglang:v0.5.11-rocm720-mi35x

## AMD-Specific Engine Flags

These flags are commonly needed when running on AMD GPUs:
```
--attention-backend triton
--model-loader-extra-config '{"enable_multithread_load": "true", "num_threads": 64}'
--mem-frac 0.95
```

If `--attention-backend triton` fails, try `--attention-backend aiter` or omit the flag entirely.

---

## Pipeline: Step-by-Step

### Phase 1: Detection — Find New Models Without AMD Support

1. **Scrape the cookbook site** at https://docs.sglang.io/cookbook/intro.
   Navigate the sidebar to get the full list of model pages under:
   - Autoregressive Models (docs/autoregressive/{Vendor}/{Model}.md)
   - Diffusion Models (docs/diffusion/{Vendor}/{Model}.md)

2. **For each model page**, check if AMD GPU options (MI300X, MI325X, MI355X) already exist.
   Models with AMD support will have:
   - AMD docker pull commands in the markdown (e.g., `docker pull lmsysorg/sglang:...-rocm...-mi30x`)
   - AMD hardware options in their ConfigGenerator component (e.g., `{ id: 'mi300x', label: 'MI300X' }`)

3. **Cross-reference** with the fork repo at:
   - `src/components/autoregressive/{ModelName}ConfigGenerator/index.js`
   - `src/components/diffusion/{ModelName}ConfigGenerator/index.js`
   Look for `mi300x`, `mi325x`, `mi355x` in the hardware items array.

4. **Output** a list of models needing AMD support, categorised by type (autoregressive vs diffusion).

### Phase 2: Setup — Prepare Server Environment

For each model to be added:

1. **SSH into the MI300X server**:
   ```
   ssh amd@64.139.222.223
   ```

2. **Create the working directory**:
   ```
   mkdir -p /home/changliu/SGLang/cookbook/auto-generated/{ModelName}
   mkdir -p /home/changliu/SGLang/cookbook/auto-generated/{ModelName}/patches
   ```

3. **Download model weights** from HuggingFace to /home/amd/models/:
   ```
   # Use huggingface-cli or git clone
   # The folder MUST follow the naming convention: models--{Vendor}--{ModelName}
   # Example: models--Lightricks--LTX-2.3
   huggingface-cli download {Vendor}/{ModelName} \
     --local-dir /home/amd/models/models--{Vendor}--{ModelName}
   ```
   Note: Some models are very large. Check disk space first with `df -h /home/amd/models/`.

4. **Pull the latest ROCm docker image**:
   ```
   docker pull lmsysorg/sglang:{latest-rocm-mi30x-tag}
   ```
   Check Docker Hub for the latest tag.

5. **Launch a docker container**:
   ```
   docker run -d --name chang_sglang_{model_name_lower} \
     --device=/dev/kfd --device=/dev/dri \
     --security-opt seccomp=unconfined \
     --group-add video \
     --ipc=host --shm-size 64g \
     -v /home:/work \
     -v /home/amd/models:/models \
     -p {PORT}:30000 \
     {docker_image} \
     sleep infinity
   ```
   Choose a unique port (30000-30099 range, check `docker ps` for conflicts).

### Phase 3: Script Creation — Generate server.sh and client.sh

1. **Extract NVIDIA commands** from the cookbook page for the model.
   - Read the markdown file from the upstream repo or the docs site.
   - Find the `sglang serve` or `python -m sglang.launch_server` command blocks.
   - Note any model-specific arguments (e.g., --pipeline-class-name, --ulysses-degree, etc.).

2. **Create server.sh** in `/home/changliu/SGLang/cookbook/auto-generated/{ModelName}/server.sh`:
   ```bash
   #!/bin/bash
   # Server script for {ModelName} on MI300X
   # Adapted from NVIDIA H200 commands
   
   sglang serve \
     --model-path /models/models--{Vendor}--{ModelName}/snapshots/{hash}/ \
     {model_specific_args} \
     --attention-backend triton \
     --mem-frac 0.95
   ```
   
   Key adaptations from NVIDIA to AMD:
   - Replace HuggingFace model ID with local path: `/models/models--{Vendor}--{ModelName}/...`
   - Add `--attention-backend triton` (try `aiter` if triton fails)
   - Add `--mem-frac 0.95`
   - Use `sglang serve` (not `python -m sglang.launch_server`)
   - For multi-node setups (MI300X/MI325X with large models), add distributed flags

3. **Create client.sh** in `/home/changliu/SGLang/cookbook/auto-generated/{ModelName}/client.sh`:

   For **autoregressive models** (LLMs):
   ```bash
   #!/bin/bash
   # Client script for {ModelName} on MI300X
   
   # Basic test
   curl http://127.0.0.1:30000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{
       "model": "{Vendor}/{ModelName}",
       "messages": [{"role": "user", "content": "Hello, how are you?"}]
     }'
   
   # Benchmark
   python3 -m sglang.bench_serving \
     --backend sglang --dataset-name random \
     --num-prompts 100 --random-input 1024 --random-output 512
   ```

   For **diffusion models** (image/video):
   ```bash
   #!/bin/bash
   # Client script for {ModelName} on MI300X
   
   # Single generation test
   python3 -m sglang.multimodal_gen.benchmarks.bench_serving \
     --backend sglang-{image|video} --dataset vbench \
     --task text-to-{image|video} \
     --num-prompts 1 --max-concurrency 1
   
   # High concurrency benchmark
   python3 -m sglang.multimodal_gen.benchmarks.bench_serving \
     --backend sglang-{image|video} --dataset vbench \
     --task text-to-{image|video} \
     --num-prompts 20 --max-concurrency 20
   ```

4. **Update model paths** in both scripts to use the local path after download.

### Phase 4: Testing — Verify on MI300X

1. **Enter the docker container**:
   ```
   docker exec -it chang_sglang_{model_name_lower} bash
   ```

2. **Run server.sh** inside the container:
   ```
   cd /work/changliu/SGLang/cookbook/auto-generated/{ModelName}
   bash server.sh
   ```

3. **If errors occur**, try these in order:
   a. Switch attention backend: `--attention-backend aiter` or remove the flag
   b. Adjust tensor parallelism: try --tp 1, 2, 4, 8
   c. Reduce memory fraction: `--mem-frac 0.9` or `--mem-frac 0.85`
   d. Add `--disable-cuda-graph`
   e. Check if the model architecture is supported in the SGLang version

4. **If a bug in SGLang is found**, create a patch:
   ```
   cd /path/to/sglang/source
   # Make the fix
   git diff > /work/changliu/SGLang/cookbook/auto-generated/{ModelName}/patches/{description}.patch
   ```
   Save all patches locally. PR creation to SGLang main repo is planned for a future skill version.

5. **Run client.sh** to verify the model works:
   ```
   # From another terminal/session inside the same container, or from the host
   bash client.sh
   ```

6. **Record results**: save outputs and any notes to:
   ```
   /home/changliu/SGLang/cookbook/auto-generated/{ModelName}/results.txt
   ```

### Phase 5: Cookbook Codebase Modifications

After successfully testing on MI300X, modify the fork's codebase.

1. **Sync the fork** with upstream:
   ```
   cd /home/changliu/SGLang/cookbook/sgl-cookbook
   git fetch upstream
   git checkout main
   git merge upstream/main
   git push origin main
   ```

2. **Create a feature branch**:
   ```
   git checkout -b {model-name-lowercase}
   # Examples: qwen-image, ltx2.3, deepseek-v4
   ```

3. **Modify the ConfigGenerator** (`src/components/{type}/{ModelName}ConfigGenerator/index.js`):

   a. Add AMD GPU options to the hardware selector:
   ```javascript
   { id: 'mi300x', label: 'MI300X', default: false },
   { id: 'mi325x', label: 'MI325X', default: false },
   { id: 'mi355x', label: 'MI355X', default: false }
   ```

   b. Add model configurations for AMD GPUs:
   ```javascript
   mi300x: { fp8: { tp: N } },   // or with pp/nnodes for multi-node
   mi325x: { fp8: { tp: N } },
   mi355x: { fp8: { tp: N } }
   ```

   c. For multi-node setups (MI300X/MI325X with large models), add the distributed
      command generation logic. Reference PR #212 (Ring-2.5-1T) for the pattern:
      - Environment variable block (MASTER_IP, PORT, DIST_PORT, GLOO/TP_SOCKET_IFNAME)
      - Per-node command builder with node-rank
      - AMD-specific flags (--attention-backend triton, --model-loader-extra-config, --mem-frac)

   d. Add AMD-specific flags in the generateCommand function:
   ```javascript
   const isAmd = ['mi300x', 'mi325x', 'mi355x'].includes(hardware);
   if (isAmd) {
     cmd += ' \\\n  --attention-backend triton';
     // Add other AMD-specific flags as tested
   }
   ```

4. **Modify the cookbook markdown** (`docs/{type}/{Vendor}/{Model}.md`):

   Add AMD docker image pull commands in the installation section:
   ```markdown
   # For MI300X/MI325X
   docker pull lmsysorg/sglang:{version}-rocm{rocm_ver}-mi30x
   
   # For MI355X
   docker pull lmsysorg/sglang:{version}-rocm{rocm_ver}-mi35x
   ```

5. **Update YAML configs** if they exist (`data/models/src/` and `data/models/generated/`):

   Add MI355X (and MI300X/MI325X if applicable) configuration blocks.
   Follow the existing YAML structure for other GPUs.

6. **Update sidebars.js** if a new model page is being added (not typically needed since we are
   adding AMD support to existing pages, not new pages).

### Phase 6: PR Creation

1. **Commit and push** to the fork:
   ```
   cd /home/changliu/SGLang/cookbook/sgl-cookbook
   git add .
   git commit -m "Add support of MI300X/MI325X/MI355X for the {ModelName} cookbook"
   git push origin {branch-name}
   ```

2. **Create the PR** to upstream:
   ```
   gh pr create \
     --repo sgl-project/sgl-cookbook \
     --base main \
     --head ChangLiu0709:{branch-name} \
     --title "Add support of MI300X/MI325X/MI355X for the {ModelName} cookbook" \
     --body "- Added the support of MI300X/MI325X/MI355X in the {ModelName} cookbook.
   - Verified the command on AMD GPUs.
   
   {Additional notes about multi-node, special flags, etc.}"
   ```

   Reference PR #212 format:
   - Title: "Add support of MI300X/MI325X/MI355X for the {ModelName} cookbook"
   - Body: bullet points describing what was added, any special requirements, verification status

---

## File Modification Patterns

### ConfigGenerator index.js — What to Change

Files follow this pattern: `src/components/{autoregressive|diffusion}/{ModelName}ConfigGenerator/index.js`

**Pattern A: Simple single-node (most models)**

Add to hardware items array:
```javascript
{ id: 'mi300x', label: 'MI300X', default: false },
{ id: 'mi325x', label: 'MI325X', default: false },
{ id: 'mi355x', label: 'MI355X', default: false }
```

Add to modelConfigs:
```javascript
mi300x: { fp8: { tp: 8 } },
mi325x: { fp8: { tp: 8 } },
mi355x: { fp8: { tp: 8 } }
```

The command remains the same as NVIDIA but with AMD flags added.

**Pattern B: Multi-node (large models like Ring-2.5-1T, DeepSeek-V3)**

MI300X/MI325X may need 2+ nodes for very large models.
Add distributed command generation with:
- Environment variables (MASTER_IP, PORT, DIST_PORT, GLOO_SOCKET_IFNAME, TP_SOCKET_IFNAME)
- Per-node command builder
- pp-size and nnodes parameters

Reference: PR #212 Ring25ConfigGenerator/index.js for the full pattern.

**Pattern C: Diffusion models (FLUX, Wan, Qwen-Image, LTX)**

May use different arguments:
- --pipeline-class-name (LTX models)
- --ulysses-degree / --ring-degree (Qwen-Image)
- --enable-cfg-parallel (LTX multi-GPU)
- Model-specific flags

### Markdown docs — What to Change

Add after existing NVIDIA docker pull commands:
```markdown
# For MI300X/MI325X
docker pull lmsysorg/sglang:{ver}-rocm{rocm}-mi30x

# For MI355X
docker pull lmsysorg/sglang:{ver}-rocm{rocm}-mi35x
```

Replace `python -m sglang.launch_server` with `sglang serve` throughout.

### YAML configs — What to Change

In `data/models/src/v{version}/{model}.yaml`:
- Add MI355X to comments, defaults, and family overrides
- Add MI300X/MI325X if multi-node config is needed

In `data/models/generated/v{version}/{model}.yaml`:
- Add full configuration block for each AMD GPU

---

## Checklist Per Model

- [ ] Detected model page without AMD support
- [ ] Extracted NVIDIA serve commands from cookbook page
- [ ] Created working directory on MI300X server
- [ ] Downloaded model weights to /home/amd/models/models--{Vendor}--{Model}
- [ ] Created server.sh with AMD-adapted commands
- [ ] Created client.sh with test/benchmark commands
- [ ] Pulled latest ROCm docker image
- [ ] Launched docker container
- [ ] Successfully launched server (noted any flag changes needed)
- [ ] Successfully ran client tests
- [ ] Saved any SGLang patches to patches/ directory
- [ ] Recorded results to results.txt
- [ ] Synced fork with upstream
- [ ] Created feature branch
- [ ] Modified ConfigGenerator index.js (hardware options + model configs + AMD flags)
- [ ] Modified cookbook markdown (docker pull commands, sglang serve)
- [ ] Updated YAML configs (if applicable)
- [ ] Committed and pushed to fork
- [ ] Created PR to sgl-project/sgl-cookbook
- [ ] PR approved and merged

---

## Known Models Already with AMD Support

As of May 2026, these models already have AMD GPU support:
- Qwen-Image (MI300X, MI325X, MI355X)
- Ring-2.5-1T (MI300X, MI325X, MI355X) — PR #212
- DeepSeek-R1 (MI300X)
- DeepSeek-V3 / V3.1 / V3.2 (MI300X)
- DeepSeek-OCR / OCR-2 (MI300X)
- FLUX (MI300X)
- Wan2.1 / Wan2.2 (MI300X)
- Ernie-4.5 (MI300X)
- Step3-VL-10B (MI300X)
- LLaDA 2.1 (MI300X)
- MiMo-V2-Flash (MI300X)
- MOVA (MI300X)

Check the fork's branch list for work in progress:
```
cd /home/changliu/SGLang/cookbook/sgl-cookbook
git branch
```

## Notes

- The MI300X server (64.139.222.223) is shared infrastructure. Check `docker ps` and GPU
  utilization (`rocm-smi`) before launching heavy workloads.
- Model weights can be 50-200+ GB. Always check `/home/amd/models/` disk space before downloading.
- Some models may require SGLang source modifications. Save patches locally but do NOT
  push SGLang patches in the cookbook PR — those go to sgl-project/sglang separately.
- Use `sglang serve` (not `python -m sglang.launch_server`) — the old command is deprecated.
- The fork remote is "origin", the upstream is "upstream" in the sgl-cookbook clone.
- When creating containers, use the naming convention `chang_sglang_{model}` to identify yours.
