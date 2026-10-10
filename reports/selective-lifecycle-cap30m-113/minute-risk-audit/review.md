# CM113 narrow independent minute risk review

Frozen source: eba62c3b5aacae341644bb05adbf7735d2751ee5, baseline 9f892974afe33820fca457bbb63cdec0433563e7.

Verdict: one blocking boundary-reporting correction pending; no second blocker found in this bounded check.

Scope read: exact native_baseline observer diff, minute_risk.py, focused native observer tests, existing TierMarginPolicy and actual liquidation trigger/callback ordering, concise audit README and 24-passed focused test log. No full replay, broad suite, pilot/config/service/order action or source edit performed.

Observer is opt-in and reads native account cash, native position unrealized_pnl and a separate existing TierMarginPolicy. It publishes no synthetic high/low event and mutates no strategy policy/account/engine execution state. Preserved class name protects native order identity. Focused native long/short roundtrip proofs include actual funding debit/credit, exact total/cash/fee/config/policy parity and normalized order/fill parity excluding only engine init_id. Streaming trace completeness and seeded distinct-excursion ranking have focused proof. High-notional MM is checked against captured tier monotonicity; opposing asset extrema are conservatively summed and explicitly conditional.

BLOCKER: final completed bar is delivered at end_exclusive. Both postquote samples at that timestamp are currently included in interval close drawdown/minimum/TOP3 trackers and may contain terminal settlement. Archived interval economics explicitly excludes terminal fills at end_exclusive. Required correction: retain final prequote snapshot/envelope as completed-last-bar/interval-end-left-limit; export both final BTC/SOL postquote snapshots separately, exclude them from interval trackers, retain them in streaming row completeness; add actual-native open-until-terminal-close proof.

Known model limits are mandatory in final reporting: current liquidation rule is native equity <= captured tierMM, with no additional liquidation-fee reserve. Thus a lower-equity > upper-MM conclusion applies only to this conditional fixed-exposure model. Venue fee/margin applicability, intrabar execution/path, cross-asset simultaneity and callback cache/cash timing are not proved by OHLC or economic parity. Adverse breach is potential, not a confirmed historical liquidation. One isolated replay remains gated on corrected review GO and full economic/order/fill/funding parity.

## Corrective review — GO

Corrected frozen source: c70f920d4daf67f3aa8e880c938cfcdfeb60bc63.

Reviewed only the corrective minute_risk/native_baseline/test diff and the updated focused evidence (25 passed in 11.42s). The recorder now receives exact end_exclusive_ns, exports both boundary quote snapshots separately and excludes them from interval curve aggregation, while retaining final prequote and 3N trace completeness. Actual-native terminal-exposure proof shows final prequote exposure held, post-boundary flat settlement/exit fee lower than the interval minimum, and expected curve counts/minimum exclusion. Existing-model-only MM/no extra liquidation-fee reserve limitation is explicit.

Verdict GO for ONE isolated observability replay at this exact source, subject to root's existing input/process isolation and exact winner total/fee/order/fill/funding parity gate. This is implementation/replay readiness, not already measured full-interval risk or historical venue-safety proof. No remaining blocker in this narrow review.
