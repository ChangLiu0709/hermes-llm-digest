---
name: vllm-daily-digest
description: "Daily vLLM digest + weekly AMD vs NVIDIA competitive intelligence from vllm-project/vllm: issues, PRs, releases, blog posts, and strategic recommendations."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [vllm, github, daily-digest, issues, pull-requests, releases, blog, amd, nvidia, competitive-intelligence]
    related_skills: [vllm-pr-tracker]
---

# vLLM Daily Digest + AMD Competitive Intelligence

## Overview

Collects a daily summary of activity from the [vLLM GitHub repository](https://github.com/vllm-project/vllm), releases, and blog posts from [vllm.ai/blog](https://vllm.ai/blog).

On top of the daily digest, the skill includes a **weekly AMD competitive intelligence section** that:
1. Summarises AMD-related activity (issues, PRs, releases) from the past 7 days
2. Summarises NVIDIA-related activity from the same period
3. Provides strategic recommendations for AMD to close gaps and surpass NVIDIA

The digest is designed for **Telegram delivery** — compact, scannable, and formatted with Markdown.

## When to Use

- User asks for vLLM daily updates or digest
- User wants to track vLLM repo activity
- User wants AMD vs NVIDIA competitive analysis in the vLLM ecosystem
- Scheduled via cron job for automated daily reports
- User asks "what's new in vLLM?"

## Data Sources

- **GitHub Issues & PRs**: `https://api.github.com/repos/vllm-project/vllm`
  - No auth required for public repos (60 req/hour unauthenticated)
  - Set `GITHUB_TOKEN` for higher rate limits (5000 req/hour)
- **GitHub Releases**: `https://api.github.com/repos/vllm-project/vllm/releases`
- **Blog RSS**: `https://vllm.ai/blog/rss.xml`

## Collection Script

Run this as a single Python script via execute_code or terminal. It outputs the formatted daily digest AND the raw weekly AMD/NVIDIA data for the agent to analyse.

```python
import json, subprocess, sys, re
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET

REPO = "vllm-project/vllm"
API = f"https://api.github.com/repos/{REPO}"
now_utc = datetime.now(timezone.utc)
cutoff_24h = now_utc - timedelta(hours=24)
cutoff_7d = now_utc - timedelta(days=7)
cutoff_24h_iso = cutoff_24h.strftime("%Y-%m-%dT%H:%M:%SZ")
cutoff_7d_iso = cutoff_7d.strftime("%Y-%m-%dT%H:%M:%SZ")
today = datetime.now()

def fetch(url):
    token = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()
    headers = ["-H", f"Authorization: token {token}"] if token else []
    r = subprocess.run(["curl", "-s"] + headers + [url], capture_output=True, text=True)
    if not r.stdout.strip():
        return []
    try:
        data = json.loads(r.stdout)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "message" in data:
            print(f"  API ERROR: {data['message']}", file=sys.stderr)
        return []
    except json.JSONDecodeError:
        return []

def fetch_pages(url_template, max_pages=3):
    all_items = []
    for page in range(1, max_pages + 1):
        url = f"{url_template}&page={page}&per_page=100"
        items = fetch(url)
        if not items:
            break
        all_items.extend(items)
    return all_items

def parse_dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

def parse_rss_date(s):
    # Parse RFC 2822 date
    months = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
              "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
    parts = s.replace(",","").split()
    if len(parts) >= 5:
        day = int(parts[1])
        month = months.get(parts[2], 1)
        year = int(parts[3])
        time_parts = parts[4].split(":")
        hour, minute, second = int(time_parts[0]), int(time_parts[1]), int(time_parts[2])
        return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    return now_utc

# ══════════════════════════════════════════════════════════
# AMD / NVIDIA KEYWORDS
# ══════════════════════════════════════════════════════════

AMD_KEYWORDS = [
    "amd", "rocm", "mi300", "mi350", "mi355", "mi30x", "mi35x", "mi325",
    "hip ", "hipblas", "instinct", "gfx9", "gfx10", "gfx11", "gfx12",
    "aiter", "radeon", "rdna", "cdna", "xdna", "ck_tile",
    "rocm_smi", "hipify", "composable_kernel", "rccl",
]

NVIDIA_KEYWORDS = [
    "nvidia", "cuda", "nccl", "tensorrt", "cutlass", "cublas", "cudnn",
    "a100", "h100", "h200", "b200", "gb200", "gb300",
    "hopper", "blackwell", "sm_", "nvcc", "nvshmem",
    "flashinfer", "thrust", "cub ",
]

def matches_keywords(item, keywords):
    title = item.get("title", "").lower()
    body_preview = (item.get("body", "") or "")[:500].lower()
    labels = " ".join(l["name"].lower() for l in item.get("labels", []))
    text = f"{title} {labels} {body_preview}"
    return any(kw in text for kw in keywords)

# ══════════════════════════════════════════════════════════
# PART 1: DAILY DIGEST (last 24h)
# ══════════════════════════════════════════════════════════

# New issues
raw = fetch(f"{API}/issues?state=open&since={cutoff_24h_iso}&sort=created&direction=desc&per_page=100")
new_issues = [i for i in raw if "pull_request" not in i and parse_dt(i["created_at"]) >= cutoff_24h]
new_issues.sort(key=lambda i: (-i.get("comments", 0),))

# Closed issues
raw = fetch(f"{API}/issues?state=closed&since={cutoff_24h_iso}&sort=updated&direction=desc&per_page=100")
closed_issues = [i for i in raw if "pull_request" not in i and i.get("closed_at") and parse_dt(i["closed_at"]) >= cutoff_24h]
closed_issues.sort(key=lambda i: (-i.get("comments", 0),))

# New PRs
raw = fetch(f"{API}/pulls?state=open&sort=created&direction=desc&per_page=100")
new_prs = [p for p in raw if parse_dt(p["created_at"]) >= cutoff_24h]
new_prs.sort(key=lambda p: (-(p.get("comments", 0) + p.get("review_comments", 0)),))

# Merged PRs
raw = fetch(f"{API}/pulls?state=closed&sort=updated&direction=desc&per_page=100")
merged_prs = [p for p in raw if p.get("merged_at") and parse_dt(p["merged_at"]) >= cutoff_24h]
merged_prs.sort(key=lambda p: (-(p.get("comments", 0) + p.get("review_comments", 0)),))

# Releases
raw = fetch(f"{API}/releases?per_page=5")
recent_releases = [r for r in raw if r.get("published_at") and parse_dt(r["published_at"]) >= cutoff_24h]

# Blog posts from RSS
rss_xml = subprocess.run(["curl", "-sL", "https://vllm.ai/blog/rss.xml"], capture_output=True, text=True).stdout
blog_posts_24h = []
blog_posts_7d = []
try:
    root = ET.fromstring(rss_xml)
    for item in root.findall(".//item"):
        title = item.findtext("title", "")
        link = item.findtext("link", "")
        pub_date = item.findtext("pubDate", "")
        desc = item.findtext("description", "")
        dt = parse_rss_date(pub_date)
        if dt >= cutoff_24h:
            blog_posts_24h.append({"title": title, "link": link, "date": pub_date, "description": desc})
        if dt >= cutoff_7d:
            blog_posts_7d.append({"title": title, "link": link, "date": pub_date, "description": desc})
except ET.ParseError:
    pass

# ── Format daily digest ───────────────────────────────────

day_name = today.strftime("%A")
date_str = today.strftime("%b %d, %Y")
total_activity = len(new_issues) + len(closed_issues) + len(new_prs) + len(merged_prs)

if total_activity >= 80:
    activity = "🔥 Very busy day"
elif total_activity >= 40:
    activity = "📈 Active day"
elif total_activity >= 10:
    activity = "📊 Normal day"
else:
    activity = "🌤 Quiet day"

lines = []
lines.append(f"📋 *vLLM Daily Digest*")
lines.append(f"_{day_name}, {date_str}_")
lines.append("")
lines.append(f"{activity} — {total_activity} total updates")
lines.append(f"🆕 {len(new_issues)} new issues · ✅ {len(closed_issues)} closed · 🔀 {len(new_prs)} new PRs · 🟣 {len(merged_prs)} merged")
if recent_releases:
    for r in recent_releases:
        lines.append(f"📦 [{r['tag_name']}]({r['html_url']}) — {r['name']}")
lines.append("")

# New Issues
lines.append(f"━━━ 🆕 New Issues ({len(new_issues)} total) ━━━")
if new_issues:
    for i in new_issues[:5]:
        num = i["number"]
        title = i["title"]
        comments = i.get("comments", 0)
        labels = [l["name"] for l in i.get("labels", [])]
        label_str = ""
        if labels:
            label_tags = " ".join(f"`{l}`" for l in labels[:3])
            label_str = f"  {label_tags}"
        comment_str = f"  💬{comments}" if comments > 0 else ""
        lines.append(f"  • [#{num}]({i['html_url']}) {title}{comment_str}{label_str}")
    if len(new_issues) > 5:
        lines.append(f"  _…and {len(new_issues) - 5} more_")
else:
    lines.append("  _No new issues_")
lines.append("")

# Closed Issues
lines.append(f"━━━ ✅ Closed Issues ({len(closed_issues)} total) ━━━")
if closed_issues:
    for i in closed_issues[:5]:
        num = i["number"]
        title = i["title"]
        comments = i.get("comments", 0)
        comment_str = f"  💬{comments}" if comments > 0 else ""
        lines.append(f"  • [#{num}]({i['html_url']}) {title}{comment_str}")
    if len(closed_issues) > 5:
        lines.append(f"  _…and {len(closed_issues) - 5} more_")
else:
    lines.append("  _No closed issues_")
lines.append("")

# New PRs
lines.append(f"━━━ 🔀 New Pull Requests ({len(new_prs)} total) ━━━")
if new_prs:
    for p in new_prs[:5]:
        num = p["number"]
        title = p["title"]
        total_comments = p.get("comments", 0) + p.get("review_comments", 0)
        labels = [l["name"] for l in p.get("labels", [])]
        label_str = ""
        if labels:
            label_tags = " ".join(f"`{l}`" for l in labels[:3])
            label_str = f"  {label_tags}"
        comment_str = f"  💬{total_comments}" if total_comments > 0 else ""
        lines.append(f"  • [#{num}]({p['html_url']}) {title}{comment_str}{label_str}")
    if len(new_prs) > 5:
        lines.append(f"  _…and {len(new_prs) - 5} more_")
else:
    lines.append("  _No new PRs_")
lines.append("")

# Merged PRs
lines.append(f"━━━ 🟣 Merged Pull Requests ({len(merged_prs)} total) ━━━")
if merged_prs:
    for p in merged_prs[:5]:
        num = p["number"]
        title = p["title"]
        total_comments = p.get("comments", 0) + p.get("review_comments", 0)
        comment_str = f"  💬{total_comments}" if total_comments > 0 else ""
        lines.append(f"  • [#{num}]({p['html_url']}) {title}{comment_str}")
    if len(merged_prs) > 5:
        lines.append(f"  _…and {len(merged_prs) - 5} more_")
else:
    lines.append("  _No merged PRs_")
lines.append("")

# Blog Posts
if blog_posts_24h:
    lines.append(f"━━━ 📝 Recent Blog Posts ━━━")
    for p in blog_posts_24h[:3]:
        lines.append(f"  • [{p['title']}]({p['link']}) — _{p['date']}_")
    lines.append("")

# Footer
lines.append(f"🔗 [Open repo](https://github.com/{REPO}) · [Issues](https://github.com/{REPO}/issues) · [PRs](https://github.com/{REPO}/pulls) · [Blog](https://vllm.ai/blog)")

print("\n".join(lines))

# ══════════════════════════════════════════════════════════
# PART 2: WEEKLY AMD vs NVIDIA RAW DATA (last 7 days)
# ══════════════════════════════════════════════════════════

print("\n\n" + "=" * 60)
print("WEEKLY COMPETITIVE INTELLIGENCE RAW DATA (last 7 days)")
print("=" * 60)

# Collect 7-day issues
all_issues_7d = []
raw = fetch_pages(f"{API}/issues?state=all&since={cutoff_7d_iso}&sort=updated&direction=desc")
all_issues_7d = [i for i in raw if "pull_request" not in i]

# Collect 7-day PRs
all_prs_open_7d = fetch_pages(f"{API}/pulls?state=open&sort=created&direction=desc")
all_prs_open_7d = [p for p in all_prs_open_7d if parse_dt(p["created_at"]) >= cutoff_7d]

all_prs_closed_7d = fetch_pages(f"{API}/pulls?state=closed&sort=updated&direction=desc")
all_prs_closed_7d = [p for p in all_prs_closed_7d if p.get("merged_at") and parse_dt(p["merged_at"]) >= cutoff_7d]

all_prs_7d = all_prs_open_7d + all_prs_closed_7d

# Releases 7d
releases_7d = [r for r in fetch(f"{API}/releases?per_page=10") if r.get("published_at") and parse_dt(r["published_at"]) >= cutoff_7d]

# Filter AMD items
amd_issues = [i for i in all_issues_7d if matches_keywords(i, AMD_KEYWORDS)]
amd_prs = [p for p in all_prs_7d if matches_keywords(p, AMD_KEYWORDS)]
amd_releases = [r for r in releases_7d if any(kw in (r.get("name","") + " " + r.get("body","")).lower() for kw in AMD_KEYWORDS)]
amd_blogs = [p for p in blog_posts_7d if any(kw in (p["title"] + " " + p["description"]).lower() for kw in AMD_KEYWORDS)]

# Filter NVIDIA items
nvidia_issues = [i for i in all_issues_7d if matches_keywords(i, NVIDIA_KEYWORDS)]
nvidia_prs = [p for p in all_prs_7d if matches_keywords(p, NVIDIA_KEYWORDS)]
nvidia_releases = [r for r in releases_7d if any(kw in (r.get("name","") + " " + r.get("body","")).lower() for kw in NVIDIA_KEYWORDS)]
nvidia_blogs = [p for p in blog_posts_7d if any(kw in (p["title"] + " " + p["description"]).lower() for kw in NVIDIA_KEYWORDS)]

print(f"\n--- AMD ACTIVITY ({len(amd_issues)} issues, {len(amd_prs)} PRs, {len(amd_releases)} releases, {len(amd_blogs)} blog posts) ---")
print("\nAMD Issues:")
for i in amd_issues:
    state = "OPEN" if i["state"] == "open" else "CLOSED"
    labels = ", ".join(l["name"] for l in i.get("labels", []))
    print(f"  [{state}] #{i['number']} {i['title']}  (💬{i.get('comments',0)}) [{labels}]")
    print(f"    {i['html_url']}")

print("\nAMD PRs:")
for p in amd_prs:
    state = "MERGED" if p.get("merged_at") else "OPEN"
    labels = ", ".join(l["name"] for l in p.get("labels", []))
    print(f"  [{state}] #{p['number']} {p['title']}  (💬{p.get('comments',0)+p.get('review_comments',0)}) [{labels}]")
    print(f"    {p['html_url']}")

if amd_releases:
    print("\nAMD Releases:")
    for r in amd_releases:
        print(f"  {r['tag_name']} — {r.get('name','')}")
        print(f"    {r['html_url']}")

if amd_blogs:
    print("\nAMD Blog Posts:")
    for p in amd_blogs:
        print(f"  {p['date']} — {p['title']}")
        print(f"    {p['link']}")

print(f"\n--- NVIDIA ACTIVITY ({len(nvidia_issues)} issues, {len(nvidia_prs)} PRs, {len(nvidia_releases)} releases, {len(nvidia_blogs)} blog posts) ---")
print("\nNVIDIA Issues:")
for i in nvidia_issues:
    state = "OPEN" if i["state"] == "open" else "CLOSED"
    labels = ", ".join(l["name"] for l in i.get("labels", []))
    print(f"  [{state}] #{i['number']} {i['title']}  (💬{i.get('comments',0)}) [{labels}]")
    print(f"    {i['html_url']}")

print("\nNVIDIA PRs:")
for p in nvidia_prs:
    state = "MERGED" if p.get("merged_at") else "OPEN"
    labels = ", ".join(l["name"] for l in p.get("labels", []))
    print(f"  [{state}] #{p['number']} {p['title']}  (💬{p.get('comments',0)+p.get('review_comments',0)}) [{labels}]")
    print(f"    {p['html_url']}")

if nvidia_releases:
    print("\nNVIDIA Releases:")
    for r in nvidia_releases:
        print(f"  {r['tag_name']} — {r.get('name','')}")
        print(f"    {r['html_url']}")

if nvidia_blogs:
    print("\nNVIDIA Blog Posts:")
    for p in nvidia_blogs:
        print(f"  {p['date']} — {p['title']}")
        print(f"    {p['link']}")

print(f"\n--- VOLUME COMPARISON ---")
print(f"AMD:    {len(amd_issues)} issues, {len(amd_prs)} PRs, {len(amd_releases)} releases, {len(amd_blogs)} blogs = {len(amd_issues)+len(amd_prs)+len(amd_releases)+len(amd_blogs)} total")
print(f"NVIDIA: {len(nvidia_issues)} issues, {len(nvidia_prs)} PRs, {len(nvidia_releases)} releases, {len(nvidia_blogs)} blogs = {len(nvidia_issues)+len(nvidia_prs)+len(nvidia_releases)+len(nvidia_blogs)} total")
print("=" * 60)
```

## Agent Instructions for the Weekly Section

After running the collection script, you will see two parts of output:

1. **PART 1** (before the `====` line): The formatted daily digest. Output this directly as-is.

2. **PART 2** (after the `WEEKLY COMPETITIVE INTELLIGENCE RAW DATA` header): Raw AMD and NVIDIA items from the past 7 days. **Do NOT output this raw data.** Instead, analyse it and write a weekly competitive intelligence section formatted as below.

### How to Write the Weekly Section

Append the following section AFTER the daily digest:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 *Weekly AMD vs NVIDIA Intel*
_Week of {date range}_

📊 *Activity Volume*
AMD: X issues, Y PRs, Z releases, W blogs
NVIDIA: X issues, Y PRs, Z releases, W blogs

🔴 *AMD This Week*
{2-4 bullet points summarising the main themes from AMD issues/PRs/blogs. Group by topic — e.g. "FP8 kernel optimisation", "ROCm CI/testing", "multi-GPU support". Mention specific PR/issue numbers for the most impactful items.}

🟢 *NVIDIA This Week*
{2-4 bullet points summarising the main themes from NVIDIA issues/PRs/blogs. Same grouping approach.}

⚔️ *Competitive Gaps & Opportunities*
{2-3 bullet points identifying where NVIDIA is ahead and AMD has gaps — based on what the issues/PRs reveal. Be specific.}

💡 *Strategic Recommendations for AMD*
{3-4 actionable bullet points. Each should be concrete and tied to the data.}
```

### Writing Guidelines

- **Be specific, not generic.** "Improve ROCm support" is useless. "Port FlashInfer autotune cache (PR #24156) to ROCm — it gives NVIDIA users 15% speedup that AMD users don't get" is actionable.
- **Reference actual PR/issue numbers** so readers can click through.
- **Identify asymmetries.** Where is one side active and the other silent? That's either a gap or an opportunity.
- **Distinguish bugs from features.** AMD bugs that block users are more urgent than missing features.
- **Keep it to 15-20 lines max.** This is a Telegram message, not a report.

## Output Format Example

```
📋 *vLLM Daily Digest*
_Thursday, May 08, 2026_

📈 Active day — 56 total updates
🆕 12 new issues · ✅ 8 closed · 🔀 22 new PRs · 🟣 14 merged
📦 v0.20.2 — FlashAttention 4, improved MoE performance

━━━ 🆕 New Issues (12 total) ━━━
  • #24500 [Bug] Memory leak with continuous batching  💬8  `bug`
  • #24499 [Feature] Qwen3.5 MoE support  💬3
  …and 7 more

━━━ ✅ Closed Issues (8 total) ━━━
  • #24450 [Bug] CUDA OOM on A100  💬12
  …and 3 more

━━━ 🔀 New Pull Requests (22 total) ━━━
  • #24501 [AMD] Enable FP8 attention for diffusion  💬5  `amd`
  …and 17 more

━━━ 🟣 Merged Pull Requests (14 total) ━━━
  • #24480 perf: optimize KV cache for MLA  💬9
  …and 9 more

━━━ 📝 Recent Blog Posts ━━━
  • Announcing vLLM v0.20.2 — _Wed, 06 May 2026_

🔗 Open repo · Issues · PRs · Blog

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 *Weekly AMD vs NVIDIA Intel*
_May 01 – May 08, 2026_

📊 *Activity Volume*
AMD: 8 issues, 24 PRs, 2 releases, 1 blog
NVIDIA: 3 issues, 15 PRs, 1 release, 0 blogs

🔴 *AMD This Week*
  • FP8 kernel work: 6 PRs landed for MLA attention, diffusion models, and Qwen3.5 on MI300/MI355 (#24677, #23955, #20319)
  • CI/testing expansion: Added nightly tests for MI30x/MI35x (#24426)
  • Bug fixes: Fixed speculative decoding NoneType error (#24319)

🟢 *NVIDIA This Week*
  • FlashInfer autotune: Merged caching for attention kernels (#24156) — 15% throughput gain on H100
  • CUDA graph improvements: 3 PRs optimising graph capture for multi-model serving

⚔️ *Competitive Gaps & Opportunities*
  • FlashInfer autotune is NVIDIA-only — AMD users miss the 15% gain. No ROCm port in progress.
  • AMD's EAGLE speculative decoding landed but has high-concurrency memory faults (#23784) — 8 reports.

💡 *Strategic Recommendations for AMD*
  • Port FlashInfer autotune cache to ROCm — highest-impact single item
  • Fix EAGLE memory fault (#23784) urgently — blocks speculative decoding on MI300
  • Double down on diffusion model serving — AMD has a clear lead here
```

## Design Principles

1. **Glanceable header** — Activity level emoji + one-line stats let you decide in 2 seconds whether to read further.
2. **Top 5 not top 10** — Respects the reader's time. The "…and N more" line tells you the full scale.
3. **Linked issue/PR numbers** — Tap `#24500` to go straight to GitHub. No raw URLs.
4. **Activity gauge** — 🔥 Very busy / 📈 Active / 📊 Normal / 🌤 Quiet gives instant context.
5. **Weekly intel is agent-written** — The script collects raw data; the LLM analyses themes and writes strategic advice tied to specific issues/PRs.
6. **Actionable recommendations** — Every recommendation references a specific PR/issue and explains *why* it matters.
7. **Asymmetry detection** — Highlights where one vendor is active and the other is silent.
8. **15-20 lines max for intel section** — Telegram message, not a strategy deck.

## Keyword Lists

### AMD Keywords
`amd`, `rocm`, `mi300`, `mi350`, `mi355`, `mi30x`, `mi35x`, `mi325`, `hip `, `hipblas`, `instinct`, `gfx9`, `gfx10`, `gfx11`, `gfx12`, `aiter`, `radeon`, `rdna`, `cdna`, `xdna`, `ck_tile`, `rocm_smi`, `hipify`, `composable_kernel`, `rccl`

### NVIDIA Keywords
`nvidia`, `cuda`, `nccl`, `tensorrt`, `cutlass`, `cublas`, `cudnn`, `a100`, `h100`, `h200`, `b200`, `gb200`, `gb300`, `hopper`, `blackwell`, `sm_`, `nvcc`, `nvshmem`, `flashinfer`, `thrust`, `cub `

These lists can be extended. Items matching both lists are counted in both categories.

## Sorting Rules

| Category | Primary sort | Secondary sort |
|----------|-------------|----------------|
| New issues | Most comments (most discussed) | Most recent |
| Closed issues | Most comments (most discussed) | Most recent |
| New PRs | Most comments + review comments | Most recent |
| Merged PRs | Most comments + review comments | Most recent |
| Releases | Most recent date | — |
| Blog posts | Most recent date | — |

## Categorising PRs by Labels

The vLLM repo uses labels like `rocm`, `cuda`, `performance`, `bug`, `enhancement`, `ci`, `documentation`, `kernel`, `distributed`. The `matches_keywords` function checks both title and labels — PRs with an explicit `rocm` label will always be caught.

## Automation with Cron

To receive this digest daily, set up a cron job:

```
Example schedule: "0 9 * * *" (every day at 9 AM)
```

The cron prompt should be:
"Load the vllm-daily-digest skill and generate today's vLLM daily digest. Run the collection script, output the daily digest from Part 1 directly, then analyse the weekly AMD vs NVIDIA raw data from Part 2 and write the competitive intelligence section following the skill's formatting guidelines. Do not output the raw Part 2 data."

## Common Pitfalls

1. **Rate limiting without auth**: Unauthenticated GitHub API allows only 60 requests/hour. The collection script needs 7-9 API calls for the full run (daily + weekly), which can exhaust the unauthenticated budget in a single session. Always use `gh auth token` auth in the `fetch()` function — this gives 5000 requests/hour. The script in this skill already includes `gh auth token` integration.

2. **The `since` parameter on issues**: GitHub's `since` filters by `updated_at`, not `created_at`. The script does a secondary filter on `created_at` to get truly new issues.
3. **PRs appear in issues endpoint**: GitHub's issues endpoint includes PRs. Always filter with `'pull_request' not in item`.
4. **Timezone**: Always use UTC for date comparisons with GitHub API.
5. **RSS XML parsing**: The blog RSS feed at `https://vllm.ai/blog/rss.xml` uses standard RSS 2.0 format. Parse with `xml.etree.ElementTree`.
6. **Telegram Markdown**: Use `*bold*`, `_italic_`, `` `code` ``, and `[text](url)` for Telegram Markdown formatting. Avoid HTML tags.
7. **Keyword false positives**: "cuda" may appear in non-NVIDIA contexts. The agent should use judgement when summarising themes.
8. **Weekly section length**: Keep the intel section to 15-20 lines. If there are 50+ AMD items, group them into 3-4 themes rather than listing everything.
