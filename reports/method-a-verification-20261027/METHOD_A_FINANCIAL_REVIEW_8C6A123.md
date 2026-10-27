# Method A financial adapter review8c6a123

**HOLD: P0=0/P1=2.** Reviewer engines/tests0; actual P0 money not read.

## FIN8C6-01 [P1] Actual three-TP qualification omits native price/side/instrument validation

`reports/method-a-verification-20261027/method_a_financial_reader.py:95`

P1 held-frame validation checks native status/reduceOnly/owner ACK/no pending command and entitled leaves, then trusts method_a.coverage_ready. It does not check actual order instrument, exit side, finite positive price, distinct outward-positive ordered3TP geometry or bind price to authorized current TP/reference/actual ACK evidence. native_3TP can be PASS with quantities matching even when these required actual protection facts are not independently qualified. Exact a4 source and M1 support the implementation invariant, but a strategy-derived flag is not the independent native financial evidence required by this gate.

Correction: Validate available native Cache order fields against actual BTC instrument/opposite parent side and source-pinned authorized TP geometry/current native ACK-price facts; classify missing facts UNKNOWN. Preserve P0 legacy exemption and do not fabricate native price/ACK facts.

## FIN8C6-02 [P1] Rights-complete gate overstates the performed oldSOL and parent-rights proof

`reports/method-a-verification-20261027/method_a_financial_reader.py:226`

rights_audit_complete is assigned PASS from profile_good and native_pairs. The only oldSOL-specific fill check (117–119) is membership of a level in the AFTER state rights set. It does not verify matching current parent, earned actual-entry fraction, raw legacy denominator/omitted-level crossing-session eligibility, authorized remaining SOL notional or irreversible consumption. For P0 the P1 entitlement checks are skipped entirely. Thus an existing rights set and complete fill snapshots can qualify rights_audit_complete while the contractually required parent/raw-right interface remains unmeasured.

Correction: Add a bounded actual/source-bound MethodA rights evidence gate with explicit raw/actual field mapping, parent/fraction/remaining-right/cross-session proof where required. When the frozen producer lacks a necessary fact, retain UNKNOWN and report the missing evidence; do not normalize unverified rights to PASS or substitute A0/paired rights. Empty actual opportunity must be explicitly distinguished from tested mechanism.

## Verified scope

- Stdlib-only import path: financial adapter imports prefix_common without executing native-import functions; no BacktestEngine/other constructor or native launch found.
- Cash identity uses actual immutable PositionClosed realized NET settlement fees plus signed native funding. It does not subtract fees again; fees separately reconcile to actual trade/closed-history/report amounts. Strict nonzero residual stays UNKNOWN, with no tolerance or funding reclassification.
- Disk tables join actual profile trade IDs to native Position fill event UUID/OID/quantity/commission facts and coherent trade IDs; verified producer coherent native_id is str(event.trade_id), so these joins are compatible.
- Current/snapshot canonical completed row, source/freeze/actual OS/PID/report/manifest/supervisor and four financial roles/four extras/profile/config chains are source-bound. P1 additional common identity/input/profile and normalized P0/P1 kwargs are checked. No runtime or334 wrapper changes in this commit.
- Inherited Decimal50 fractional-tail ES20,136-day calendar,195840 source/195839settled count and chronological separate event/settled peak-DD logic remain; signed funding uses read-only immutable SQLite and actual observer account transitions.
- P0 native3TP exemption is explicit; DD>50 does not reject diagnostic controls. Raw parent-ES missing endpoints remain UNKNOWN. No financial receipt, ledger or P1 GO is written by this reader.
- Seven owner pure groups inspected only. They cover arithmetic/basic parsing/partial profile checks, not a completed actual financial qualification; no actual P0 outcome inferred from their PASS.

P1 all-held-frame TP checks include forced/global-close phases. Missing native retirement/global-close ownership facts must remain UNKNOWN; this review does not authorize a relaxed blanket exemption. Actual P1 lifecycle qualification will require the declared boundary evidence.

One concise packet-only correction for these two qualification overclaims. Existing actual P0 artifact analysis remains a separate read-only root-gated step; no new engine, product correction or P1 permission is inferred.
