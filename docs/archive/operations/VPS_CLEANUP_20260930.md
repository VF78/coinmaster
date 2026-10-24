# VPS CoinMaster artifact cleanup — 2026-09-30

Scope: one bounded storage cleanup on 46.225.163.123. No service restart, order, trading setting, credential, or `/opt/coinmaster` edit. Exact release directory paths and pre-removal `du` bytes are in `VPS_CLEANUP_RELEASE_MANIFEST_20260930.json`.

## Removed

- Old GUI c789 release runtime venv: 909,029,376 `du` bytes; the rest of that release was later removed with 30 other inactive GUI releases.
- `/tmp/cm110-wheel-proof-36341940809/{venv,site,server-site}`: 1,243,246,592 `du` bytes of test installs. The patched Nautilus 1.231 wheel, build source, SHA files, and loopback proof script remain.
- `/tmp/coinmaster-nt-rc5`: 290,426,880 `du` bytes from abandoned Nautilus 2.0.0rc5 research. Qualification notes remain in repo docs.
- 31 inactive GUI release directories, six inactive Stage-G release directories, and the superseded 5529c1b inactive live candidate: summed `du` bytes 27,589,267,456. Most GUI files were hard linked, so this sum is not physical space reclaimed.

Filesystem `/` before: 35,199,418,368 used / 3,090,313,216 available (92%). After: 32,329,719,808 used / 5,960,011,776 available (85%). Actual available-space gain: 2,869,698,560 bytes. No global cache or unrelated directory was pruned.

## Preserved

- Stage-G active PID 2009732 from `/srv/coinmaster/runtime`, active release 81e6318 and previous 5ea1d46 rollback; live Sandbox virtual BTC 0.54262 and one reduce-only resting TP.
- GUI active 5adc0c8, prior 747d3cd rollback, 24daf08 used by the connections broker and mapped by the trader, and cbcc6ba mapped by the trader. Live paths were found by process cwd and lsof before pruning.
- Near-live 86b9d95 candidate, its patched Nautilus 1.231 wheel (SHA-256 `8ff3c6dcc150bc9ced8b96da80c4cf51645acf7efdc2b1d528634a3cad640b46`), matching wheel/build proof under `/tmp/cm110-wheel-proof-36341940809`, and canonical source/runtime venv.
- Stage-G data and genuine Bybit history, #113 reports, journals, backups, archives, secrets, legacy Freqtrade source/history, and non-CoinMaster assets.

## Read-only after checks

Stage-G, GUI runtime and connections broker remained active with the same PIDs (2009732, 2601412, 2263215) and NRestarts=0. Stage-G loopback `/status` returned HTTP 200 with BTC 0.54262, one accepted reduce-only TP, `recovery_required=false`, and `live_order_capability=false`. Public `f-ai.studio`, `app.f-ai.studio`, and `coinmaster24.com` returned HTTP 200 after redirects.

Hermes received SIGUSR1 on client request at 11:30:38 UTC during this window and systemd restarted it from PID 3008443 to 3025575 (NRestarts 1 to 2). The originating client was not established; this cleanup issued no Hermes service action. Hermes was active afterward, its log reported Telegram connected, and protected web routes remained healthy.
