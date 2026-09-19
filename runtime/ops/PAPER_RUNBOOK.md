# Paper runtime operations runbook

Scope: the isolated Nautilus paper services only. This runbook never enables
live execution, imports credentials, changes a proxy/firewall, or modifies a
strategy/optimizer.

## Monitoring and doctor

Use the loopback APIs from the VPS. The runtime token stays in the protected
`/etc/coinmaster-paper.env` file and must never be printed or copied into a
shell history.

```sh
systemctl is-active coinmaster-paper.service coinmaster-runtime.service
curl -fsS http://127.0.0.1:18181/health
.venv/bin/python scripts/paper_doctor.py /var/lib/coinmaster-paper/paper.sqlite
```

Healthy paper evidence requires `mode=paper`, `live_order_capability=false`,
only `SandboxExecutionClient`, all required feeds `READY`, a valid/reconciled
snapshot, and no unknown open orders. Doctor output always keeps
`live_gate=BLOCKED_PAPER_ONLY`; `OK` is journal readability, not live approval.

## Backup and restore drill

Use SQLite's online backup on the live database; do not copy WAL files by hand.
Write drills outside the service database directory and verify both hash and
doctor output. The restore drill targets only a disposable copy.

```sh
stamp=$(date -u +%Y%m%dT%H%M%SZ)
drill=/var/lib/coinmaster-runtime/drills/$stamp
install -d -m 0700 "$drill"
sqlite3 /var/lib/coinmaster-paper/paper.sqlite ".backup '$drill/paper.sqlite'"
sha256sum "$drill/paper.sqlite"
cd /root/.openclaw/workspace/coinmaster/coinmaster/runtime
.venv/bin/python scripts/paper_doctor.py "$drill/paper.sqlite"
cp "$drill/paper.sqlite" "$drill/restore-copy.sqlite"
.venv/bin/python scripts/paper_doctor.py "$drill/restore-copy.sqlite"
```

Never restore over `/var/lib/coinmaster-paper/paper.sqlite` while either paper
service is running. A real restore needs a separate authorized maintenance
procedure, a stopped paper worker, a pre-restore backup, and a reconciliation
check before any paper command.

## Reconciliation and incident response

After a paper-worker restart, confirm `/health` reports `RECONCILED` through
the sidecar and inspect positions/orders. Any mismatch, stale feed, or open
unknown order is fail-closed: leave entries paused, preserve the journal, take
an online backup, and investigate. The tested crash window is submit-before-ACK:
the persisted Sandbox client order must match the restored cache exactly; it
does not re-enable increases while still open.

## Live gate

There is no live promotion command. Live remains blocked until a separately
approved design and evidence package covers venue/account authorization,
historical faithfulness, execution/reconciliation, risk limits, and an explicit
owner approval. `live_order_capability=false` is a required invariant.
