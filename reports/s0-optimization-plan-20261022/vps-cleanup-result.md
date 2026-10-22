# VPS obsolete AI cleanup — completed 2026-10-22

Deleted exactly 20 approved resolved paths: 19 individual obsolete fitted-model/checkpoint/transform-cache files plus the isolated fast-rnd AI environment. No service/process action, install, source/ops/git/Project change or compute experiment was performed.

Deleted allocation: **1,846,198,272 bytes**. Observed free-disk increase: **1,846,120,448 bytes** (1.719 GiB). Free disk: 2,010,816,512 → 3,856,936,960 bytes (95% → 91% used). The small difference between removed allocation and observed free-space delta reflects concurrent filesystem activity.

Every allowlisted path is absent. Fresh pre-unlink checks found no process cwd/exe/root/maps/cmdline/fd/mountinfo dependency and no container mount overlap. Paths, inode/device identities, allocation and file SHA-256 values matched inventory; symlink/ancestor resolution was rejected unless exact. Recursive deletion of the single environment did not follow symlinks.

The canonical native runtime `.venv` is retained and hash-verified; archived S0 uses it. The removed environment contained AI-only NumPy/aeon/STUMPY/CPUtorch and no Nautilus package. Coordinator confirmed future S0 optimization uses canonical native `.venv`. No dependency surgery or replacement environment was installed.

Protected native runtime, source/config, reports, all existing job evidence, BTC/SOL real-data/funding, D1 numerical features/historical infrastructure and archived result payloads matched before/after aggregate SHA-256 digests. Individual approved model/cache files were excluded from the retained digest. Forecasts, probabilities, labels, metrics, JSON/CSV, S0 money/trade and settled-receipt evidence remain. Kronos/TS2Vec upstream source/provenance remains. Secrets, installed releases, /srv /opt /etc, Hermes/shared caches and runtime journals/state DBs were excluded from deletion.

## Protected services

All sampled unit properties, MainPID and NRestarts were unchanged. Inactive disabled paper/live units remained inactive.

| Unit | Before → after state | MainPID | NRestarts |
| --- | --- | ---: | ---: |
| coinmaster-paper.service | inactive/dead → same | 0 | 0 |
| coinmaster-hl-stageg-live.service | inactive/dead → same | 0 | 0 |
| coinmaster-connections.service | active/running → same | 1089245 | 0 |
| coinmaster-hl-stageg-testnet.service | active/running → same | 2009732 | 0 |
| coinmaster-hl-stageg-warmup.service | inactive/dead → same | 0 | 0 |
| coinmaster-runtime.service | active/running → same | 1089244 | 0 |
| containerd.service | active/running → same | 1247553 | 0 |
| docker.service | active/running → same | 1067 | 0 |
| fai-app-vpn-shortcut.service | active/exited → same | 0 | 0 |
| fai-content-backup.service | inactive/dead → same | 0 | 0 |
| fai-content-platform.service | active/running → same | 1247629 | 0 |
| hermes-daniil-gateway.service | active/running → same | 1867980 | 1 |
| hermes-gateway.service | active/running → same | 1089318 | 0 |
| myshopai-website.service | active/running → same | 3958400 | 0 |
| nginx.service | active/running → same | 2235511 | 0 |

All container IDs, running state, host PIDs, StartedAt and restart counts remained identical:
- `/hermes-db8f04b6`: PID 26361, running=True, restart_count=0, started 2026-10-11T18:55:10.459126198Z.
- `/fai-paperclip-postgres`: PID 1691527, running=True, restart_count=0, started 2026-09-18T17:53:08.088446388Z.
- `/amnezia-awg2`: PID 455728, running=True, restart_count=0, started 2026-09-02T09:50:06.868233194Z.

## Retained payload verification

| Protected root | Regular files | Logical bytes | Aggregate SHA-256 |
| --- | ---: | ---: | --- |
| `/root/.openclaw/workspace/coinmaster/coinmaster/runtime/.venv` | 7348 | 918120286 | `7c69d73c77da76e5a6c93ab8463a48088d6592e8aeb2c1bcd6db430e883f68cc` |
| `/root/.openclaw/workspace/coinmaster/coinmaster/runtime/var/data` | 4246 | 376149950 | `6ec5042b377bab75e8759658f7d8cf1228f985816c0f7301085bde8c6b0034ee` |
| `/root/.openclaw/workspace/coinmaster/coinmaster/runtime/var/research-datasets` | 164 | 78282855 | `5debdd01875807232abda85ac292faee4b9253abcd258a6281e5a8f09e8802b5` |
| `/root/.openclaw/workspace/coinmaster/coinmaster/runtime/var/research-results` | 77 | 37821607 | `11eb59e1d2be2a515ebd55b52f2f1f135297fa3f74a038a13709d041249ae837` |
| `/root/.openclaw/workspace/coinmaster/coinmaster/runtime/coinmaster` | 123 | 2634932 | `94cb981e6e1de611004c725f97096a5fed1c02d3fa9118d94115c09004e2ab3d` |
| `/root/.openclaw/workspace/coinmaster/coinmaster/runtime/configs` | 9 | 5451 | `b79a5a79fa4e34ec867269a4924fb44c7fe7bd77f083609618c7c5f476ffca8d` |
| `/root/.openclaw/workspace/coinmaster/coinmaster/reports` | 2033 | 144921487 | `cb4c77c4dabb39361dd7770096ee7bd1e5573b80f443914456fe33b3d4224df0` |
| `/var/lib/coinmaster-native-gui/data/runs/jobs` | 6396 | 2746651384 | `c450b7148bd93313af79995b22e6b99713e1d0572c30660904639f8bf663dc18` |

Exact deleted paths, logical/allocated sizes, identities and file hashes: `vps-cleanup-inventory.json` / `.md`. Before/after disk, unit/container snapshots and retained digests: `vps-cleanup-result.json`.

The first execution SSH attempt failed during banner exchange before any remote execution; bounded retry completed successfully.

Supplemental final checkpoint: see `vps-cleanup-final.md`; 100 learned-model files from the original retained report population were subsequently intentionally deleted after separate ROOT GO. Its original report digest/count is historical, not the final surviving population.
