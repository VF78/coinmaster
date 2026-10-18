# SOL risk-first bounded tradingdiff review — before frozen proof

**BLOCK pending one correction batch and native proof.** WIP source read only; not a frozen-source final verdict. No reviewer runtime/test/index edits or engine runs.

- **[P1] H2_CHILD_Q_OVERRIDE**: SOL child can submit whole acceptedQ rather than remaining leg budget, causing overfill/excess margin and violating fixedQ.
  Evidence: strategy/risk_first_sol.py:278 passes child entry_override_qty; strategy/wave_overlay.py:1764 honors override for BTC_ENTRY only and SOL requested_notional recalculates full original quantity.
  Correction: Apply explicit accepted SOL child quantity override before original requested-notional sizing; freeze initial groupQ once. Native firstpartial, siblings, cancel/fallback must conserve exactQ.
- **[P1] H3_FLAT_CEILING_AUTHORITY**: Fresh original auth or higherstage while BTCflat cannot clear ceiling as pinned. At stage0 freshlateO can remain accepted/pending without filling because target is capped at held every quote.
  Evidence: strategy/risk_first_sol.py:71 clears ceiling for new lawful auth, but149 unconditionally relatches ceiling whenever notbqty.
  Correction: Latch ceiling on actual transition to BTCflat/lowerstage, retaining it until allowed reset. Verify BTCflatstage0 freshlateauth and lowerstage noautoreadd on laterquotes/hourly/BTCdecrease.
- **[P1] H3_MIXED_MARK_PEAK**: Sequential BTC/SOL mark delivery can create an artificial portfolio highwater from one new mark and one old mark, permanently changing DD/stages.
  Evidence: strategy/risk_first_sol.py:35-41 accepts fresh but unequal mark timestamps and samples on each mark callback; existing v3 sampling checks paired current timestamps.
  Correction: Use synchronized causal paired marks for pre-fill equity highwater; prove same-timestamp sequential paired updates and global peak persistence across two BTC episodes.

Real selected-control vs risk-inert native parity including composite15m/hour data and bar_executionFalse path: BTC split/P0/TP IOC and originalSOL order/fill/liquidity/fees/cash semantics. Runner change is not automatically sameexecution. CLI selected-BTC flag validation exists; constructor has weaker direct-instantiation guard, disclose boundary.

H3 min((1-w)*Oref,Olive)+wQc and latched recovery ceiling remains pinned. DefaultOFF economic regression and causal720hour factor/globalnativeequity proof remain required. Risk-first variants untested until final frozen evidence.

All findings sent together to engine/root for one substantial correction, then focused evidence/final source-pin recheck. No total audit or speculative parameter optimization.
