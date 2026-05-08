---
name: sglang-daily-digest
description: "Use when collecting daily updates from the SGLang GitHub repo (sgl-project/sglang): top 5 new/closed issues, new/merged PRs, and related blog posts from lmsys.org."
version: 2.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [sglang, github, daily-digest, issues, pull-requests, blog]
    related_skills: []
---

# SGLang Daily Digest

## Overview

Collects a daily summary of activity in the SGLang GitHub repository (https://github.com/sgl-project/sglang) and related blog posts from https://lmsys.org/blog/.

The digest is optimised for **Telegram delivery** — compact, scannable, and formatted with Markdown so it reads well on a phone screen.

Each category shows the **top 5** most relevant items, sorted by:
- **Issues**: most commented (most discussed) first, then by recency
- **PRs**: most commented first, then by recency
- **Blog posts**: most recent first

## When to Use

- User asks for SGLang daily updates or digest
- User wants to track SGLang repo activity
- Scheduled via cron job for automated daily reports
- User asks "what's new in SGLang?"

## Data Sources

- **GitHub REST API**: `https://api.github.com/repos/sgl-project/sglang`
  - No auth required for public repos (60 req/hour unauthenticated)
  - Set `GITHUB_TOKEN` in ~/.hermes/.env for higher rate limits (5000 req/hour)
- **LMSYS Blog**: `https://lmsys.org/blog/` — SGLang-related posts

## Collection Script

Run this as a single Python script via execute_code or terminal:

```python
import json, subprocess, sys, re
from datetime import datetime, timedelta, timezone

REPO = "sgl-project/sglang"
API = f"https://api.github.com/repos/{REPO}"
cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
cutoff_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
today = datetime.now()

def fetch(url):
    r = subprocess.run(["curl", "-s", url], capture_output=True, text=True)
    return json.loads(r.stdout)

def parse_dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

# ── Collect data ──────────────────────────────────────────

# New issues
raw = fetch(f"{API}/issues?state=open&since={cutoff_iso}&sort=created&direction=desc&per_page=100")
new_issues = [i for i in raw if "pull_request" not in i and parse_dt(i["created_at"]) >= cutoff]
new_issues.sort(key=lambda i: (-i.get("comments", 0),))

# Closed issues
raw = fetch(f"{API}/issues?state=closed&since={cutoff_iso}&sort=updated&direction=desc&per_page=100")
closed_issues = [i for i in raw if "pull_request" not in i and i.get("closed_at") and parse_dt(i["closed_at"]) >= cutoff]
closed_issues.sort(key=lambda i: (-i.get("comments", 0),))

# New PRs
raw = fetch(f"{API}/pulls?state=open&sort=created&direction=desc&per_page=100")
new_prs = [p for p in raw if parse_dt(p["created_at"]) >= cutoff]
new_prs.sort(key=lambda p: (-(p.get("comments", 0) + p.get("review_comments", 0)),))

# Merged PRs
raw = fetch(f"{API}/pulls?state=closed&sort=updated&direction=desc&per_page=100")
merged_prs = [p for p in raw if p.get("merged_at") and parse_dt(p["merged_at"]) >= cutoff]
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

# ── Format output ─────────────────────────────────────────

day_name = today.strftime("%A")
date_str = today.strftime("%b %d, %Y")
total_activity = len(new_issues) + len(closed_issues) + len(new_prs) + len(merged_prs)

# Activity level indicator
if total_activity >= 80:
    activity = "🔥 Very busy day"
elif total_activity >= 40:
    activity = "📈 Active day"
elif total_activity >= 10:
    activity = "📊 Normal day"
else:
    activity = "🌤 Quiet day"

lines = []

# Header
lines.append(f"📋 *SGLang Daily Digest*")
lines.append(f"_{day_name}, {date_str}_")
lines.append("")
lines.append(f"{activity} — {total_activity} total updates")
lines.append(f"🆕 {len(new_issues)} new issues · ✅ {len(closed_issues)} closed · 🔀 {len(new_prs)} new PRs · 🟣 {len(merged_prs)} merged")
lines.append("")

# ── New Issues ──
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

# ── Closed Issues ──
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

# ── New PRs ──
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

# ── Merged PRs ──
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

# ── Blog Posts ──
if sglang_posts:
    lines.append(f"━━━ 📝 Recent Blog Posts ━━━")
    for p in sglang_posts[:3]:
        date = p.get("date", "")
        title = p.get("title", "")
        url = f"https://lmsys.org/blog/{p['slug']}/"
        lines.append(f"  • [{title}]({url}) — _{date}_")
    lines.append("")

# Footer
lines.append(f"🔗 [Open repo](https://github.com/{REPO}) · [Issues](https://github.com/{REPO}/issues) · [PRs](https://github.com/{REPO}/pulls)")

print("\n".join(lines))
```

## Output Format

The digest is formatted with Telegram Markdown for readability on mobile:

```
📋 *SGLang Daily Digest*
_Thursday, May 08, 2026_

📈 Active day — 56 total updates
🆕 12 new issues · ✅ 8 closed · 🔀 22 new PRs · 🟣 14 merged

━━━ 🆕 New Issues (12 total) ━━━
  • #24500 [Bug] Memory leak in continuous batching  💬8  `bug` `performance`
  • #24499 [Feature] Support for Qwen3.5 MoE  💬3  `enhancement`
  • #24498 CUDA error on multi-GPU inference
  • #24497 Documentation update for v0.5
  • #24496 Add streaming support for vision models  💬1
  …and 7 more

━━━ ✅ Closed Issues (8 total) ━━━
  • #24450 [Bug] CUDA OOM on A100 with DeepSeek V3  💬12
  • #24445 Fix tokenizer mismatch in chat template  💬5
  • #24440 Dependency conflict with transformers 4.50
  • #24438 Add batch size auto-tuning
  • #24435 [Bug] Speculative decoding crash with Outlines  💬2
  …and 3 more

━━━ 🔀 New Pull Requests (22 total) ━━━
  • #24501 [AMD] Enable FP8 attention for diffusion  💬5  `amd` `sgl-kernel`
  • #24502 perf: reduce KV cache fragmentation  💬3  `performance`
  • #24503 feat: Gemma 4 MTP support  💬2
  • #24504 fix: correct LoRA buffer sizing for MoE
  • #24505 ci: add nightly benchmark suite  💬1
  …and 17 more

━━━ 🟣 Merged Pull Requests (14 total) ━━━
  • #24480 perf: optimize KV cache allocation for MLA  💬9
  • #24478 [AMD] Cherry-pick aiter commit for mhc_pre fix  💬4
  • #24475 feat: FlashInfer autotune caching  💬3
  • #24470 fix: gateway health check regression
  • #24468 docs: update ROCm installation guide  💬1
  …and 9 more

━━━ 📝 Recent Blog Posts ━━━
  • SGLang v0.5: FlashAttention 4 and Elastic EP — _April 6, 2026_
  • DeepSeek-V4 Day-0 Support — _March 25, 2026_

🔗 Open repo · Issues · PRs
```

## Design Principles

1. **Glanceable header** — Activity level emoji + one-line stats let you decide in 2 seconds whether to read further.
2. **Top 5 not top 10** — Respects the reader's time. The "…and N more" line tells you the full scale.
3. **Linked issue/PR numbers** — Tap `#24500` to go straight to GitHub. No raw URLs cluttering the screen.
4. **Inline labels as code tags** — `bug` `performance` stand out visually but don't dominate.
5. **Comment count as signal** — 💬8 tells you which items have active discussion, helping you prioritise.
6. **No author names** — Saves space. The author is one tap away on the linked issue.
7. **Activity gauge** — 🔥 Very busy / 📈 Active / 📊 Normal / 🌤 Quiet gives instant context.
8. **Blog posts capped at 3** — These are evergreen, not daily items. Less is more.
9. **Quick-access footer** — One-tap links to the repo, issues page, and PRs page.

## Sorting Rules

| Category | Primary sort | Secondary sort |
|----------|-------------|----------------|
| New issues | Most comments (most discussed) | Most recent |
| Closed issues | Most comments (most discussed) | Most recent |
| New PRs | Most comments + review comments | Most recent |
| Merged PRs | Most comments + review comments | Most recent |
| Blog posts | Most recent date | — |

## Automation with Cron

To receive this digest daily, set up a cron job:

```
Use the Hermes cron tool to schedule this skill to run daily.
Example schedule: "0 9 * * *" (every day at 9 AM)
```

The cron prompt should be:
"Load the sglang-daily-digest skill and generate today's SGLang daily digest. Run the collection script and format the report. Output the formatted result directly — do not add any extra commentary before or after the digest."

## Common Pitfalls

1. **Rate limiting without auth**: Unauthenticated GitHub API allows only 60 requests/hour. Set GITHUB_TOKEN for 5000/hour.
2. **The `since` parameter on issues**: GitHub's `since` filters by `updated_at`, not `created_at`. The script does a secondary filter on `created_at` to get truly new issues.
3. **PRs appear in issues endpoint**: GitHub's issues endpoint includes PRs. Always filter with `'pull_request' not in item`.
4. **Timezone**: Always use UTC for date comparisons with GitHub API.
5. **Blog scraping**: The lmsys.org blog uses Next.js with client-side rendering. The blog post data is embedded in the page's JavaScript payload, not in plain HTML.
6. **Telegram Markdown**: Use `*bold*`, `_italic_`, `` `code` ``, and `[text](url)` for Telegram Markdown formatting. Avoid HTML tags.
