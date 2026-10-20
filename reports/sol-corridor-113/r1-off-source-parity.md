# Targeted OFF source parity against actual winner

Read-only source mapping; no source changes, tests, engine, service or commit. Current report checkpoint9df1ade leaves product source unchanged from5b45a7c. Immutable winner source commit759823d69a74e72b123add5ae775dd8c3aed4ac5 matches all4 control-reference source pins byte-for-byte; targeted minute_risk snapshot also matches that commit. Winner raw SHA matches reference; all710 native order artifact rows match its SHA.

Conclusion: static equivalence is supported for the actual recorded winner path with a declared denial-edge exception; universal OFF parity is false. Reusing control remains subject to root acceptance and focused native OFF tests after R1 approval. No automatic control engine.

| Path | OFF mapping |
| --- | --- |
| strategy/wave_overlay.py | New policy hooks gated OFF; carry busy/check/daily false, fill/bar helpers return; split-ATR contexts empty. BTC entry sizing/PLANREF/TP-IOC branches unchanged. Two denial-edge fixes below remain active. |
| domain/wave_overlay.py | Transfer/retirement credits and half-release lots start zero and have no writer in ordinary OFF path. first_owned follows ordinary first_fill, resets together on full exit; fixed_sigma and half/full calculations reduce to winner behavior. New credit methods unreachable without conditional policy. |
| strategy/split_cover.py | Only additional feature-history collection gate for new flags, all false in winner. |
| research/minute_risk.py | Extra risk/alpha observer callbacks gated OFF; observer flag unused OFF. Same reporting DD observations. |
| research/native_baseline.py | New policy/feed/cache/bar_execution branches OFF; existing winner quote/feed/fees/margin stay same. Sequential native report generation is post-engine housekeeping; explicit run_analysis=True OFF preserves original default. Extra research_conditional_sol=False metadata key changes current config hash without changing economics. |

Actual active edge drift: `_terminal_without_fill` now passes ClientOrderId to failed forced-close cache lookup, and avoids immediate recursive forced-close resubmission after synchronous Denied/Rejected/Expired, retaining fresh-quote retry. Do not roll back these fixes or call them inactive.

Historical-path exclusion: winner orders.csv has710 terminal rows:447 FILLED,263 CANCELED; zero DENIED, REJECTED or EXPIRED. Raw native_order_rejections=0 is secondary only because it alone does not count Denied. Winner run.log has no DENIED/REJECTED/EXPIRED/ERROR/EXCEPTION line. The changed failed-forced-close branch was not observed in this winner output. A separate full native event export is absent; do not claim such an export exists. No future or universal economic-equivalence guarantee follows.

Precise paths/SHA evidence and limitations: r1-off-source-parity.json.
