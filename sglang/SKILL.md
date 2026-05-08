---
name: sglang-daily-digest
description: "Use when collecting daily updates from the SGLang GitHub repo (sgl-project/sglang): top 10 new/closed issues, new/merged PRs, and related blog posts from lmsys.org."
version: 1.1.0
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

Each category shows the **top 10** most relevant items, sorted by:
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
import json, subprocess, sys
from datetime import datetime, timedelta, timezone

REPO = "sgl-project/sglang"
API = f"https://api.github.com/repos/{REPO}"
cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
cutoff_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

def fetch(url):
    r = subprocess.run(["curl", "-s", url], capture_output=True, text=True)
    return json.loads(r.stdout)

def parse_dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

def fmt_item(num, title, url, meta=""):
    line = f"  {num}. {title}"
    if meta:
        line += f"\n     {meta}"
    line += f"\n     {url}"
    return line

print(f"=== SGLang Daily Digest ({datetime.now().strftime('%Y-%m-%d')}) ===\n")

# --- 1. New Issues (top 10, sorted by most comments then recency) ---
print("--- NEW ISSUES (last 24h, top 10 most discussed) ---")
raw = fetch(f"{API}/issues?state=open&since={cutoff_iso}&sort=created&direction=desc&per_page=100")
new_issues = [i for i in raw if "pull_request" not in i and parse_dt(i["created_at"]) >= cutoff]
new_issues.sort(key=lambda i: (-i.get("comments", 0), i["created_at"]), reverse=False)
new_issues.sort(key=lambda i: (-i.get("comments", 0),))
for idx, i in enumerate(new_issues[:10], 1):
    labels = ", ".join(l["name"] for l in i.get("labels", []))
    meta = f"by @{i['user']['login']} | {i.get('comments',0)} comments"
    if labels:
        meta += f" | {labels}"
    print(fmt_item(idx, i["title"], i["html_url"], meta))
if not new_issues:
    print("  No new issues in the last 24 hours.")
print(f"\n  Total: {len(new_issues)} new issues (showing top {min(len(new_issues), 10)})\n")

# --- 2. Closed Issues (top 10, sorted by most comments then recency) ---
print("--- CLOSED ISSUES (last 24h, top 10 most discussed) ---")
raw = fetch(f"{API}/issues?state=closed&since={cutoff_iso}&sort=updated&direction=desc&per_page=100")
closed = [i for i in raw if "pull_request" not in i and i.get("closed_at") and parse_dt(i["closed_at"]) >= cutoff]
closed.sort(key=lambda i: (-i.get("comments", 0),))
for idx, i in enumerate(closed[:10], 1):
    meta = f"by @{i['user']['login']} | {i.get('comments',0)} comments | {i.get('state_reason','completed')}"
    print(fmt_item(idx, i["title"], i["html_url"], meta))
if not closed:
    print("  No closed issues in the last 24 hours.")
print(f"\n  Total: {len(closed)} closed issues (showing top {min(len(closed), 10)})\n")

# --- 3. New PRs (top 10, sorted by most comments then recency) ---
print("--- NEW PULL REQUESTS (last 24h, top 10 most discussed) ---")
raw = fetch(f"{API}/pulls?state=open&sort=created&direction=desc&per_page=100")
new_prs = [p for p in raw if parse_dt(p["created_at"]) >= cutoff]
new_prs.sort(key=lambda p: (-(p.get("comments",0) + p.get("review_comments",0)),))
for idx, p in enumerate(new_prs[:10], 1):
    total_comments = p.get("comments", 0) + p.get("review_comments", 0)
    labels = ", ".join(l["name"] for l in p.get("labels", []))
    meta = f"by @{p['user']['login']} | {total_comments} comments"
    if labels:
        meta += f" | {labels}"
    print(fmt_item(idx, p["title"], p["html_url"], meta))
if not new_prs:
    print("  No new PRs in the last 24 hours.")
print(f"\n  Total: {len(new_prs)} new PRs (showing top {min(len(new_prs), 10)})\n")

# --- 4. Merged PRs (top 10, sorted by most comments then recency) ---
print("--- MERGED PULL REQUESTS (last 24h, top 10 most discussed) ---")
raw = fetch(f"{API}/pulls?state=closed&sort=updated&direction=desc&per_page=100")
merged = [p for p in raw if p.get("merged_at") and parse_dt(p["merged_at"]) >= cutoff]
merged.sort(key=lambda p: (-(p.get("comments",0) + p.get("review_comments",0)),))
for idx, p in enumerate(merged[:10], 1):
    total_comments = p.get("comments", 0) + p.get("review_comments", 0)
    merger = p["merged_by"]["login"] if p.get("merged_by") else "unknown"
    meta = f"merged by @{merger} | {total_comments} comments"
    print(fmt_item(idx, p["title"], p["html_url"], meta))
if not merged:
    print("  No merged PRs in the last 24 hours.")
print(f"\n  Total: {len(merged)} merged PRs (showing top {min(len(merged), 10)})\n")

# --- 5. Recent Blog Posts ---
print("--- RECENT SGLANG BLOG POSTS ---")
import re
r = subprocess.run(["curl", "-sL", "https://lmsys.org/blog/"], capture_output=True, text=True)
posts_match = re.search(r'"posts":(\[.*?\])\}', r.stdout)
if posts_match:
    posts = json.loads(posts_match.group(1))
    sglang_posts = [p for p in posts
                    if "sglang" in p.get("title","").lower()
                    or "sglang" in p.get("excerpt","").lower()
                    or p.get("category","") == "sglang"]
    for idx, p in enumerate(sglang_posts[:5], 1):
        excerpt = p.get("excerpt", "")[:100].replace("\n", " ")
        meta = f"{p['date']} | {excerpt}..."
        url = f"https://lmsys.org/blog/{p['slug']}/"
        print(fmt_item(idx, p["title"], url, meta))
    if not sglang_posts:
        print("  No recent SGLang blog posts found.")
else:
    print("  Could not fetch blog data.")

print("\n=== End of Digest ===")
```

## Output Format

The digest follows this clean, numbered format:

```
=== SGLang Daily Digest (2026-05-05) ===

--- NEW ISSUES (last 24h, top 10 most discussed) ---
  1. Issue title here
     by @username | 5 comments | bug, urgent
     https://github.com/sgl-project/sglang/issues/1234

  2. Another issue
     by @user2 | 3 comments
     https://github.com/sgl-project/sglang/issues/1235

  Total: 25 new issues (showing top 10)

--- CLOSED ISSUES (last 24h, top 10 most discussed) ---
  1. Fixed issue title
     by @user | 8 comments | completed
     https://github.com/sgl-project/sglang/issues/1230

  Total: 12 closed issues (showing top 10)

--- NEW PULL REQUESTS (last 24h, top 10 most discussed) ---
  1. PR title here
     by @user | 4 comments | enhancement
     https://github.com/sgl-project/sglang/pull/1235

  Total: 18 new PRs (showing top 10)

--- MERGED PULL REQUESTS (last 24h, top 10 most discussed) ---
  1. Merged PR title
     merged by @maintainer | 6 comments
     https://github.com/sgl-project/sglang/pull/1220

  Total: 15 merged PRs (showing top 10)

--- RECENT SGLANG BLOG POSTS ---
  1. Blog Post Title
     April 29, 2026 | Brief excerpt of the post content...
     https://lmsys.org/blog/2026-04-29-slug/

=== End of Digest ===
```

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
"Load the sglang-daily-digest skill and generate today's SGLang daily digest. Run the collection script and format the report."

## Common Pitfalls

1. **Rate limiting without auth**: Unauthenticated GitHub API allows only 60 requests/hour. Set GITHUB_TOKEN for 5000/hour.
2. **The `since` parameter on issues**: GitHub's `since` filters by `updated_at`, not `created_at`. The script does a secondary filter on `created_at` to get truly new issues.
3. **PRs appear in issues endpoint**: GitHub's issues endpoint includes PRs. Always filter with `'pull_request' not in item`.
4. **Timezone**: Always use UTC for date comparisons with GitHub API.
5. **Blog scraping**: The lmsys.org blog uses Next.js with client-side rendering. The blog post data is embedded in the page's JavaScript payload, not in plain HTML.
