# Frozen source contract

Base bd04c9b3858bcda40060a08eff488849c69af5d8. Default-off research_sol_residual requires S; research_sol_minute requires residual S. R1 = original E4+S plus residual actual BTC-flat eligibility. R2 = R1 predicates/thresholds/half target on actual native minute paired quotes instead of H1. No new BTC exit, fallback, right retirement or SOL grant.

Residual eligibility requires prior actual BTC fill (positive native-confirmed domain initial qty), domain open qty exactly zero, matching closed split parent, no unfinished split, no native BTC position, and no BTC pending/queued/open/inflight ownership. Immutable plan beta remains mandatory and valid. Opposite actual BTC/SOL and beta-weighted dominance remain unchanged while BTC is open.

R2 runs on SOL quote at a minute boundary only after both cache quotes have exactly that timestamp, existing mark freshness passes, and the native settled observer receipt has this timestamp and source exactly one minute earlier. It consumes that minute once. Existing causal SOL mark replaces H1 close solely for adverse2% evaluation. Global settled DD40 and frozen lot-floor50% remaining stay unchanged. Real observer integration proves first minute cannot act without receipt; next CustomData finalizes settled native equity before current paired quotes produce one actual risk fill.

Existing task/cancel/unknownACK/partial/latefill and ordinary/mandatory priority mechanisms are reused. Already-owned risk survives BTCflat/newBTCentry with same frozen target; no predicate reevaluation cancels that target. SOL adds remain blocked until native SOLflat and no owned work. No coefficient/grid/fullcut/profitfloor/new account/PnL or matching data path.

Flags OFF preserve original next_band config keys and S_TRIGGER fields. P0 must prove actual native XS parity, not merely unit tests. R1 may diverge earlier than the previously examined October prefix if an earlier eligible residual cycle exists; actual first divergence must be reported. No 50/90 guarantee and no full research launch before root GO.

Verification: 24 focused tests passed before final source/source-age negative additions; final one full relevant pass 137 passed,284 warnings,20.09s. Native R2 test uses real NativeMinuteRiskRecorder, observed_strategy_type, native CustomData marks, paired quote events and actual reduction fill; no manually populated settled receipt in this integration test. Other gate unit fixtures deliberately seed receipt fields for negative coverage.
