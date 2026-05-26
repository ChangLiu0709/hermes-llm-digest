#!/usr/bin/env python3
"""
InferenceX AMD PR Scanner for SGLang Cookbook Alignment

Scans recent PRs in SemiAnalysisAI/InferenceX for AMD-related changes
that modify benchmark commands. Cross-references with sgl-cookbook to
identify models that need cookbook alignment.

Usage:
    python3 scan_inferencex_prs.py [--days 7] [--cookbook-path /path/to/sgl-cookbook]

Output: Text report of PRs that need cookbook alignment.
"""

import json
import urllib.request
import re
import sys
import os
from datetime import datetime, timedelta

# --- Configuration ---
INFERENCEX_REPO = "SemiAnalysisAI/InferenceX"
COOKBOOK_REPO = "sgl-project/sgl-cookbook"
AMD_KEYWORDS = ['mi300x', 'mi325x', 'mi355x', 'mi35x']
BENCHMARK_FILE_PATTERN = re.compile(r'benchmarks/single_node/.*\.sh$')
SKIP_TITLE_PATTERNS = [
    r'runner', r'revert', r'docker-tag-monitor', r'nodelist',
    r'--exclude', r'klaud-pr-status', r'perf-changelog',
]
MODEL_FROM_FILE = re.compile(
    r'benchmarks/single_node/(?:agentic/)?(.+?)_(?:fp[48]|bf16|int[48]|mxfp4)_(?:mi3[0-9]+x|mi35x)'
)

# InferenceX model slug -> cookbook ConfigGenerator name
MODEL_NAME_MAP = {
    'glm5': 'GLM5',
    'glm47flash': 'GLM47Flash',
    'glm4.7flash': 'GLM47Flash',
    'qwen3.5': 'Qwen36',
    'qwen35': 'Qwen36',
    'dsr1': 'DeepSeekR1',
    'dsv4': 'DeepSeek',
    'dsv3': 'DeepSeekV3',
    'mimo': 'MiMo',
    'minimaxm2.5': 'MiniMaxM25',
    'minimaxm25': 'MiniMaxM25',
    'gptoss': 'GptOss',
    'mistralsmall4': 'MistralSmall4',
    'interns1': 'InternS1',
    'kimik2.5': 'KimiK25',
    'kimik25': 'KimiK25',
}


def github_api(path):
    url = f"https://api.github.com/{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "sglang-auto-cookbook-scanner"})
    try:
        return json.loads(urllib.request.urlopen(req).read())
    except urllib.error.HTTPError as e:
        print(f"  [WARN] GitHub API error for {url}: {e.code}", file=sys.stderr)
        return None


def get_recent_amd_prs(days=7):
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    prs = []
    page = 1
    while True:
        data = github_api(
            f"repos/{INFERENCEX_REPO}/pulls?state=all&sort=created&direction=desc&per_page=50&page={page}"
        )
        if not data:
            break
        for pr in data:
            if pr['created_at'] < since:
                return prs
            title_lower = pr['title'].lower()
            branch_lower = pr['head']['ref'].lower()
            is_amd = any(kw in title_lower or kw in branch_lower for kw in AMD_KEYWORDS)
            if not is_amd:
                continue
            skip = any(re.search(p, title_lower) for p in SKIP_TITLE_PATTERNS)
            if skip:
                continue
            prs.append({
                'number': pr['number'],
                'title': pr['title'],
                'state': pr['state'],
                'merged': pr.get('merged_at') is not None,
                'branch': pr['head']['ref'],
                'created': pr['created_at'][:10],
                'url': pr['html_url'],
            })
        page += 1
        if len(data) < 50:
            break
    return prs


def extract_model_and_gpu(filename):
    m = MODEL_FROM_FILE.search(filename)
    if not m:
        return None, None
    model_slug = m.group(1).lower().replace('-', '').replace('_', '')
    gpu_match = re.search(r'(mi300x|mi325x|mi355x|mi35x)', filename.lower())
    gpu = gpu_match.group(1) if gpu_match else None
    if gpu == 'mi35x':
        gpu = 'mi355x'
    return model_slug, gpu


def check_cookbook_has_gpu(model_slug, gpu, cookbook_path=None):
    clean_slug = model_slug.lower().replace('-', '').replace('_', '')
    config_gen_name = MODEL_NAME_MAP.get(clean_slug)
    if not config_gen_name:
        for key, val in MODEL_NAME_MAP.items():
            if key in clean_slug or clean_slug in key:
                config_gen_name = val
                break
    if not config_gen_name:
        return None, f"Unknown model mapping for '{model_slug}'"
    if cookbook_path:
        js_path = os.path.join(
            cookbook_path,
            f"src/components/autoregressive/{config_gen_name}ConfigGenerator/index.js"
        )
        if os.path.exists(js_path):
            with open(js_path) as f:
                content = f.read()
            return gpu in content, config_gen_name
        else:
            return None, f"ConfigGenerator not found: {config_gen_name}"
    data = github_api(
        f"repos/{COOKBOOK_REPO}/contents/src/components/autoregressive/{config_gen_name}ConfigGenerator/index.js"
    )
    if not data or 'content' not in data:
        return None, f"ConfigGenerator not found: {config_gen_name}"
    import base64
    content = base64.b64decode(data['content']).decode('utf-8')
    return gpu in content, config_gen_name


def scan(days=7, cookbook_path=None):
    print(f"Scanning InferenceX PRs from the last {days} days...")
    print(f"Cookbook path: {cookbook_path or '(GitHub API)'}")
    print()

    prs = get_recent_amd_prs(days=days)
    print(f"Found {len(prs)} AMD-related PRs (after filtering infrastructure PRs)")
    print()

    actionable = []

    for pr in prs:
        files = github_api(f"repos/{INFERENCEX_REPO}/pulls/{pr['number']}/files?per_page=100")
        if not files:
            continue
        benchmark_files = [f for f in files if BENCHMARK_FILE_PATTERN.match(f['filename'])]
        if not benchmark_files:
            continue

        print(f"#{pr['number']} [{pr['state']}] {pr['title']}")

        for bf in benchmark_files:
            model_slug, gpu = extract_model_and_gpu(bf['filename'])
            if not model_slug or not gpu:
                print(f"  ? Could not parse: {bf['filename']}")
                continue
            has_gpu, config_name = check_cookbook_has_gpu(model_slug, gpu, cookbook_path)
            if has_gpu is None:
                symbol, status = "?", "UNKNOWN"
            elif has_gpu:
                symbol, status = "✓", "ALREADY_IN_COOKBOOK"
            else:
                symbol, status = "✗", "NEEDS_ALIGNMENT"
            print(f"  {symbol} {bf['filename']}")
            print(f"    model={model_slug}, gpu={gpu}, cookbook={config_name}, status={status}")
            if status == "NEEDS_ALIGNMENT":
                actionable.append({
                    'pr_number': pr['number'], 'pr_title': pr['title'],
                    'pr_state': pr['state'], 'pr_merged': pr['merged'],
                    'pr_url': pr['url'], 'pr_branch': pr['branch'],
                    'benchmark_file': bf['filename'],
                    'model_slug': model_slug, 'gpu': gpu,
                    'cookbook_config_gen': config_name,
                })
        print()

    print("=" * 60)
    print(f"ACTIONABLE: {len(actionable)} benchmark(s) need cookbook alignment")
    print("=" * 60)

    seen = set()
    for item in actionable:
        key = f"{item['cookbook_config_gen']}+{item['gpu']}"
        if key in seen:
            continue
        seen.add(key)
        merged_str = "MERGED" if item['pr_merged'] else item['pr_state'].upper()
        print(f"\n  Model: {item['cookbook_config_gen']} | GPU: {item['gpu']} | Status: {merged_str}")
        print(f"  InferenceX PR: #{item['pr_number']} - {item['pr_title']}")
        print(f"  Benchmark: {item['benchmark_file']}")
        print(f"  URL: {item['pr_url']}")

    if not actionable:
        print("\n  (none - cookbook is up to date with recent InferenceX AMD PRs)")

    return actionable


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Scan InferenceX PRs for cookbook alignment')
    parser.add_argument('--days', type=int, default=7, help='Look back N days (default: 7)')
    parser.add_argument('--cookbook-path', type=str, default=None,
                        help='Local path to sgl-cookbook repo')
    parser.add_argument('--json', action='store_true', help='Output JSON')
    args = parser.parse_args()

    results = scan(days=args.days, cookbook_path=args.cookbook_path)
    if args.json:
        print(json.dumps(results, indent=2))
