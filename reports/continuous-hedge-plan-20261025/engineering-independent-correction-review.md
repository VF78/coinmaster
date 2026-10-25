# Independent correction review — PASS

Both original P1 findings are closed for source2eb080a14237770d14aa20c05c290f328b2768e0. F05/F06 use R3; existing R2 paired denial remains. Full registered kwargs/defaults are validated and now feed the single shared strategy-config mapping. Reviewer independently compared helper return AST with the actual frozen7d constructor: identical. F01–F04 exercise causal directional requested notional, q0/q1 selection and resulting fill/3TP assertions rather than fixed entry quantity. Effective fixture hashes are separate from archival refs; fixture-only seed/identity/clock/margin context is explicit. Actual native instrument fee assertions and BTC40/SOL20/default1 margin context are present.

No new P0/P1. Eight planned counted engines; ledger0 and rootGOfalse at review. Reviewer ran no tests, engines or public requests. PASS does not grant rootGO or prove native fixture success, economic results, full parity or historical publication latency. Original P1 review retained.

Source: 2eb080a14237770d14aa20c05c290f328b2768e0

New feed SHA256: 5a02a0bc2555404261780cb4979e398494c70194e99317d8db1020fb026b8698

Fixture plan SHA256 (canonical fixtures JSON): 7a967784fb4ccb3d00f01fa128b11739d68c3b1270779981ce7c029f5f0de88e

Checkpoint file SHA256: fff3ba25e3cbf77c24be66830c45eb1835af46e64d28d0051d994faa65c689e6

Probe limitation: ControlProbe inherits NativeProbe (test_native_episode_risk.py30–35), whose _advance_current_day is a no-op and _tier_allows_increase returns True. F01–F04 explicitly call the base WaveOverlayStrategy._advance_current_day for real domain sizing; fixed completed-wave inputs are declared fixture inputs. Thus native engine/cache/fees/margin/fills are actual, but ordinary strategy tier admission is bypassed and automatic signal lifecycle is suppressed. This is bounded engineering lifecycle/config/sizing evidence, not actual venue admission, full baseline parity or economic validity.
