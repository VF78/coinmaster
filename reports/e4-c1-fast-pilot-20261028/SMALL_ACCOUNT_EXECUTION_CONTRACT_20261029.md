# Small-account execution contract — 2026-10-29

Status: **HOLD; source analysis only; no release/START qualification.** Base source is `082ce016248faa9be5736cd67ba8b4cd9bafbf15`; the qualified successor will add live-health and initial-deposit policy. No HTTP, native model/engine, order, service or transfer was performed for this analysis. The old private report's numeric-cap DENY remains immutable. The owner's new direct instruction supersedes that cap for preparation: start with the actual available verified USDC deposit under explicit `ACTUAL_AVAILABLE_USDC_AT_FRESH_FLAT_INIT`. Implementation/qualification is pending; no new numeric confirmation is required. Actual equity/address remain private. Never replace reported equity with `min(equity, old_cap)` or relabel excess funds as a separate budget.

## Public-market arithmetic, conditional on price and rights

Saved public book: BTC bid/ask 79907/79908 USDC; SOL 99.738/99.739 USDC. These are historical snapshot inputs, not fresh quotes. Stock metadata maps BTC size step 0.00001 and price tick 0.1; SOL size step 0.01 and price tick 0.0001; min_notional is 10 USDC, min_quantity is unset. Instrument metadata is retained unchanged.

At executable price P and size step s, minimum-notional lot count is `m = ceil(10 / (s*P))`. Floor every strategy quantity to native lots; never round up to satisfy a minimum. Check each child's own price, including the BTC second-child 0.0025 discount. At these snapshot prices:

| Planned operation | BTC | SOL |
|---|---:|---:|
| One >=10 USDC order | 13 lots = 0.00013 | 11 lots = 0.11 |
| Two 50/50 children both >=10 | 26 held lots minimum | 22 held lots minimum |
| C1 cut and remainder, quarter BTC / half SOL | 52 held lots minimum | 22 held lots minimum |
| SOL ordinary half followed by C1 half of remaining | — | 44 held lots minimum |

General split conditions are `floor(L/2)>=m1` and `L-floor(L/2)>=m2`; C1 BTC requires `floor(L/4)>=m_cut`, with separate cut/restore/remainder price checks. SOL ordinary half and C1 half use `floor(L/2)`. TP1/TP2 are floor(0.2125*initial lots); TP3 owns the exact remaining lots. Omitted zero levels retain the canonical reference allocation; partial confirmed holdings use the existing proportional target planner. DP whole-close uses actual held quantity after cancellation/reconciliation, not a rounded-up order.

Illustration with hypothetical equity exactly 81.84 USDC, **not the actual account assessment**: BTC gross long/short is 563/806 lots under 5.5/7.875 multipliers. Smallest nonzero TP1-only planned net is 119/171 lots; split children are 59+60/85+86. If the parent closes after exactly that first child fills, its C1 quarter is 14/21 lots, worth about 11.18712/16.78047 USDC at the snapshot executable prices. Thus ordinary planned sizes can fit the approved cap conditionally.

For the isolated current-price lattice calculation across nonzero retained TP masks, fully filled net parents need gross >=245 lots: equity about 35.595382 long /24.859956 short. Including a completed parent containing exactly one fully filled first split child requires gross >=490 lots: about 71.190764 long /49.719911 short. These are arithmetic lower bounds for those enumerated holdings, not a release minimum, future-price guarantee, or proof for arbitrary partial fills. Real SOL size additionally depends on `H = BTC_reference_qty*entry_vwap/beta`, level multipliers 1.75/2.625/3.5, actual fractional rights, existing/pending positions, venue side limits, leverage, shared USDC collateral and fees. No single funding number proves all these gates. The earlier 72/108 formula PASS is not actual-account capacity.

## Corrected native minimum-notional boundary

The earlier blanket claim that pinned RiskEngine necessarily denies every sub10 reduce order is **incorrect for its margin-account branch**. Static inspection of installed stock source found:

- Hyperliquid `HyperliquidExecutionClient.__init__` sets `account_type=AccountType.MARGIN` (`adapters/hyperliquid/execution.py:122`). `QualifiedHyperliquidExecutionClient` inherits that initialization. Unified projection calls `generate_account_state` and does not change account type.
- RiskEngine `_handle_submit_order` performs reduce-only validation, `_check_order`, then `_check_orders_risk`. `_check_order` checks price, quantity precision/bounds and GTD expiry; it does not check min_notional.
- `_check_orders_risk_for_account` returns True for `account.is_margin_account` before the later min_notional check. The check at `risk/engine.pyx:921` applies on the subsequently reached cash-account path. Its later reducing-SELL balance exemption is also not a min_notional exemption.
- Stock `Strategy.close_position` creates an ordinary market reduce-only order for the actual position quantity and calls `submit_order`; it provides no special venue full-close primitive.
- Product `RecoverableWaveOverlayStrategy._submit_intent` explicitly enforces min_notional for ACTIVE BTC TP reductions and records `LIVE_PARTIAL_PROTECTION_QUANTITY_OR_NATIVE_MINIMUM_UNKNOWN` if unsupported. Base `_submit_intent` enforces opening minima; `_record_submission` also runs conservative `native_lifecycle_feasible` for opening parents. These are real product gates, independently of the stock margin early return.
- Product `_owned_reduce_capacity` / `_owned_reduce_allowed` enforce held-minus-all-pending and lineage, not min_notional. `WaveOverlayStrategy.submit_order` validates latched DP `MARKET_EXIT` shape and records its actual quantity. `_submit_forced_close_on_quote` likewise creates an exact-held IOC reduce-only order. No supported full-close exception is established by those functions.

Consequently sub10 ordinary TP protection is an explicit product minimum boundary. A sub10 whole-close on the expected stock margin route is **not statically proven blocked by RiskEngine**, but native composed dispatch and venue acceptance remain unqualified. Actual runtime Cache account type is not established by this source-only inspection. A cash-account Sandbox denial must not be generalized to margin-account live behavior.

Arbitrary partial execution can leave BTC 1–12 lots or SOL 1–10 lots at these prices. Additional capital cannot rule out that event. Root's official-document review found [MinTradeNtl](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/error-responses) and [reduce-only semantics](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/order-types), without a documented sub10 full-close exception. Do not infer venue acceptance from native dispatch, nor native denial from instrument metadata alone. Until exact supported closure is qualified, retain the position and honest `EXIT_INCOMPLETE`/manual reconciliation on rejection or unresolved exit. No bypass, metadata deletion, top-up, flip, fake flat or uncertain resend is permitted.

Installed stock source hashes, read without importing native code: `risk/engine.pyx` SHA256 `bf51d0d886d98c4e95c1ef1aa74e4dd24a236a9fc149fb646a1f038d7dfb8d84`; `trading/strategy.pyx` SHA256 `c8c72a2b4796fa2c70fd1d8ec2c82172c8693e8274e3e397f8e8756707177246`. Installed source root: `/root/.openclaw/workspace/coinmaster/coinmaster/runtime/.venv/lib/python3.12/site-packages/nautilus_trader`.

## Saved-helper identity against 082

The saved helper declares source `83e8931f9e24fbdf68dd3aca4a6deb5d13acc61d`. Seven of nine complete file pins match 082 exactly. Paths below are relative to runtime:

| File | 082 SHA256 | Saved pin |
|---|---|---|
| coinmaster/strategy/wave_overlay.py | 561a5cb85fb17a1fdfd38b49dd67ab235909a4e8f278ce8ae8769860a4ca97ee | exact |
| coinmaster/strategy/split_cover.py | d4c154132e22da548cd3e573abe5713d14c493cee95d9b1ebf5af10b276094d2 | exact |
| coinmaster/strategy/residual_recovery.py | 55b4db26540a297a8d53dfe45be446136c7c0df3956ba73005013be7a5112483 | exact |
| coinmaster/domain/wave_overlay.py | 797625eaed18a59ecc9a02ba8786ae915b63637a8091930392c84debbf303531 | exact |
| coinmaster/ops/hl_live_money.py | e81488c33a04f374006418a09380db0051a9cb3c6d91a95dd7e73078b5fc12e9 | exact |
| configs/hl-live-v3-dp50.candidate.json | 310173f7553ee7b048ee5332d4d86b5789f792d57c2aa95a3d8cd1b57b7d80e6 | exact |
| coinmaster/ops/hl_live_profile.py | b9ac119bfc26ebb45d8df3f9472a73562278461d2aead4b7ee8d6ddc8db0d884 | exact |
| coinmaster/ops/hl_info_receipt.py | abf87351f59e7fc8e3c513164e0c0e2b8867eff568af91455cc0f48a02fd5c96 | saved 908c702b70a8a8265b48d07d0feaf19d00a7cb1703d372250ee738d40da7a9f4 |
| coinmaster/ops/hl_live_execution.py | b142b3947db223156a9b28d8b0b24a6e0f3ac111515e735aa606aeb7d7bcadee | saved 38675c659261eb9cfc73000abc91a1814f9c1f346d97c53a4a78389cca3f9fc3 |

The two changed files add applied-fill anchor binding and bootstrap/final-handover verification. They are lifecycle authority changes, not sizing changes. All four definitions actually extracted from those files match exact source-segment SHA256 on both sides: `IncompleteInfoReport` 892d946b1977b7cbfc1a22ea6b487e20585c54aa690b7dd96fcd09417b6f3a5c; `ReadinessInfoBudget` b9051ee41f55c609c9194fd2c655f7e7bb901dfd28294cc8a5238d0b642a773d; `finite_generation_reservation` 6d9f0fc94c424c921fd674a84be3eff51fe831862eccf85a6925b4891eac1c30; `held_sample_reservation` c784fd2a8f7aea6ed6c57fd321e13935ce19273ed66c1575082b8761ffa45a29. This supports reuse of arithmetic, not promotion of the old report to full 082 lifecycle acceptance.

## Release tooling and next qualification

`runtime/scripts/release_manifest.py` is the existing generic payload manifest generator/verifier. `runtime/scripts/stage_live82.py` stages an inactive legacy Live82 release; it hardcodes 82/V3+DP50 identity and requires `strategy_sha256`, absent from the selected-profile schema. It is not qualified current E4/C1 selected-profile packaging. `deploy_stageg_sandbox.py` targets the separate Sandbox service and must not be reused as live release authority.

The current loader is `runtime/coinmaster/ops/hl_live_profile.py:load_live_profile`, preferring `configs/hl-live-selected.profile.json`. ACTIVE requires schema `coinmaster-live-selected-c1-v1`, profile `E4_C1_ACTIVE_SELECTED`, exact winner/config/pins, DP55/retained0.45 and separate owner-start requirement. The alternative `E4_C1_INPUT_READINESS_ONLY` is manage-only. The repository has no tracked selected profile. `runtime/tests/test_e4_c1_active_authorization_pure.py:profile_metadata` creates synthetic temporary profiles; these are not account-specific sealed release artifacts.

Next work: qualify the explicit actual-initial-deposit policy while preserving legacy caps, fresh virgin-flat/native parity, atomic E0/H initialization and no H reset; later-deposit support stays deferred with existing quarantine. Exact-source native A/B acceptance and a fresh bounded private capacity check need their own root admission. A stock-margin sub10 whole-close dispatch proof must remain separate from venue acceptance; product TP refusal, DP ownership, pending bounds and honest rejection/incomplete state must be retained. Finally seal a current selected profile/payload/runbook/rollback, obtain owner VERSION approval and run the installed benchmark. START remains separate. Existing failed attempts stay immutable; no retry follows from this document.
