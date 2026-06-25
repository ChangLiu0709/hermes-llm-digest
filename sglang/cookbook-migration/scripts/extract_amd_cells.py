#!/usr/bin/env python3
"""Extract AMD cells from a SGLang cookbook config JSX file.

Parses the config's `cells` array and `modelNames` map to reconstruct
runnable `sglang serve` commands for MI300X / MI355X hardware.

Usage:
    # From a local file:
    python3 extract_amd_cells.py /tmp/deepseek-v4.jsx --hw mi300x

    # Fetch from GitHub and pipe:
    curl -sL "https://api.github.com/repos/sgl-project/sglang/contents/\
docs_new/src/snippets/configs/deepseek-ai/deepseek-v4.jsx" \
      -H "Accept: application/vnd.github.v3.raw" | python3 extract_amd_cells.py - --hw mi300x

    # Also extract benchmark stubs:
    python3 extract_amd_cells.py /tmp/model.jsx --hw mi300x --benchmarks /tmp/model-benchmarks.jsx

    # Write individual shell scripts:
    python3 extract_amd_cells.py /tmp/model.jsx --hw mi300x --scripts-dir /tmp/scripts/

Output: prints reconstructed commands grouped by (variant, quant, strategy).
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict


def find_balanced(text: str, start: int, opener: str = '{', closer: str = '}') -> int:
    """Find the index of the closing bracket that matches the opener at `start`."""
    depth = 0
    i = start
    while i < len(text):
        if text[i] == opener:
            depth += 1
        elif text[i] == closer:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def extract_cells_text(jsx_text: str) -> str:
    """Extract the cells array text from the JSX config."""
    # Find `cells:` or `cells :` followed by `[`
    m = re.search(r'\bcells\s*:\s*\[', jsx_text)
    if not m:
        return ""
    bracket_start = m.end() - 1  # position of [
    bracket_end = find_balanced(jsx_text, bracket_start, '[', ']')
    if bracket_end == -1:
        return ""
    return jsx_text[bracket_start:bracket_end + 1]


def parse_cell(cell_text: str) -> dict:
    """Parse a single cell object text into a dict."""
    cell = {"match": {}, "verified": False, "env": [], "flags": []}

    # Extract match
    m = re.search(r'match\s*:\s*\{([^}]+)\}', cell_text)
    if m:
        for kv in re.finditer(r'(\w+)\s*:\s*"([^"]+)"', m.group(1)):
            cell["match"][kv.group(1)] = kv.group(2)

    # Extract verified
    m = re.search(r'verified\s*:\s*(true|false)', cell_text)
    if m:
        cell["verified"] = m.group(1) == "true"

    # Extract env array
    m = re.search(r'env\s*:\s*\[([^\]]*)\]', cell_text)
    if m:
        cell["env"] = [s.strip().strip('"').strip("'")
                       for s in re.findall(r'"([^"]*)"', m.group(1))]

    # Extract flags array - need to handle multi-line
    m = re.search(r'flags\s*:\s*\[', cell_text)
    if m:
        bracket_start = m.end() - 1
        bracket_end = find_balanced(cell_text, bracket_start, '[', ']')
        if bracket_end > 0:
            flags_text = cell_text[bracket_start:bracket_end + 1]
            cell["flags"] = [s for s in re.findall(r'"([^"]*)"', flags_text)]

    return cell


def parse_all_cells(jsx_text: str) -> list:
    """Parse all cells from the JSX config."""
    cells_text = extract_cells_text(jsx_text)
    if not cells_text:
        return []

    cells = []
    # Find each cell object by matching balanced braces
    i = 0
    while i < len(cells_text):
        if cells_text[i] == '{':
            end = find_balanced(cells_text, i)
            if end > 0:
                cell_text = cells_text[i:end + 1]
                cell = parse_cell(cell_text)
                if cell["match"]:  # Only add if we got a valid match
                    cells.append(cell)
                i = end + 1
                continue
        i += 1

    return cells


def parse_model_names(jsx_text: str) -> dict:
    """Extract the modelNames map from JSX config."""
    m = re.search(r'modelNames\s*:\s*\{', jsx_text)
    if not m:
        return {}
    brace_start = m.end() - 1
    brace_end = find_balanced(jsx_text, brace_start)
    if brace_end == -1:
        return {}
    mn_text = jsx_text[brace_start:brace_end + 1]
    names = {}
    for kv in re.finditer(r'"([^"]+)"\s*:\s*"([^"]+)"', mn_text):
        names[kv.group(1)] = kv.group(2)
    return names


def parse_docker_images(jsx_text: str) -> dict:
    """Extract dockerImages map."""
    m = re.search(r'dockerImages\s*:\s*\{', jsx_text)
    if not m:
        return {}
    brace_start = m.end() - 1
    brace_end = find_balanced(jsx_text, brace_start)
    if brace_end == -1:
        return {}
    di_text = jsx_text[brace_start:brace_end + 1]
    images = {}
    for kv in re.finditer(r'(\w+)\s*:\s*"([^"]+)"', di_text):
        images[kv.group(1)] = kv.group(2)
    return images


def parse_model_name(jsx_text: str) -> str:
    """Extract modelName field."""
    m = re.search(r'modelName\s*:\s*"([^"]+)"', jsx_text)
    return m.group(1) if m else "unknown"


def parse_benchmark_stubs(bench_text: str, hw_filter: str) -> set:
    """Parse benchmark file to find stub entries (match-only, no speed data)."""
    stubs = set()
    # Stub entries look like: { match: { ... } },  (no speed/accuracy keys)
    # We find all match blocks, then check if that entry has speed data
    for m in re.finditer(r'\{[^{}]*match\s*:\s*\{([^}]+)\}[^{}]*\}', bench_text):
        full = m.group(0)
        match_str = m.group(1)
        match = {}
        for kv in re.finditer(r'(\w+)\s*:\s*"([^"]+)"', match_str):
            match[kv.group(1)] = kv.group(2)
        if match.get("hw") == hw_filter:
            has_speed = "speed:" in full or "sglang_version:" in full
            if not has_speed:
                key = (match.get("variant", ""), match.get("quant", ""),
                       match.get("strategy", ""), match.get("nodes", ""))
                stubs.add(key)
    return stubs


def resolve_model_name(model_names: dict, hw: str, variant: str, quant: str) -> str:
    """Resolve HF model name: try hw|variant|quant, fall back to variant|quant."""
    key_hw = f"{hw}|{variant}|{quant}"
    key_generic = f"{variant}|{quant}"
    return model_names.get(key_hw, model_names.get(key_generic, "{{MODEL_NAME}}"))


def build_command(cell: dict, model_name: str, port: int = 30000) -> str:
    """Build a runnable sglang serve command from a cell."""
    parts = []

    # Environment variables
    if cell["env"]:
        parts.append(" ".join(cell["env"]))

    parts.append("sglang serve")

    # Flags (resolve placeholders)
    for flag in cell["flags"]:
        resolved = flag.replace("{{MODEL_NAME}}", model_name)
        resolved = resolved.replace("{{HOST_IP}}", "0.0.0.0")
        resolved = resolved.replace("{{PORT}}", str(port))
        parts.append(f"  {resolved}")

    return " \\\n".join(parts)


def build_docker_env_flags(cell: dict) -> str:
    """Build -e flags for docker run from cell env vars."""
    return " ".join(f"-e {e}" for e in cell["env"])


def main():
    parser = argparse.ArgumentParser(
        description="Extract AMD cells from SGLang cookbook config JSX")
    parser.add_argument("config_file",
                        help="Path to config JSX file (or - for stdin)")
    parser.add_argument("--hw", default="mi300x",
                        choices=["mi300x", "mi325x", "mi355x"],
                        help="Hardware to filter for (default: mi300x)")
    parser.add_argument("--benchmarks",
                        help="Path to benchmarks JSX file (to show stub status)")
    parser.add_argument("--port", type=int, default=30000,
                        help="Server port (default: 30000)")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON instead of shell commands")
    parser.add_argument("--scripts-dir",
                        help="Write individual .sh scripts to this directory")
    args = parser.parse_args()

    # Read config
    if args.config_file == "-":
        jsx_text = sys.stdin.read()
    else:
        with open(args.config_file) as f:
            jsx_text = f.read()

    model_name_display = parse_model_name(jsx_text)
    model_names = parse_model_names(jsx_text)
    docker_images = parse_docker_images(jsx_text)
    cells = parse_all_cells(jsx_text)

    # Filter for target hardware
    amd_cells = [c for c in cells if c["match"].get("hw") == args.hw]

    if not amd_cells:
        print(f"No cells found for hardware '{args.hw}'")
        sys.exit(1)

    # Parse benchmark stubs if provided
    bench_stubs = set()
    if args.benchmarks:
        with open(args.benchmarks) as f:
            bench_text = f.read()
        bench_stubs = parse_benchmark_stubs(bench_text, args.hw)

    # Docker image
    docker_image = docker_images.get(args.hw, "lmsysorg/sglang-rocm:latest")

    print(f"# {model_name_display} — {args.hw.upper()} cells")
    print(f"# Docker image: {docker_image}")
    print(f"# Found {len(amd_cells)} cells")
    print()

    json_output = {
        "model": model_name_display,
        "hardware": args.hw,
        "docker_image": docker_image,
        "cells": []
    } if args.json else None

    # Group by variant+quant
    groups = defaultdict(list)
    for cell in amd_cells:
        m = cell["match"]
        key = (m.get("variant", ""), m.get("quant", ""))
        groups[key].append(cell)

    for (variant, quant), group_cells in sorted(groups.items()):
        hf_model = resolve_model_name(model_names, args.hw, variant, quant)
        print(f"# === {variant} / {quant} → {hf_model} ===")
        print()

        for cell in group_cells:
            m = cell["match"]
            strategy = m.get("strategy", "unknown")
            nodes = m.get("nodes", "single")
            verified_mark = "✓" if cell["verified"] else "✗"

            # Check if benchmark stub exists
            bench_key = (variant, quant, strategy, nodes)
            bench_status = " [BENCHMARK STUB — needs data]" if bench_key in bench_stubs else ""

            print(f"# --- {strategy} / {nodes} [verified: {verified_mark}]{bench_status}")
            cmd = build_command(cell, hf_model, args.port)
            print(cmd)
            print()

            if json_output is not None:
                json_output["cells"].append({
                    "match": cell["match"],
                    "verified": cell["verified"],
                    "hf_model": hf_model,
                    "command": cmd,
                    "docker_env_flags": build_docker_env_flags(cell),
                })

            # Write individual script
            if args.scripts_dir:
                os.makedirs(args.scripts_dir, exist_ok=True)
                script_name = f"{args.hw}_{variant}_{quant}_{strategy}_{nodes}.sh"
                script_path = os.path.join(args.scripts_dir, script_name)
                with open(script_path, "w") as sf:
                    sf.write("#!/bin/bash\n")
                    sf.write(f"# {model_name_display} — {args.hw} / {variant} / {quant} / {strategy}\n")
                    sf.write(f"# Docker image: {docker_image}\n")
                    sf.write(f"# Docker env: {build_docker_env_flags(cell)}\n\n")
                    sf.write(cmd + "\n")
                os.chmod(script_path, 0o755)

    # Print concurrency sweep reference
    print()
    print("# === Concurrency Sweep Reference ===")
    print("# Strategy        | Concurrency | num_prompts")
    print("# low-latency     |    1        |   64")
    print("# low-latency     |   16        |  256")
    print("# balanced        |   64        |  512")
    print("# balanced        |  256        | 1024")
    print("# high-throughput | 1024        | 2048")
    print("# high-throughput | 4096        | 4096")
    print("#")
    print("# Workload: --dataset-name random --random-input-len 8192 --random-output-len 1024")
    print("# Add: --warmup-requests 64")

    if json_output is not None:
        print()
        print(json.dumps(json_output, indent=2))


if __name__ == "__main__":
    main()
