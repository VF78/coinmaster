# CM2 v2 execution units and emergency HWM: bounded engineering evidence

Current source: [1046ddd97610c0367ad7eee2954632ebfa48dd3b](https://github.com/VF78/coinmaster/commit/1046ddd97610c0367ad7eee2954632ebfa48dd3b).

Execution bands now use closed-H1 simple ATR24 independently of the core stop horizon. Their absolute price widths are frozen once per admitted initial/restore epoch. A separate optional backend tracks a growing native-equity peak and persists its emergency latch and immutable trigger record. The configuration default is disabled; the historical comparison profile explicitly keeps it disabled.

| Native engineering case | Physical outcome | Required checks | Raw report SHA-256 |
|---|---|---:|---|
| CM2_V2_E01_JOINT | FAILED, preserved | 5/7 | `ccda2e4526d0976cc3728a0820e6af8fb569198dc7ff101ef6eafa849ca0df0d` |
| CM2_V2_E02_JOINT_R1 | PASS, expected native dust | 7/7 | `bfd19026fa0b5807d242430aa9ec93e10db417b1c9d47fe85bf4c946c7f5dcde` |
| CM2_V2_E03_TRIM_R1 | PASS, expected native dust | 6/6 | `acc1bf65954fc08ae7a32f60db3dbbde8dc5dd8d353059360775b175c33ca8e2` |
| CM2_V2_E04_UNITS_DD_NATIVE | PASS, actual native flat | 11/11 | `b3e687ac288825308382a22bd4c31da2c4d4e71223687ba761aaeea6a761c6dd` |

The fourth case used the existing 12-hour synthetic joint sequence and an explicit TEST-ONLY 40% threshold. Actual native observations confirmed initial cash-peak seeding, a higher observed peak, a threshold crossing that would not cross a seed-only boundary, a latched two-symbol drain, frozen initial execution width, partial native fill/cancellation, old-parent late-fill lineage, subsequent reduce-only submissions, bounded same-engine save/load, signed funding, and an exact native cash bridge. Native cache positions and orders were flat at the end.

The ordinary BTC stop coincided with the emergency event. This proves the emergency path was invoked and retained its latch; it does not isolate that path as the sole counterfactual cause of the close. Between-mark cash-trigger and same-valuation maintenance-breach cases remain constructor-free component proofs, not observations from this native scenario.

The earlier failed physical attempt remains failed and spent. The two earlier R1 cases intentionally retain real unresolved dust; their component passes are not terminal-flat financial qualification. The latest case did not add a dust-seed order after the emergency latch. Each physical attempt used one fresh native engine/account/journal.

One actual public-checkout import and connected constructor-free suite passed: 93 tests, zero engine constructors, Native 1.231.0; every loaded CoinMaster dependency came from that public checkout. These counts are not additive to earlier suites.

This report contains no historical economic result or ROI. GUI binding, manual operational reset, cold recovery, live trading and historical market-capacity equivalence remain outside this engineering acceptance. Test-only order shapes and numeric fixture inputs are not production defaults.
