# RUNBOOK: Cutover CoinMaster OpenClaw → VPS (coinmaster24.com / 46.225.133.161)

## Goal (P0)
Make **one** authoritative CoinMaster bot running 24/7 on VPS `46.225.133.161` (domain `coinmaster24.com`) to avoid context split.
- VPS = **primary** (Telegram + cron + project truth)
- Mac = **cold резерв** (no Telegram polling, no cron)

## Hard constraints
- BTC first; ETH/SOL only after BTC success.
- Live limits locked: max notional 30 USDC, leverage cap 10x, manual confirmation ON.
- Pre-go-live: only P0 launch-critical tasks.
- Truthful comms: only artifact-backed progress; completion only after GitHub Project status update.

## Current state snapshot (what is already done)
- VPS: OpenClaw installed (`openclaw@2026.2.14`), user-systemd gateway installed and running on loopback.
- VPS workspace prepared: `/home/coinmaster/openclaw-workspace` (+ symlink `coinmaster -> /opt/coinmaster`).
- VPS model policy configured in `~/.openclaw/openclaw.json`:
  - primary `openai-codex/gpt-5.3-codex`
  - fallbacks `["anthropic/claude-opus-4-6"]`
- VPS Telegram token file staged at `/home/coinmaster/.secrets/telegram_bot_token.txt`, but **Telegram disabled** until cutover.
- Mac: hourly progress cron disabled to avoid noise during cutover.

## Secrets policy
- Do **not** store secrets in repo or memory files.
- Prefer interactive entry on VPS (SSH) and file permissions 600.

---

## Step 1 — Prepare required credentials on VPS (no Telegram yet)

### 1A) Anthropic (fallback) token (requires owner help)
Requirement: a **valid Anthropic API key** that passes probe. Some tokens may look valid but return 401.

On VPS:
```bash
openclaw models status --json
openclaw models status --probe --json | head
```
If probe shows `HTTP 401 Invalid bearer token` for `anthropic/claude-opus-4-6`:
- Ask owner to provide a valid key (ideally create a dedicated key for this bot).
- Add it interactively:
```bash
openclaw models auth paste-token --provider anthropic --profile-id anthropic:reserv_claude
openclaw models status --probe --json | head
```
Acceptance: probe result for `anthropic/claude-opus-4-6` is `status=ok`.

### 1B) GitHub PAT (classic) for repo + GitHub Project
Need a PAT that can:
- manage issues in repo `VF78/coinmaster`
- read/write `VF78 Projects v2` (user project `https://github.com/users/VF78/projects/2`)

On VPS store token with 600 perms (example):
```bash
mkdir -p ~/.secrets && chmod 700 ~/.secrets
cat > ~/.secrets/github_pat.txt
chmod 600 ~/.secrets/github_pat.txt
```

---

## Step 2 — Update GitHub Project descriptions (before cutover)
Goal: new VPS bot can continue without losing context.
- Add/Update issue bodies: #11 risk gates, plus new P0 cutover issue.
- Ensure only **one** item is `In Progress`.

Implementation: run `scripts/gh_project_sync.mjs` (added in repo) with `GITHUB_TOKEN`.

---

## Step 3 — Cutover Telegram (avoid dual consumers)

### 3A) Disable Telegram on Mac (first)
On Mac:
```bash
openclaw config set channels.telegram.enabled false
openclaw config set plugins.entries.telegram.enabled false
openclaw gateway restart
```

### 3B) Enable Telegram on VPS
On VPS:
```bash
openclaw config set channels.telegram.enabled true
openclaw config set plugins.entries.telegram.enabled true
openclaw gateway restart
```

### 3C) Smoke: VPS can message owner
On VPS:
```bash
openclaw message send --channel telegram --target 96211907 --message "CoinMaster VPS online (cutover ok)"
```
Acceptance: owner receives message from bot.

---

## Step 4 — Start cron tasks on VPS, keep Mac silent
After Telegram confirmed:
- Enable only the required cron jobs on VPS (hourly truthful status, daily truth save).
- Keep Mac:
  - gateway stopped, or at minimum telegram disabled and cron disabled.

Mac stop (cold reserve):
```bash
openclaw gateway stop
openclaw gateway status
```

---

## Step 5 — Verify model failover (controlled test)
Goal: verify fallback works **without waiting for real usage limit**.

Method (safe):
1) Temporarily set primary to an invalid model (so primary fails fast).
2) Run a small agent turn and ensure it completes via fallback.
3) Revert primary to Codex.

Record evidence: command output + timestamp, and attach to GitHub issue.

---

## Next work after cutover (P0)
- Continue Issue #11: launch-critical risk gates
  1) owner-auth for live endpoints
  2) idempotency/retry/dedupe submit path
  3) hard-stop day 20%
  4) portfolio leverage cap 10x

