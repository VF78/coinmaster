# E4 and EP independent saved-output validation

Both pass38saved-output checks each: complete frozen artifact/raw/config/source/input/data/policy pins, native commissions, flat exposure/orders/lifecycle, closed-cycle ledger reconciliation and full global settled DD. No engine/replay/data fetch. Each corrected settled trace was traversed once; P0 cache was reused without any rescan.

E4: TOTAL5631617.35953723, net-profit retention92.65729347120922274896207062%, native fees706755.52937844,535fills (BTC337/SOL198),0liquidations,1051199receipts/0missing. Its ROI component passes; global DD57.58541045962226379114466259% fails50%, so overall50/90FAIL.

EP: TOTAL3992055.58641779, retention65.63351247366905933081845698%, native fees615999.76639960,520fills (BTC341/SOL179),0liquidations,1051199receipts/0missing. Same global DD57.58541045962226379114466259%; both economic components fail.

Saved verifier-E4/EP-risk-cache.json retain all native>=30%global-peak excursions (E4:7,EP:11), native peak/trough/recovery holdings/cash/equity snapshots and6prior A/C/D boundary pairs. Both have24monthly native-equity rows and complete asset zero-to-zero cycle ledgers. Maximum negative BTC fill-net streak E4:10,EP:9; SOL:1each. These streaks exclude unknown funding and do not substitute for marked-equity DD. Asset signed funding staysUNKNOWN; each audit records the unallocated native cash bridge.

Sourcebd04c9b3858bcda40060a08eff488849c69af5d8; all89frozen source files and13actual input pins pass. Config payload hashes independently recompute and match prepared recipes; original B data/policy hashes match exactly. Full independently calculated uncompressed trace SHA256 values and native artifact hashes are retained per audit. Source correctness review remains separate. Root owns economic selection and aggregate report; no further run is implied by this validation.
