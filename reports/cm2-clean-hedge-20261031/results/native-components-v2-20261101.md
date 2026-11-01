# CM2 v2 native component validation

Source: [6a7a37fc9b1425eed9c56a4ce2443e88621c8257](https://github.com/VF78/coinmaster/commit/6a7a37fc9b1425eed9c56a4ce2443e88621c8257).

Three physical engineering attempts used one fresh native engine/account/journal each. Each scenario contains 12 hours of synthetic data. The original failed attempt is retained; two subsequent R1 cases passed every required component check. No economic run or ROI assessment was performed.

| Case | Physical outcome | Required checks | Raw report SHA-256 |
|---|---|---:|---|
| CM2_V2_E01_JOINT | FAILED, preserved | 5/7 | `ccda2e4526d0976cc3728a0820e6af8fb569198dc7ff101ef6eafa849ca0df0d` |
| CM2_V2_E02_JOINT_R1 | PASS, expected nonflat dust | 7/7 | `bfd19026fa0b5807d242430aa9ec93e10db417b1c9d47fe85bf4c946c7f5dcde` |
| CM2_V2_E03_TRIM_R1 | PASS, expected nonflat dust | 6/6 | `acc1bf65954fc08ae7a32f60db3dbbde8dc5dd8d353059360775b175c33ca8e2` |

The original fixture could not fill a maker order at an exact touch and its one-contract witness was below the stock five-contract partial-fill depth. R1 corrects the fixture touch probability and uses finite native reduction witnesses bounded by actual admitted targets. Production strategy, request guards and the qualified runner are unchanged.

| Actual native observation | Joint R1 | Trim R1 |
|---|---|---|
| Mandatory BTC stop between H1 signals while optional SOL data is unavailable | PASS | PASS |
| Canceled ADD retains the actual held hedge | PASS | N/A |
| Stock partial fill followed by native cancellation | PASS | PASS |
| Revoked old-parent fill strictly between cancel request and ACK | PASS | N/A |
| Finite matched comparator restoration | N/A | PASS |
| Bounded save/load retains domain and native identity | PASS | PASS |
| Actual native signed funding journal | PASS | PASS |
| Actual residual remains blocked after the modeled drain deadline | PASS | PASS |

Both R1 cases retain real native residue. The expected unresolved-dust observation is limited negative-case engineering acceptance. There is no qualified terminal-flat TOTAL, profitability, historical-market execution, cold-recovery or live-readiness result. Test-only numeric fixture inputs are not approved economic defaults.

Current validation epoch: 3 of 8 engineering attempts spent, comprising 1 failed and 2 completed cases. No active engine remains. The remaining 5 slots and every economic stage remain unallocated/HOLD. Earlier campaign history is unchanged.
