# OPS_MINIMUM.md

Compact index only; not a second source of truth.

Read after restart:
1. `.ops/PROJECT_TRUTH.md`
2. `.ops/ACTIVE_TASK.md`
3. Protocol files only if needed: `.ops/SOFTWARE_DEVELOPMENT_PROTOCOL.md`, `.ops/RESET_PREP_PROTOCOL.md`, `.ops/TASK_STATE_PROTOCOL.md`

Preflight:
```bash
cd /root/.openclaw/workspace/coinmaster/coinmaster
git status --short
git rev-parse HEAD
git rev-parse origin/main
git rev-list --left-right --count origin/main...HEAD
cat /opt/coinmaster/.deploy-source-commit 2>/dev/null || true
```

Runbooks: root `RUNBOOK_COMMANDS.md`, app `coinmaster/RUNBOOK_COMMANDS.md`.
