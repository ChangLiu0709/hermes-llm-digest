---
name: sglang-daily-digest
description: "Daily SGLang digest + weekly AMD vs NVIDIA competitive intelligence from sgl-project/sglang: issues, PRs, blogs, strategic advice."
version: 3.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [sglang, github, daily-digest, issues, pull-requests, blog, amd, nvidia, competitive-intelligence]
    related_skills: []
---

# SGLang Daily Digest + AMD Competitive Intelligence

## Overview

Collects a daily summary of activity in the SGLang GitHub repository (https://github.com/sgl-project/sglang) and related blog posts from https://lmsys.org/blog/.

On top of the daily digest, the skill includes a **weekly AMD competitive intelligence section** that:
1. Summarises AMD-related activity (issues, PRs, blogs) from the past 7 days
2. Summarises NVIDIA-related activity from the same period
3. Provides strategic recommendations for AMD to close gaps and surpass NVIDIA

The digest is optimised for **Telegram delivery** — compact, scannable, and formatted with Markdown.

## When to Use

- User asks for SGLang daily updates or digest
- User wants to track SGLang repo activity
- User wants AMD vs NVIDIA competitive analysis in the SGLang ecosystem
- Scheduled via cron job for automated daily reports
- User asks "what's new in SGLang?"

## Data Sources

- **GitHub REST API**: `https://api.github.com/repos/sgl-project/sglang`
  - No auth required for public repos (60 req/hour unauthenticated)
  - Set `GITHUB_TOKEN` in ~/.hermes/.env for higher rate limits (5000 req/hour)
- **LMSYS Blog**: `https://lmsys.org/blog/` — SGLang-related posts

## Collection Script

Run this as a single Python script via execute_code or terminal. It outputs the daily digest AND the raw weekly AMD/NVIDIA data for the agent to analyse.

```python
import json, subprocess, sys, re
from datetime import datetime, timedelta, timezone

REPO = "sgl-project/sglang"
API = f"https://api.github.com/repos/{REPO}"
now_utc = datetime.now(timezone.utc)
cutoff_24h = now_utc - timedelta(hours=24)
cutoff_7d = now_utc - timedelta(days=7)
cutoff_24h_iso = cutoff_24h.strftime("%Y-%m-%dT%H:%M:%SZ")
cutoff_7d_iso = cutoff_7d.strftime("%Y-%m-%dT%H:%M:%SZ")
today = datetime.now()

def fetch(url):
    r = subprocess.run(["curl", "-s", url], capture_output=True, text=True)
    return json.loads(r.stdout)

def fetch_pages(url_template, max_pages=3):
    """Fetch multiple pages of results."""
    all_items = []
    for page in range(1, max_pages + 1):
        url = url_template + f"&page={page}&per_page=100"
        items = fetch(url)
        if not items:
            break
        all_items.extend(items)
    return all_items

def parse_dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

# ── AMD / NVIDIA keyword matching ─────────────────────────

AMD_KEYWORDS = [
    "amd", "rocm", "mi300", "mi350", "mi355", "mi30x", "mi35x",
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
    """Check if an issue/PR title or labels match any keyword."""
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

# Blog posts
blog_html = subprocess.run(["curl", "-sL", "https://lmsys.org/blog/"], capture_output=True, text=True).stdout
posts_match = re.search(r'"posts":(\[.*?\])\}', blog_html)
sglang_posts = []
if posts_match:
    posts = json.loads(posts_match.group(1))
    sglang_posts = [p for p in posts
                    if "sglang" in p.get("title", "").lower()
                    or "sglang" in p.get("excerpt", "").lower()
                    or p.get("category", "") == "sglang"]

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
lines.append(f"📋 *SGLang Daily Digest*")
lines.append(f"_{day_name}, {date_str}_")
lines.append("")
lines.append(f"{activity} — {total_activity} total updates")
lines.append(f"🆕 {len(new_issues)} new issues · ✅ {len(closed_issues)} closed · 🔀 {len(new_prs)} new PRs · 🟣 {len(merged_prs)} merged")
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
if sglang_posts:
    lines.append(f"━━━ 📝 Recent Blog Posts ━━━")
    for p in sglang_posts[:3]:
        date = p.get("date", "")
        title = p.get("title", "")
        url = f"https://lmsys.org/blog/{p['slug']}/"
        lines.append(f"  • [{title}]({url}) — _{date}_")
    lines.append("")

# Footer for daily section
lines.append(f"🔗 [Open repo](https://github.com/{REPO}) · [Issues](https://github.com/{REPO}/issues) · [PRs](https://github.com/{REPO}/pulls)")

print("\n".join(lines))

# ══════════════════════════════════════════════════════════
# PART 2: WEEKLY AMD vs NVIDIA RAW DATA (last 7 days)
# ══════════════════════════════════════════════════════════

print("\n\n" + "=" * 60)
print("WEEKLY COMPETITIVE INTELLIGENCE RAW DATA (last 7 days)")
print("=" * 60)

# Collect 7-day issues (open + closed)
all_issues_7d = []
raw = fetch_pages(f"{API}/issues?state=all&since={cutoff_7d_iso}&sort=updated&direction=desc")
all_issues_7d = [i for i in raw if "pull_request" not in i]

# Collect 7-day PRs (open + closed)
all_prs_open_7d = fetch_pages(f"{API}/pulls?state=open&sort=created&direction=desc")
all_prs_open_7d = [p for p in all_prs_open_7d if parse_dt(p["created_at"]) >= cutoff_7d]

all_prs_closed_7d = fetch_pages(f"{API}/pulls?state=closed&sort=updated&direction=desc")
all_prs_closed_7d = [p for p in all_prs_closed_7d if p.get("merged_at") and parse_dt(p["merged_at"]) >= cutoff_7d]

all_prs_7d = all_prs_open_7d + all_prs_closed_7d

# Filter AMD items
amd_issues = [i for i in all_issues_7d if matches_keywords(i, AMD_KEYWORDS)]
amd_prs = [p for p in all_prs_7d if matches_keywords(p, AMD_KEYWORDS)]
amd_blogs = [p for p in sglang_posts if any(kw in (p.get("title","") + " " + p.get("excerpt","")).lower() for kw in AMD_KEYWORDS)]

# Filter NVIDIA items
nvidia_issues = [i for i in all_issues_7d if matches_keywords(i, NVIDIA_KEYWORDS)]
nvidia_prs = [p for p in all_prs_7d if matches_keywords(p, NVIDIA_KEYWORDS)]
nvidia_blogs = [p for p in sglang_posts if any(kw in (p.get("title","") + " " + p.get("excerpt","")).lower() for kw in NVIDIA_KEYWORDS)]

print(f"\n--- AMD ACTIVITY ({len(amd_issues)} issues, {len(amd_prs)} PRs, {len(amd_blogs)} blog posts) ---")
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

print("\nAMD Blog Posts:")
for p in amd_blogs:
    print(f"  {p.get('date','')} — {p.get('title','')}")
    print(f"    https://lmsys.org/blog/{p['slug']}/")
    excerpt = (p.get("excerpt","") or "")[:200].replace("\n"," ")
    if excerpt:
        print(f"    {excerpt}")

print(f"\n--- NVIDIA ACTIVITY ({len(nvidia_issues)} issues, {len(nvidia_prs)} PRs, {len(nvidia_blogs)} blog posts) ---")
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

print("\nNVIDIA Blog Posts:")
for p in nvidia_blogs:
    print(f"  {p.get('date','')} — {p.get('title','')}")
    print(f"    https://lmsys.org/blog/{p['slug']}/")
    excerpt = (p.get("excerpt","") or "")[:200].replace("\n"," ")
    if excerpt:
        print(f"    {excerpt}")

print(f"\n--- VOLUME COMPARISON ---")
print(f"AMD:    {len(amd_issues)} issues, {len(amd_prs)} PRs, {len(amd_blogs)} blogs = {len(amd_issues)+len(amd_prs)+len(amd_blogs)} total")
print(f"NVIDIA: {len(nvidia_issues)} issues, {len(nvidia_prs)} PRs, {len(nvidia_blogs)} blogs = {len(nvidia_issues)+len(nvidia_prs)+len(nvidia_blogs)} total")
print("=" * 60)
```

## Agent Instructions for the Weekly Section

After running the collection script, you will see two parts of output:

1. **PART 1** (before the `====` line): The formatted daily digest. Output this directly as-is.

2. **PART 2** (after the `WEEKLY COMPETITIVE INTELLIGENCE RAW DATA` header): Raw AMD and NVIDIA items from the past 7 days. **Do NOT output this raw data.** Instead, analyse it and write a weekly competitive intelligence section formatted as below.

### How to Write the Weekly Section

Append the following section AFTER the daily digest. Analyse the raw data from Part 2 and write:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 *Weekly AMD vs NVIDIA Intel*
_Week of {date range}_

📊 *Activity Volume*
AMD: X issues, Y PRs, Z blogs
NVIDIA: X issues, Y PRs, Z blogs

🔴 *AMD This Week*
{2-4 bullet points summarising the main themes from AMD issues/PRs/blogs. Group by topic — e.g. "FP8 kernel optimisation", "ROCm CI/testing", "multi-GPU support". Mention specific PR/issue numbers for the most impactful items.}

🟢 *NVIDIA This Week*
{2-4 bullet points summarising the main themes from NVIDIA issues/PRs/blogs. Same grouping approach.}

⚔️ *Competitive Gaps & Opportunities*
{2-3 bullet points identifying where NVIDIA is ahead and AMD has gaps — based on what the issues/PRs reveal. Be specific: "NVIDIA has X merged while AMD's equivalent Y is still open."}

💡 *Strategic Recommendations for AMD*
{3-4 actionable bullet points. Each should be concrete and tied to the data. Examples:
- "Prioritise [specific feature] — NVIDIA landed this in PR #XXXX, AMD has no equivalent yet"
- "The [bug/issue] is blocking AMD adoption — 8 community reports this week"
- "Opportunity: [area] has no NVIDIA activity — AMD can lead here"}
```

### Writing Guidelines for the Intel Section

- **Be specific, not generic.** "Improve ROCm support" is useless. "Port the FlashInfer autotune cache (PR #24156) to ROCm — it gives NVIDIA users 15% speedup that AMD users don't get" is actionable.
- **Reference actual PR/issue numbers** so readers can click through.
- **Identify asymmetries.** Where is one side active and the other silent? That's either a gap or an opportunity.
- **Distinguish bugs from features.** AMD bugs that block users are more urgent than missing features.
- **Keep it to 15-20 lines max.** This is a Telegram message, not a report.

## Output Format

The final Telegram message should look like this (daily + weekly combined):

```
📋 *SGLang Daily Digest*
_Thursday, May 08, 2026_

📈 Active day — 56 total updates
🆕 12 new issues · ✅ 8 closed · 🔀 22 new PRs · 🟣 14 merged

━━━ 🆕 New Issues (12 total) ━━━
  • #24500 [Bug] Memory leak in continuous batching  💬8  `bug`
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
  • SGLang v0.5: FlashAttention 4 — _April 6, 2026_

🔗 Open repo · Issues · PRs

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 *Weekly AMD vs NVIDIA Intel*
_May 01 – May 08, 2026_

📊 *Activity Volume*
AMD: 8 issues, 24 PRs, 2 blogs
NVIDIA: 3 issues, 15 PRs, 1 blog

🔴 *AMD This Week*
  • FP8 kernel work: 6 PRs landed for MLA attention, diffusion models, and Qwen3.5 on MI300/MI355 (#24677, #23955, #20319)
  • CI/testing expansion: Added nightly tests for MI30x/MI35x (#24426), new unit test coverage for custom all-reduce on ROCm 7.0/7.2 (#24680)
  • Bug fixes: Fixed speculative decoding NoneType error (#24319), Docker nightly builds (#24407)

🟢 *NVIDIA This Week*
  • FlashInfer autotune: Merged caching for attention kernels (#24156) — 15% throughput gain on H100
  • Streaming perf: Removed per-token heap allocation in SSE (#24669)
  • CUDA graph improvements: 3 PRs optimising graph capture for multi-model serving

⚔️ *Competitive Gaps & Opportunities*
  • FlashInfer autotune (#24156) is NVIDIA-only — AMD users miss the 15% gain. No ROCm port in progress.
  • AMD's EAGLE speculative decoding landed (#23146) but has high-concurrency GPU memory faults (#23784) — 8 reports this week.
  • NVIDIA has zero activity on diffusion model serving — AMD is leading here with 3 merged FP8 diffusion PRs.

💡 *Strategic Recommendations for AMD*
  • Port FlashInfer autotune cache to ROCm — this is the highest-impact single item; NVIDIA users get 15% free throughput that AMD users don't.
  • Fix EAGLE memory fault (#23784) urgently — it's the top community complaint and blocks speculative decoding adoption on MI300.
  • Double down on diffusion model serving — AMD has a clear lead here. Publish a benchmark blog showing FP8 diffusion perf vs NVIDIA to attract users.
  • Add LoRA-for-MoE support on ROCm — PR #24420 landed for CUDA but AMD isn't mentioned.
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
`amd`, `rocm`, `mi300`, `mi350`, `mi355`, `mi30x`, `mi35x`, `hip `, `hipblas`, `instinct`, `gfx9`, `gfx10`, `gfx11`, `gfx12`, `aiter`, `radeon`, `rdna`, `cdna`, `xdna`, `ck_tile`, `rocm_smi`, `hipify`, `composable_kernel`, `rccl`

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
| Blog posts | Most recent date | — |
| Weekly AMD/NVIDIA items | Not sorted — grouped by theme by the agent | — |

## Automation with Cron

To receive this digest daily, set up a cron job:

```
Use the Hermes cron tool to schedule this skill to run daily.
Example schedule: "0 9 * * *" (every day at 9 AM)
```

The cron prompt should be:
"Load the sglang-daily-digest skill and generate today's SGLang daily digest. Run the collection script, output the daily digest from Part 1 directly, then analyse the weekly AMD vs NVIDIA raw data from Part 2 and write the competitive intelligence section following the skill's formatting guidelines. Do not output the raw Part 2 data."

## Common Pitfalls

1. **Rate limiting without auth**: Unauthenticated GitHub API allows only 60 requests/hour. Set GITHUB_TOKEN for 5000/hour. The weekly collection fetches ~9 API pages so budget accordingly.
2. **The `since` parameter on issues**: GitHub's `since` filters by `updated_at`, not `created_at`. The script does a secondary filter on `created_at` to get truly new issues.
3. **PRs appear in issues endpoint**: GitHub's issues endpoint includes PRs. Always filter with `'pull_request' not in item`.
4. **Timezone**: Always use UTC for date comparisons with GitHub API.
5. **Blog scraping**: The lmsys.org blog uses Next.js with client-side rendering. The blog post data is embedded in the page's JavaScript payload, not in plain HTML.
6. **Telegram Markdown**: Use `*bold*`, `_italic_`, `` `code` ``, and `[text](url)` for Telegram Markdown formatting. Avoid HTML tags.
7. **Keyword false positives**: "cuda" may appear in non-NVIDIA contexts (e.g. "CUDA graph" as a general concept). The agent should use judgement when summarising themes.
8. **Weekly section length**: Keep the intel section to 15-20 lines. If there are 50+ AMD items, group them into 3-4 themes rather than listing everything.
