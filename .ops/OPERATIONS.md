# Operations — read-only handoff snapshot, 2026-10-24

VPS `root@46.225.163.123`; protected siblings Hermes/f-ai.studio/app.f-ai.studio/VPN untouched.
Production is not any branch HEAD; determine release/seal/config from installed metadata before runtime work.

| Surface | Observed | Scope of evidence |
|---|---|---|
| `coinmaster-hl-stageg-testnet.service` | active/running,NRestarts0; ActiveEnter2026-09-28 07:39:45UTC | systemd only, no trade/account/gate-health assertion. Despite legacy name, this is local native Sandbox, not exchange testnet. |
| `coinmaster-runtime.service` | active/running,NRestarts0; ActiveEnter2026-10-24 06:30:16UTC | GUI/API service metadata only; no browser/content acceptance performed. |
| Sandbox working directory | `/srv/coinmaster/runtime` | installed `.venv` reports nautilus_trader1.231.0. |
| GUI current symlink | `/srv/coinmaster-native-gui/releases/be2f71daac848a20b183ee0167194e5cfa65a5b8` | observed link, not proof of actual process source or full GUI health. |
| `/opt/coinmaster/.deploy-source-commit` | absent | do not infer current release from this legacy path. Sandbox `.release-commit` observed81e6318646b51280497806a1c0492591654b5fe6; verify seal/config on demand. |

Current positions/PnL/balance/entrygate/master funding/agent authorization/live readiness are NOT rechecked by this memory cleanup. Never replace UNKNOWN with last historical values.
Existing live backlog #101 retains inactive82USDC+DP50 preparation and manual-reconciliation boundary. Current blocker: sufficient genuineHL execution/mark/funding history + venue qualification and separate guarded rollout/owner authorization. No request to fund or submit orders now. See #101; older release/recovery/GUI proofs moved unchanged to `docs/archive/operations/`.
Only stock nativeHL connector; no silent fork/upgrade or new recovery subsystem. Preserve sealed source approval and separate paper/live state; virtual trades never migrate to live. Unknown ACK is not rejection; erroneous empty report is not proven flat.
For authorized runtime work: inspect exact installed identity, current persisted controls/account/ownedorders, qualified script and current approval; retain state or fail closed per the actual deployed contract. Do not promise auto-recovery from historical docs.
No services were restarted or changed in this handoff. SSH may intermittently time out; report that rather than substituting local guesses.
