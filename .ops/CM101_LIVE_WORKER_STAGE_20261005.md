# #101 isolated live-worker stage — 2026-10-05

Technical stage is installed and inactive. This is not permission to place real orders and is not an unconditional READY_FOR_OWNER_LIVE_APPROVAL claim.

- Source commit: `b20814019202ec93b234c052d5d8e92448c85a17`.
- Release: `/srv/coinmaster/hl-live/releases/b20814019202ec93b234c052d5d8e92448c85a17-v0-81e6318-wheel-8ff3c6dcc150`; separate `/srv/coinmaster/hl-live/current` pointer.
- Release-tree SHA-256: `d67d2a647f49a8e22b052208ccc7cc6232be427b74392417989a0adc3794c8c1`.
- Native wheel: pinned Nautilus 1.231.0, SHA-256 `8ff3c6dcc150bc9ced8b96da80c4cf51645acf7efdc2b1d528634a3cad640b46`; already qualified artifact, no rebuild or version change.
- Exact sealed V0 strategy/domain overlay comes from `81e6318646b51280497806a1c0492591654b5fe6`; strategy SHA-256 `0edecde9548533004292d5a6174ef6aeb77596817080c4a160f72aa2dc7dd511`. The current canonical strategy is not silently accepted by the live constructor. Fee-floor V1 remains disabled/absent in the staged V0 config.
- Installed unit `coinmaster-hl-stageg-live.service`: disabled, inactive, MainPID=0, Restart=no; no approval file. Dedicated user, state/journal, runtime lock root and port 18184. Public warmup copied to the live data namespace; no virtual account/episode/journal imported.
- Standard systemd LoadCredential selects the exact existing broker record. Master is explicit in the native execution config; keys are not copied into source, release metadata, GUI or research. Existing Sandbox live-route guards remain intact.

## Implementation and evidence

Separate composition uses FeedBook/FeedObserver, verified Bybit warmup, sealed V0 strategy, RecoverableWaveOverlayStrategy, qualified native factory, existing money contract and durable native submission/fill journal. Native selected cross leverage and authoritative accountValue drive admission; no Sandbox leverage or dummy FX enters live. Native account ID `HYPERLIQUID-master` is also the deposit-protection scope. The worker reuses public warmup refresh on a background thread every 900s; a failure keeps the existing stale-data admission gate closed.

Clean-flat bootstrap is followed by current-process owned parity. Ordinary stale money requests the existing serialized refresh and leaves account/status unavailable; it does not permanently latch. Actual worker snapshot failures revoke the qualified client and persist a fsynced manual-recovery marker. Any restart with journal/checkpoint/uncertain state requires manual recovery; no automatic open-position takeover.

Qualification artifacts are retained under `runtime/var/cm101-qualification/`:
- `relevant.log`: exact V0/patched-wheel native relevant run, 100 passed and four failures, all due to newer replay-wrapper fee-floor keyword assumptions.
- `correction.log`: four failures plus worker checks rerun after wrapper-only compatibility correction, 11 passed. Native commission journal unchanged.
- `final-focused.log`: final worker/preflight set, 13 passed.
- `unprivileged.log`: staged actual qualified-client construction under coinmaster-hl-live, seven passed without connect/run/order or real credential access.
- `singleton-uid.log`: LIVE_UID_SECOND_ACCOUNT_OWNER_DENIED.
- `install.json`: release identity and reproducible no-start command.

Existing connected fake transport proves a 100-USDC account through BTC entry, partial TP/cancel, BTC replacement reduction, SOL add/exit and BTC flat, with six owned orders/six fills, 0.2790 native/journal fees, 99.7210 final equity, and at least nine strict generations; foreign/unknown/stale and denial cases remain fail-closed. This does not claim exchange smoke, natural mainnet fills, or autonomous restart takeover. Independent narrow review was completed before staging. Installed tree, wheel and native extension bytes were independently compared; systemd unit verification succeeded.

No-start verification (test fixtures use synthetic key/account and never connect):
```sh
runuser -u coinmaster-hl-live -- env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/srv/coinmaster/hl-live/releases/b20814019202ec93b234c052d5d8e92448c85a17-v0-81e6318-wheel-8ff3c6dcc150 COINMASTER_TEST_LIVE_WARMUP=/var/lib/coinmaster-hl-stageg-live/data/current/manifest.json /srv/coinmaster/hl-live/releases/b20814019202ec93b234c052d5d8e92448c85a17-v0-81e6318-wheel-8ff3c6dcc150/.venv/bin/python -m pytest -q -p no:cacheprovider /srv/coinmaster/hl-live/releases/b20814019202ec93b234c052d5d8e92448c85a17-v0-81e6318-wheel-8ff3c6dcc150/tests/test_hl_live_worker.py
```

## Current external blockers

Read-only official Info observations: MASTER_ROLE_USER, AGENT_ROLE_MISSING, ACCOUNT_COLLATERAL_ZERO. The existing broker record's saved VERIFIED state is stale relative to current exchange authorization. Derived existing public API wallet `0x5cbba958a0a884c2766bb61be1de2b7055f65d79` matches the sealed agent fingerprint `e7940e7cc81dab6c3755a8752ff180e61d5bfe7f739e5686990885896e2e7ab2`. Reauthorize this exact existing agent for the existing master and repeat bounded read-only preflight; no forced rotation or new account. Do not request funding while delegation is missing. A funded exact 100-USDC clean-flat account still requires successful native margin/metadata/lot/minimum/fee qualification, then separate exact-release real-order approval and approved exchange smoke. The technical tests did not wait for funding and did not send exchange orders.

Preserved running Sandbox: release 81e6318, PID 2009732, NRestarts=0. Native flat does not erase the retained SOL-rights episode. GUI routing remains bound to this dry-run. No Sandbox/GUI service restart, real order, transfer, exchange leverage mutation, protected-route or VPN change occurred.
