# CHOP_PAIR_50_NET_v1 — code postmortem

Analysis only at HEAD b631040. No source/config changes, services, engines or backtests.

**Conclusion:** the tested portfolio version failed; optimizing0.5/beta/range alone is unsupported. Carry demonstrably activated. The terminal SOL7000 loss occurred outside carry. This exposes inadequate portfolio-risk coverage, not proof that every pair-recovery idea is unsound.

**Admission worked at least once.** After eight identical native filled-order rows, candidate retained BTC long1.219 on Sep17 and sold SOL222.7 instead of control’s BTC regime close. Native marks58185/131.39 and causal beta1.2114905546983887 give half-cover222.793442…; native lot flooring gives exactly222.7. That requires successful FREEZE/GRANT. Universal rejection by fee allocation, native quantity, account identity or synchronized marks is therefore ruled out. Those guards precede the only new SOL-grant path: carry_pair.py:129–164,207–259.

Both legs exit taker at16:08, off an hourly/Daily boundary. Native admission cash13359.66080444, remaining old fees27.63163160 and BTC notional70927.515 imply B*=13458.21995104. Pre-close native E13556.09116573 less estimated taker close fees57.554026585 exceeds it by40.317188105. This strongly supports RECOVERY (carry_pair.py:233–243); the exact event label remains UNKNOWN. It does not prove a globally profitable policy.

**The fatal SOL was ordinary alpha.** Candidate starts a fresh BTC short Mar30. Every completed Daily through Apr6 is SHORT: for example Apr2close85130.5<EMA86273.4617. Carry requires an opposite current signal and positive actual BTC (carry_pair.py:99–105), so it cannot enter this terminal cycle. Active carry also blocks ordinary intents and changes in frozen BTC inventory (strategy/wave_overlay.py:1228,1752; carry_pair.py:179–205).

Seven midnight SOL BUY1000 fills Mar31–Apr6 are ordinary attempts against remaining earned authority, **not seven proven new rights**. Exact original levels/intent IDs are lost. Ordinary code permits a new Daily attempt while authorized notional remains (domain/wave_overlay.py:438–442). One carry grant instead retries its immutable remaining quantity on the next SOL quote.

Original SOL authority is H*level-multiplier*earned-fraction minus actual spent/allocated/retired notional. H=(gross BTC reference quantity, otherwise initial quantity)*actual entry VWAP/entry beta (domain/wave_overlay.py:438–442,560). It does not shrink with remaining BTC or current equity. Native equity supplies an admission margin/gross veto, not target rescaling or automatic reduction of held SOL (strategy/wave_overlay.py:1888–1897,2234–2272). Margin solvency and gross<=50x are not DD30–50 control.

BTC becomes flat Apr6 18:04. At18:07 both runs are SOL-only at110.88: candidate7000 SOL / E37362.10 gives20.774x notional/equity; control4000 / E818323.02 gives0.542x. These different exposures follow changed episode dates, equity, H, rights, first-SOL sigma and timeout anchors despite unchanged outside-mode rules. Carry’s skipped entries necessarily change that path. Earlier failures also matter: data analysis finds DD50 in a BTC-only state on Oct11 and DD90 in a SOL-only state on Jan13; fixing April alone cannot satisfy DD50.

**Pair limits:** half-beta leaves common-factor and SOL residual risk. B* is a residual recovery target, not a high-water or loss stop. The BTC-only seven-Daily range waits for two completed hours; it cannot bound intrahour gaps or SOL-specific losses inside that range (carry_pair.py:220–277). Old/new fee treatment shows no identified double-charge defect.

A separate edge needs an explicit contract: ARM consumes the right/snapshot before native freeze; rejected carry closes with CHOP_PAIR reasons, while only REGIME immediately evaluates the current Daily after flat (carry_pair.py:109,208; strategy/wave_overlay.py:2606). Its realized frequency/effect is UNKNOWN.

**Three bounded repairs, before parameter search:**

1. Structural whole-book native-equity risk budget covering carry, BTC-only and SOL-only. Precheck existing DD50/DD90 samples against a declared trigger and execution limits.
2. Structural SOL ownership: consider closing original SOL when actual BTC becomes flat. Precheck every existing such interval, including profitable ones; this sacrifices standalone alpha and cannot fix BTC-only losses.
3. Protocol/implementation: durably save lifecycle and terminal state before packaging assertions; specify rejected-carry handoff and stale ARM snapshots. Precheck a complete transition/reconciliation table.

Full admission/exit/grant counts and liquidation/domain state remain UNKNOWN. No future variant’s ROI/DD is claimed. Details and evidence paths are in postmortem-code.json and postmortem-data.json.
