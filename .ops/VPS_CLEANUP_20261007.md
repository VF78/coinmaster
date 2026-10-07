# VPS cleanup — 7 October 2026

Owner-authorized safe cleanup only. No service restart/deploy, order, mode/parameter change, protected application edit, source rewrite, journal truncation or market/research data removal.

Removed exact allowlist:
- Two inactive GUI releases:24daf08909e4892b942adabcc40c45f0e7c78362 andcbcc6bae8c92f95eb08861c7568d46cd8a8a770a. Archived stage receipts/identities; no active process/unit/symlink references. Activeea071ab, knownrollback7fe1e19 and its prior chain93eb/5adc/747 retained; no broken active/rollback symlinks or .pth targets.
- One temporary proof wheel under /tmp/cm110-wheel-proof-36341940809. SHA8ff3c6dcc150bc9ced8b96da80c4cf51645acf7efdc2b1d528634a3cad640b46 matched retained approved live/candidate copies before and after deletion. Small proof script/hashes/receipt preserved; source archive retained.
- /var/cache/apt/pkgcache.bin andsrcpkgcache.bin: regenerated binary indexes only. No active package transaction/lock holders; PID868 was only the shutdown watcher. Installed package database, configurations, package sources and service state unchanged.

Measured per-action available-space gains:6,848,512 +189,034,496 +117,022,720 +6,754,304 bytes. Net whole-task gain318,095,360 bytes (background allocation makes it slightly different). Final available3,761,819,648 bytes; usage91%, compared with initial92%. The initial old-release uniqueness estimate was flawed and discarded; du allocation is not physical free-space gain when packages use shared hardlinks.

Preserved: canonical checkout/.git/user changes, trading journals/backups, real warmup/market data, all V0/V1/G4 research artifacts/native7day results, secrets, runtime/live environments and approved wheel, rollback chain. Docker/Hermes/f-ai.studio/app.f-ai.studio/VPN untouched. Largest remaining non-CoinMaster directories belong to protected projects or shared installed software; no generic docker/cache prune or package uninstall.

Final service checks: SandboxPID2009732/NRestarts0; GUIPID2129174/NRestarts0; brokerPID2129221/NRestarts0. Fresh native read-back confirms same epoch10e39dc6efa64c8b820b174c0a5b65fe/cursor23/equity11319.40534863USDC/fees47.45465137, flat positions/orders, recoveryfalse, native thread alive and PUBLIC_FEEDS_READY. Coinmaster24.com/f-ai.studio/app.f-ai.studio returnHTTP200 with redirects followed.

Exact paths/hashes/physicaldf receipts: VPS_CLEANUP_20261007.json; tiny preserved evidence:artifacts/vps-cleanup-20261007/. No production implementation changed.
