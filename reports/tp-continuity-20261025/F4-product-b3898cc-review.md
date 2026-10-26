# Product b3898cc money/order review

**HOLD — P0=0/P1=2, one consolidated correction batch.** Source `b3898cc3f478b29b8872565bc2318f3b044a6411`; driver not inspected.

**F4-PROD-01:** `_tp_native_event` always performs live cache/intent ownership lookup. But public submit publishes Initialized before cache.add_order; owner is already bound, so first TP fails. On fullfill, typed core removes pendingintent before native genericFill, causing another valid terminal lifecycle failure. Distinguish pre-cacheInitialized and post-terminal delivery using immutableowner/nativeevent/cachetruth; never grant ACK/protection to Initialized, restore consumedrights or relax liveowner checks. Add engine-free real order/event checks for these actualcallback boundaries, partial/terminal/cancel and stale/foreign rejection.

**F4-PROD-02:** marketableDEFER logs only parent/OID/book, without required outstanding amount/duration. Add actualheld/cap/residual/debt_since/elapsed and explicit ordinaryTP/flat or actualDEBT resolution. Waiting above cap is not capPASS. Keep cap/SOL/quantity rules unchanged and verify transition logging engine-free.

Other reviewed paths are narrow and flag-gated: defaultOFF/originalbranch/R3guard preserved; C0/A0 exactB2_F0 samefix with onlyA0flag difference; initial/debt target_lots versus ordinary standing conservation; actualfilled+desiredleaves; ENTRY-only cancellation duringdebt; publicreadonly nativebook/zeroinsert-update guard, unexpectedindex/update/reject/unknownSTOP. No size/TPprice/initialweight/SOL/A0right/fee/funding change found. These source observations are not economicparity or nativeproof.

Saved9group/7996vector purePASS was read, not executed; it misses the lifecycle failures above. Future driver must separately handle only the authorized expectednegativeprobe; validprotectivemodify rejection remainsSTOP. No driver/native/plan qualification here.

Diff SHA `1041245fba78877281df9016105c26788172cbbd08953501503f01ad89d113aa`; pure SHA `b94266685e50897bbef83e9e58cac347b347621cca32d05dfb505c317e115f1a`. Exactsource/nativefile pins inJSON. No tests/engines/Popen/source/gate/ledger edits. Onlythisreviewpairwritten; max4/3FAILED/remaining1 andprefix0/3 unchanged.
