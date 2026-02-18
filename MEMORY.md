# MEMORY.md — Core Invariants

## Identity
- **User:** Владимир (Europe/Madrid)
- **Agent:** CoinMaster 🪙
- **Style:** practical, expert, no filler
- **Scope:** crypto trading automation (Hyperliquid API, backtests, SL/TP, risk management)

## Model Policy (CRITICAL)
- **Primary:** `openai/gpt-5.1-codex-mini` (Codex 5.1 mini)
- **Fallback:** `anthropic/claude-haiku-4-5` (Claude Haiku)
- **DevTask (main work):** `anthropic/claude-opus-4-6` via sessions_spawn (Claude Opus)
- **ComplexBug/Arch:** `openai/gpt-5.3-codex` (Codex 5.3)

**Work scheme:**
- Codex 5.1 mini: conversation, planning, testing, cron, current tasks
- Claude Opus: main dev (spawn → task → test → fix)
- Codex 5.3: complex bugs/architecture only

## Project State
- **BTC first**, then ETH/SOL after success
- **Bias format:** `BTC long`/`BTC short`/`BTC off`
- **Startup:** Hyperliquid perp with manual confirmation (30 USDC max, 10x leverage max)
- **Exit trigger:** 4H reverse signal only
- **P0 status:** enforce risk gates → live smoke test → VPS cutover

## Risk Parameters (v1 baseline)
- Hard-stop daily: 20% DD → close all
- SL: structure + ATR-buffer + 0.70% cap
- Partial: 1.0R/2.2R/3.8R (40%/35%/25%)
- Portfolio leverage cap: 10x
- Manual confirmation: ON (startup phase)

## Infrastructure
- **Web:** Vercel
- **API/DB:** Hetzner VPS (46.225.133.161, coinmaster24.com)
- **Auth:** single-operator phase (keys in `.env`)
- **Telegram/Cron:** on VPS only (silent exec, final answer only)

## Decisions Log
- 2026-02-15: Context audit + token optimization (AGENTS.md/MEMORY.md sжаты)
- 2026-02-15: Model lock on Codex 5.3-codex → now Codex 5.1 mini primary + Opus spawn for dev
- 2026-02-14: Live-only UI, HTTPS enabled, historical replay paused
- 2026-02-13: VPS OAuth issue resolved (IPv6 polling fix)

---
**For detailed specs:** see PROJECT_TRUTH.md (on-demand) or memory/YYYY-MM-DD.md (daily logs)
