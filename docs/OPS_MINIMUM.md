# OPS_MINIMUM.md

Minimal startup/read path for Coinmaster operations.

## Read first

1. `.ops/PROJECT_TRUTH.md`
2. `.ops/SOFTWARE_DEVELOPMENT_PROTOCOL.md`
3. `.ops/RESET_PREP_PROTOCOL.md`
4. `.ops/TASK_STATE_PROTOCOL.md`
5. `.ops/ACTIVE_TASK.md`

## Command references

- OpenClaw / VPS bot operations: `RUNBOOK_COMMANDS.md`
- Coinmaster app operations: `coinmaster/RUNBOOK_COMMANDS.md`

## Recovery preflight

```bash
cd /root/.openclaw/workspace/coinmaster/coinmaster
git status --short
git rev-parse HEAD
git rev-list --left-right --count origin/main...HEAD
cat /opt/coinmaster/.deploy-source-commit
```

## Rule

Do not use this file as a second truth document. It is only a compact index into the canonical `.ops/` protocol set.
