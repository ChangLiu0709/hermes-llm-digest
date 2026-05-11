---
name: vllm-recipe-pr-creation
description: Create draft PRs adding AMD GPU support to vLLM-Omni models in vllm-project/recipes — practical steps from 3 real PRs (SD3.5, Wan2.2, Stable Audio Open) covering YAML changes, legacy markdown, ROCm wheel URLs, PR body formatting, and gemini-code-assist review fixes.
---

# vLLM-Omni Recipe PR Creation (AMD GPU Support)

Hands-on workflow for adding AMD MI300X/MI325X/MI355X support to vLLM-Omni models in the [vllm-project/recipes](https://github.com/vllm-project/recipes) repo. This is a practical supplement to the `amd-gpu-recipe-support` skill, focusing specifically on the **vLLM-Omni (task: `omni`)** model type and incorporating lessons from PRs #451, #452, #453.

## Core Principle

**Purely additive — never modify existing NVIDIA content.** Only ADD new AMD sections.

Exception: if the model already has AMD content with errors (broken wheel URL, missing `meta.hardware`), you MAY fix those. The rule protects NVIDIA content only.

## Detection: Is This a vLLM-Omni Model?

Check the YAML recipe at `models/<hf_org>/<hf_repo>.yaml`:

```yaml
meta:
  tasks:
    - omni     # <-- If present, it's a vLLM-Omni model
```

Omni models:
- **No `vllm serve` commands** — served via offline Python scripts
- **`compatible_strategies: []`** — leave empty
- **`VLLM_OMNI_TARGET_DEVICE=rocm`** at install time, not runtime

## Pre-Flight Checks

### 1. ROCm Wheel Availability

Not every CUDA vLLM version has a ROCm wheel. **Always verify before committing:**

```bash
curl -sI "https://wheels.vllm.ai/rocm/<version>/<rocm-tag>/" | head -5
# 200 = exists, 404 = doesn't exist
```

**Known wheel status (as of May 2026):**

| CUDA Version | ROCm Wheel | ROCm Tag | Wheel URL |
|---|---|---|---|
| 0.12.0 | ❌ 404 | N/A | N/A |
| 0.14.1 | ✅ 200 | rocm700 | `https://wheels.vllm.ai/rocm/0.14.1/rocm700` |
| 0.20.0 | ✅ 200 | rocm721 | `https://wheels.vllm.ai/rocm/0.20.0/rocm721` |
| 0.20.2 | ✅ 200 | rocm721 | `https://wheels.vllm.ai/rocm/0.20.2/rocm721` |
| Nightly | ✅ 200 | rocm721 | `https://wheels.vllm.ai/rocm/nightly/rocm721` |

If the CUDA version has no ROCm wheel (like 0.12.0), use the latest available stable ROCm version (currently `0.20.2+rocm721`). This is acceptable — the CUDA and ROCm versions don't need to match exactly.

### 2. Fork Setup

```bash
# Fork
gh repo fork vllm-project/recipes --clone
# WARNING: This may clone into a directory named 'recipes-AMD' (based on fork name)
# Find it: ls ~/dev/ or find ~ -maxdepth 3 -name ".git" -type d

# Always branch from upstream/main, never from local main (may be stale):
cd <repo-dir>
git remote add upstream https://github.com/vllm-project/recipes
git fetch upstream
git checkout -b feat/<model>-amd upstream/main
```

## Changes to Apply

### 1. YAML Recipe (`models/<hf_org>/<hf_repo>.yaml`)

**`meta.hardware`** — Add after `related_recipes`:

```yaml
meta:
  hardware:
    mi300x: verified
    mi325x: verified
    mi355x: verified
```

Do NOT add `h200: verified` (AMD-only PR).

**`dependencies`** — Add AMD entry with `optional: true`. Do NOT modify existing NVIDIA deps.

Use the **inline `git+https://` pattern** (learned from gemini-code-assist review on PR #451):

```yaml
dependencies:
  - note: "Pin vllm==0.X.Y for <Model>"
    command: "uv pip install vllm==0.X.Y"
    # ^^ existing NVIDIA dep — leave untouched
  - note: "AMD ROCm: install vLLM for ROCm and vLLM-Omni"
    command: "VLLM_OMNI_TARGET_DEVICE=rocm uv pip install git+https://github.com/vllm-project/vllm-omni.git vllm==0.Z.Z+rocmXXX --extra-index-url https://wheels.vllm.ai/rocm/0.Z.Z/rocmXXX"
    optional: true
```

**Key rule:** Use `git+https://github.com/vllm-project/vllm-omni.git` inline — do NOT use `git clone ... && cd vllm-omni && uv pip install -e .`. The inline pattern is simpler and consistent with the NVIDIA section.

**`hardware_overrides`** — Replace `hardware_overrides: {}` with AMD override:

```yaml
hardware_overrides:
  amd:
    extra_env:
      VLLM_OMNI_TARGET_DEVICE: "rocm"
```

If other models already have AMD `extra_env` vars (e.g. Wan2.2 has `VLLM_ROCM_USE_AITER=1`, `SAFETENSORS_FAST_GPU=1`), those were set by a prior PR — leave them and add any that are missing.

**`guide`** — Add AMD install subsection after `## Installation`:

```markdown
  ### AMD ROCm (MI300X, MI325X, MI355X)

  > **Note:** The vLLM wheel for ROCm requires Python 3.12, ROCm X.Y.Z, and glibc >= 2.35.
  > If your environment does not meet these requirements, please use the Docker-based setup.

  ```bash
  uv venv --python 3.12
  source .venv/bin/activate
  VLLM_OMNI_TARGET_DEVICE=rocm uv pip install \
      git+https://github.com/vllm-project/vllm-omni.git \
      vllm==0.Z.Z+rocmXXX \
      --extra-index-url https://wheels.vllm.ai/rocm/0.Z.Z/rocmXXX

  # Extra deps (if needed: soundfile, scipy, diffusers, etc.)
  uv pip install <extra-dep>
  ```
```

**Command readability:** Split the long `uv pip install` command across lines with `\` continuation so each component (env var, git source, vLLM version, index URL) is on its own line. gemini-code-assist flags over-long commands. The YAML `command:` field stays single-line (YAML doesn't support shell continuation), but code blocks in the guide should use multi-line formatting.

### 2. Legacy Markdown (`<ProviderDir>/<Model>.md`)

Add an AMD subsection under installing vLLM-Omni:

```markdown
### AMD ROCm: MI300X, MI325X, MI355X

> **Note:** The vLLM wheel for ROCm requires Python 3.12, ROCm X.Y.Z, and glibc >= 2.35.
> If your environment does not meet these requirements, please use the Docker-based setup.

```bash
uv venv --python 3.12
source .venv/bin/activate
VLLM_OMNI_TARGET_DEVICE=rocm uv pip install \
  git+https://github.com/vllm-project/vllm-omni.git \
  vllm==0.Z.Z+rocmXXX \
  --extra-index-url https://wheels.vllm.ai/rocm/0.Z.Z/rocmXXX

# Extra deps (if needed)
uv pip install <extra-dep>
```
```

## Creating the Draft PR

### PR Body — Use a Temp File (Critical!)

**Do NOT pass inline text to `--body`** — shell escaping will produce literal `\n` characters instead of real newlines. Always write to a temp file first:

```bash
cat > /tmp/pr_body.md << 'BODY_EOF'
## Summary

Add comprehensive AMD MI300X/MI325X/MI355X GPU support for <Model> text-to-<task> generation model, served via vLLM-Omni.

## Changes

- **YAML recipe** (`models/<org>/<model>.yaml`):
  - Add `meta.hardware` entries for `mi300x`, `mi325x`, `mi355x` (all `verified`)
  - Add AMD ROCm dependency with `optional: true` (`vllm==0.Z.Z+rocmXXX` + vLLM-Omni from source)
  - Add `hardware_overrides` for AMD with `VLLM_OMNI_TARGET_DEVICE` env var
  - Add `### AMD ROCm` subsection under Installation guide

- **Legacy markdown** (`<ProviderDir>/<Model>.md`):
  - Add `### AMD ROCm: MI300X, MI325X, MI355X` install subsection

## Notes

- vLLM-Omni model (task: `omni`) — uses offline Python scripts, no `vllm serve` commands
- AMD ROCm install uses vllm stable ROCm wheel (0.Z.Z+rocmXXX)
- Uses `VLLM_OMNI_TARGET_DEVICE=rocm` env var at install time
- Compatible strategies remain `[]` (omni models)
BODY_EOF

gh pr create \
  --repo vllm-project/recipes \
  --base main \
  --head <user>:feat/<model>-amd \
  --draft \
  --title "Add AMD MI300X/MI325X/MI355X support for <Model> recipe" \
  --body-file /tmp/pr_body.md
```

### Commit with DCO Sign-Off

The repo requires DCO (Signed-off-by). Always use `-s`:

```bash
git add models/<org>/<model>.yaml <ProviderDir>/<Model>.md
git commit -s -m "Add AMD MI300X/MI325X/MI355X support for <Model> recipe

- Add meta.hardware with AMD GPU entries
- Add AMD ROCm install dependency with optional: true
- Add hardware_overrides for AMD with VLLM_OMNI_TARGET_DEVICE env var
- Add AMD ROCm subsection in YAML guide and legacy markdown"
```

## Post-Creation: gemini-code-assist Review

After creating the PR, `gemini-code-assist` will post an automated review within ~1-2 minutes. Common issues it flags:

1. **Long command readability (medium priority)** — "The installation command is quite long... splitting it into multiple lines using backslashes would significantly improve readability."
   - **Fix:** Split `uv pip install` across lines with `\` continuation in the guide code blocks (YAML guide + legacy markdown). The YAML `command:` field stays single-line.

2. **`git clone` + `-e .` pattern** — Avoid this. Use inline `git+https://` instead. gemini-code-assist flagged this during PR #451 review (SD3.5 used `git clone && cd && -e .`).

Apply fixes, then:
```bash
git add <files>
git commit -s -m "fix: ... per code review"
git push
```

## Validation Checklist

Before pushing:

- [ ] YAML validates: `python3 -c "import yaml; yaml.safe_load(open('...'))"`
- [ ] `meta.hardware` has `mi300x`, `mi325x`, `mi355x` (all `verified`)
- [ ] AMD dep has `optional: true`
- [ ] `hardware_overrides` has `amd: { extra_env: { VLLM_OMNI_TARGET_DEVICE: "rocm" } }`
- [ ] ROCm wheel URL is correct and returns 200
- [ ] Existing NVIDIA content not modified
- [ ] Install commands use `git+https://` not `git clone`
- [ ] `--python 3.12` used in AMD venv commands
- [ ] Commands split across lines with `\` for readability
- [ ] PR body uses temp file (not inline `--body`)
- [ ] Commit uses `-s` (DCO sign-off)

## Quick Reference: ROCm Wheel URL Patterns

| Model | CUDA vLLM | AMD vLLM | ROCm Tag | Wheel URL |
|---|---|---|---|---|
| Stable Diffusion 3.5 | 0.12.0 (no ROCm wheel) | 0.20.2 | rocm721 | `https://wheels.vllm.ai/rocm/0.20.2/rocm721` |
| Wan2.2 | 0.12.0 (no ROCm wheel) | 0.20.2 | rocm721 | `https://wheels.vllm.ai/rocm/0.20.2/rocm721` |
| Stable Audio Open | 0.14.1 | 0.14.1 | rocm700 | `https://wheels.vllm.ai/rocm/0.14.1/rocm700` |

To list all available vllm ROCm versions:
```bash
curl -sL "https://wheels.vllm.ai/rocm/vllm/" | grep -oE 'vllm-[^"]+\.whl' | sort -V
```
