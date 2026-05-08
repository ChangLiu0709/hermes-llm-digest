# Hermes SGLang Daily Digest

An automated daily digest system built on [Hermes Agent](https://github.com/NousResearch/hermes-agent) that tracks activity in the [SGLang](https://github.com/sgl-project/sglang) GitHub repository. Every morning, it collects new and closed issues, opened and merged pull requests, and related blog posts — then delivers a formatted summary straight to Telegram.

This project was created as a practical example of setting up Hermes Agent with the AMD LLM Gateway, configuring a Telegram bot, and building a custom Hermes skill with automated cron delivery.

---

## Table of Contents

- [Setting Up Hermes Agent](#setting-up-hermes-agent)
  - [Step 1: Install Hermes Agent](#step-1-install-hermes-agent)
  - [Step 2: Configure the AMD LLM Gateway](#step-2-configure-the-amd-llm-gateway)
  - [Step 3: Set Up the Telegram Bot](#step-3-set-up-the-telegram-bot)
  - [Step 4: Start the Gateway](#step-4-start-the-gateway)
- [SGLang Daily Digest Skill](#sglang-daily-digest-skill)
  - [What It Does](#what-it-does)
  - [Skill Design](#skill-design)
  - [Installing the Skill](#installing-the-skill)
  - [Running Manually](#running-manually)
  - [Scheduling with Cron](#scheduling-with-cron)
  - [Example Output](#example-output)

---

## Setting Up Hermes Agent

### Step 1: Install Hermes Agent

Hermes Agent is an open-source AI agent framework by [Nous Research](https://nousresearch.com/) that runs in your terminal and on messaging platforms. Install it with one command:

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

After installation, run the setup wizard to configure your model and provider:

```bash
hermes setup
```

Or start chatting immediately with:

```bash
hermes
```

### Step 2: Configure the AMD LLM Gateway

AMD provides an LLM gateway at `https://llm-api.amd.com` that offers Anthropic-compatible API endpoints. To use it with Hermes, we set up a lightweight local proxy that injects AMD's required authentication header (`Ocp-Apim-Subscription-Key`) into every request.

#### 2a. Create the AMD Proxy Script

Save the following as `amd_proxy.py` (e.g. at `~/.hermes/amd_proxy.py`):

```python
"""
AMD API Gateway Proxy for Hermes
Injects the required Ocp-Apim-Subscription-Key header into all requests
forwarded to AMD's Anthropic-compatible endpoint.

Usage:
    python amd_proxy.py

Then configure Hermes with:
    ANTHROPIC_BASE_URL=http://127.0.0.1:8082
    ANTHROPIC_API_KEY=dummy
"""

import http.server
import urllib.request
import urllib.error
import ssl

AMD_ENDPOINT = "https://llm-api.amd.com/Anthropic"
SUBSCRIPTION_KEY = "<your-amd-subscription-key>"
PROXY_PORT = 8082

SKIP_HEADERS = {"host", "content-length", "transfer-encoding"}


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[proxy] {fmt % args}")

    def _forward(self, method, body=None):
        url = AMD_ENDPOINT + self.path
        headers = {
            k: v for k, v in self.headers.items()
            if k.lower() not in SKIP_HEADERS
        }
        headers["Ocp-Apim-Subscription-Key"] = SUBSCRIPTION_KEY
        headers["host"] = "llm-api.amd.com"

        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        ctx = ssl.create_default_context()

        try:
            with urllib.request.urlopen(req, context=ctx) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() not in {"transfer-encoding"}:
                        self.send_header(k, v)
                self.end_headers()
                self.wfile.write(resp.read())
        except urllib.error.HTTPError as e:
            body_bytes = e.read()
            self.send_response(e.code)
            for k, v in e.headers.items():
                if k.lower() not in {"transfer-encoding"}:
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body_bytes)

    def do_GET(self):
        self._forward("GET")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else None
        self._forward("POST", body)

    def do_DELETE(self):
        self._forward("DELETE")


if __name__ == "__main__":
    server = http.server.HTTPServer(("127.0.0.1", PROXY_PORT), ProxyHandler)
    print(f"AMD proxy running on http://127.0.0.1:{PROXY_PORT}")
    print(f"Forwarding to: {AMD_ENDPOINT}")
    print(f"Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nProxy stopped.")
```

Replace `<your-amd-subscription-key>` with your actual AMD API subscription key.

#### 2b. Start the Proxy

Run the proxy in the background (using tmux, screen, or a separate terminal):

```bash
# Using tmux (recommended for WSL where systemd is unavailable)
tmux new-session -d -s amd-proxy 'python3 ~/.hermes/amd_proxy.py'
```

Verify it is running:

```bash
curl -s http://127.0.0.1:8082/ 2>&1 | head -5
```

#### 2c. Configure Hermes to Use the AMD Proxy

Edit `~/.hermes/.env` and add:

```bash
ANTHROPIC_API_KEY=dummy
ANTHROPIC_BASE_URL=http://127.0.0.1:8082
```

Then set the model in Hermes:

```bash
hermes config set model.default claude-opus-4-6
hermes config set model.provider anthropic
```

Hermes now sends all API calls to the local proxy on port 8082, which forwards them to AMD's gateway with the proper authentication header. From Hermes's perspective, it looks like a standard Anthropic endpoint.

### Step 3: Set Up the Telegram Bot

#### 3a. Create a Bot with BotFather

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts to name your bot
3. Copy the bot token (looks like `1234567890:ABCdefGhIjKlmNoPqRsTuVwXyZ`)

#### 3b. Configure Hermes

Add the token to `~/.hermes/.env`:

```bash
TELEGRAM_BOT_TOKEN=<your-bot-token>
TELEGRAM_ALLOWED_USERS=*
```

The `TELEGRAM_ALLOWED_USERS=*` allows all users to interact with the bot. For production, restrict to specific user IDs (comma-separated).

#### 3c. Find Your Telegram Chat ID

Send any message to your bot, then retrieve your chat ID:

```bash
curl -s "https://api.telegram.org/bot<your-bot-token>/getUpdates" | python3 -m json.tool | grep '"id"'
```

Note your chat ID — you will need it for cron job delivery.

### Step 4: Start the Gateway

The Hermes gateway connects to messaging platforms and runs the agent loop for incoming messages.

On a system with systemd:

```bash
hermes gateway install
hermes gateway start
```

On WSL (where systemd is typically unavailable), use tmux:

```bash
tmux new-session -d -s hermes-gw 'hermes gateway run'
```

Verify the gateway is running:

```bash
tmux capture-pane -t hermes-gw -p | tail -5
```

You should see output like:

```
✓ telegram connected
Gateway running with 1 platform(s)
Cron ticker started (interval=60s)
```

Your Hermes Agent is now fully operational — connected to the AMD LLM Gateway and reachable via Telegram.

---

## SGLang Daily Digest Skill

### What It Does

The SGLang Daily Digest skill automatically collects and summarises the last 24 hours of activity from the [SGLang GitHub repository](https://github.com/sgl-project/sglang):

| Category | Source | Sorting |
|----------|--------|---------|
| New issues | GitHub Issues API (state=open, created in last 24h) | Most commented first |
| Closed issues | GitHub Issues API (state=closed, closed in last 24h) | Most commented first |
| New pull requests | GitHub Pulls API (state=open, created in last 24h) | Most commented first |
| Merged pull requests | GitHub Pulls API (state=closed, merged in last 24h) | Most commented first |
| Blog posts | LMSYS blog (lmsys.org/blog/) | Most recent first |

Each category shows the **top 10** most relevant items, prioritising the most-discussed ones. Blog posts are filtered to SGLang-related content only.

### Skill Design

The skill is structured as a standard Hermes SKILL.md file (see [`sglang/SKILL.md`](sglang/SKILL.md)) with the following architecture:

```
sglang/SKILL.md
├── YAML Frontmatter        — name, description, version, tags
├── Overview                 — what the skill does
├── When to Use              — trigger conditions for the agent
├── Data Sources             — GitHub REST API + LMSYS blog
├── Collection Script        — self-contained Python script
├── Output Format            — example of the formatted digest
├── Sorting Rules            — how items are ranked
├── Automation with Cron     — scheduling instructions
└── Common Pitfalls          — edge cases and gotchas
```

**Key design decisions:**

1. **Self-contained Python script** — The collection logic is embedded directly in the skill as a Python script rather than relying on external dependencies. It uses only `curl`, `json`, `re`, and the Python standard library.

2. **GitHub REST API (not GraphQL)** — Simpler, no auth required for public repos (60 requests/hour unauthenticated, 5000/hour with a `GITHUB_TOKEN`).

3. **Two-stage filtering for issues** — GitHub's `since` parameter filters by `updated_at`, not `created_at`. The script applies a secondary filter on `created_at` to capture only genuinely new issues.

4. **PR deduplication** — GitHub's Issues endpoint returns PRs mixed with issues. The script filters these out with `'pull_request' not in item`.

5. **Blog scraping via JSON payload** — The LMSYS blog uses Next.js with client-side rendering. Instead of parsing HTML, the script extracts the embedded JSON data payload from the page source.

6. **Discussion-priority sorting** — Items are sorted by comment count (most discussed first) rather than pure recency, surfacing the issues and PRs that are generating the most community engagement.

### Installing the Skill

Copy the skill into your Hermes skills directory:

```bash
mkdir -p ~/.hermes/skills/research/sglang-daily-digest/
cp sglang/SKILL.md ~/.hermes/skills/research/sglang-daily-digest/SKILL.md
```

Or install directly from this repository using Hermes:

```bash
hermes skills install https://raw.githubusercontent.com/<your-username>/hermes-sglang-digest/main/sglang/SKILL.md --name sglang-daily-digest
```

Verify it is installed:

```bash
hermes skills list | grep sglang
```

### Running Manually

In an interactive Hermes session, load the skill and ask for a digest:

```
/skill sglang-daily-digest
What's new in SGLang today?
```

Or as a one-shot command:

```bash
hermes -s sglang-daily-digest chat -q "Generate today's SGLang daily digest"
```

### Scheduling with Cron

To receive the digest automatically every morning via Telegram, set up a Hermes cron job.

In an interactive Hermes session:

```
Create a cron job that runs the sglang-daily-digest skill every day at 7:30 AM UK time
and delivers the result to my Telegram.
```

Or configure it programmatically. The cron job uses these settings:

| Setting | Value |
|---------|-------|
| Schedule | `30 6 * * *` (6:30 UTC = 7:30 AM BST) |
| Skill | `sglang-daily-digest` |
| Delivery | `telegram:<your-chat-id>` |
| Toolsets | `terminal`, `web`, `file` |
| Repeat | forever |

Manage the cron job with:

```bash
hermes cron list                 # view all jobs
hermes cron run <job-id>         # trigger immediately
hermes cron pause <job-id>       # pause
hermes cron resume <job-id>      # resume
```

### Example Output

```
=== SGLang Daily Digest (2026-05-07) ===

--- NEW ISSUES (last 24h, top 10 most discussed) ---
  1. [Bug] Memory leak in continuous batching with long sequences
     by @user123 | 8 comments | bug, performance
     https://github.com/sgl-project/sglang/issues/24500

  2. [Feature] Support for Qwen3.5 MoE architecture
     by @contributor | 3 comments | enhancement
     https://github.com/sgl-project/sglang/issues/24499

  Total: 15 new issues (showing top 10)

--- CLOSED ISSUES (last 24h, top 10 most discussed) ---
  1. [Bug] CUDA OOM on A100 with DeepSeek V3
     by @dev42 | 12 comments | completed
     https://github.com/sgl-project/sglang/issues/24450

  Total: 8 closed issues (showing top 10)

--- NEW PULL REQUESTS (last 24h, top 10 most discussed) ---
  1. [AMD] Enable FP8 attention for diffusion models
     by @amd-dev | 5 comments | amd, sgl-kernel
     https://github.com/sgl-project/sglang/pull/24501

  Total: 22 new PRs (showing top 10)

--- MERGED PULL REQUESTS (last 24h, top 10 most discussed) ---
  1. perf: optimize KV cache allocation for MLA
     merged by @maintainer | 9 comments
     https://github.com/sgl-project/sglang/pull/24480

  Total: 18 merged PRs (showing top 10)

--- RECENT SGLANG BLOG POSTS ---
  1. SGLang v0.5: FlashAttention 4 and Elastic Expert Parallelism
     April 6, 2026 | Major release with CUDA graph improvements...
     https://lmsys.org/blog/2026-04-06-sglang-v0-5/

=== End of Digest ===
```

---

## License

MIT
