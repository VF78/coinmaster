# R1 focused native verification plan — NOT RUN

Use the existing native fixtures/helpers in test_native_sol_risk_first.py, test_native_conditional_hedge.py, test_native_alpha_cushion.py and test_native_minute_risk.py. New focused corridor tests may be a small dedicated file. These are bounded synthetic native tests only after root implementation GO; no historical engine or new control.

1. OFF native fills/orders/account/right state parity with unchanged control configuration. Healthy ON alpha both BTC sides matches OFF actual native fills through partial, half/all exits and repeated cycles. Existing variants stay unchanged.
2. Convex solver nearest-alpha lower/upper boundaries, cost breakpoints, adjacent lot rounding, >100% lawful alpha, B=0 and 0 inventory, negative C, invalid beta/data/residual infeasibility and margin-only infeasibility; pure deterministic arithmetic where no engine is needed.
3. Actual native BTC-only minimum protective increment; excess alpha trim keeps maximal lawful alpha; BTC-flat pure-protection removal versus lawful SOL-only budget; no flat opening without permission.
4. Causal Daily90 beta/a/u update after completed available pair only, refreshed in SOL-only and independent of alpha-beta. Future bar/mark and stale checkpoint fail DATA_UNKNOWN. Unequal but fresh instrument mark timestamps accepted.
5. Native partial fill/cancel/late fill/Denied/UNKNOWN ACK race: owned leaves bound worst case, no duplicate, explicit status, retained required exits; fresh native quote executes retry only when legal.
6. Accepted BTC Q2 reserve remains available, no change to split quantities/PLANREF/TP-IOC; no BTC regime/TP/trail delay. Native executor effects separately measured.
7. Protection release needs fresh opposite closed15m and .8C; alpha restore needs fresh permission and .8C. Canceled/retired old IOC not revived across repeated quotes/Daily updates/cycles; original fill/notional/right clocks retained.
8. Completed-account observer E/H matches actual native account plus native PnL after fill/close; one native close, fees and realized gain count once; H monotonic over BTC-flat, SOL-flat, new episodes and checkpoint restoration. Dirty fill callback never uses provisional cash.
9. Packaging fault injection at inner boundary assertion and outer metadata validation: atomic raw native result/events/counters and native fills/orders survive byte-valid; successful packaging preserves raw identity; partial snapshot clearly incomplete. No economic engine to reproduce known CHOP audit loss.

Acceptance evidence: exact source hashes + command/log + native assertions/receipts. Reuse existing passing scope, broaden only for changed execution/accounting integration. Report source-parity limitations; do not infer economic parity solely from focused tests.
