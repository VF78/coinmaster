# Exact 6,077,107.23887483 winner: native risk and time statistics

Source is the selected control artifact, not CHOP_PAIR_50_NET_v1 and not the embedded older control_terminal_total 3,386,491.65211338. Seed 10,000 USDT; interval [2024-09-01,2026-09-01), UTC. No new engine, backtest, optimizer or PnL matching engine. Existing artifact status is NOT_FAITHFUL_DIAGNOSTIC with ranking_eligible=false; these are statistics of this exact run, not a venue-fidelity approval.

## Measurement and verification

**all_native_DD:** Seed plus every interval native pre/postBTC/postSOL sample; final prequote at end-exclusive included; two post-boundary settlement rows excluded.

**calendar:** One post_quote_paired_close per source minute, except finalminute uses final prequote left-limit. UTC period assigned by source bar_open_ms. Internal period ends include their boundary callbacks; finalend excludes settlement. Min/max and within-period DD in calendar CSV use this paired-minute sampling, not allphase DD.

**elapsed_time:** Minutes sampled at one paired sample per source minute. Threshold sampled DD uses sampled runningpeak, with separate allnative threshold entry counts.

**rolling:** Exact 1,60,1440,10080,43200-minute changes of paired native equity. 43200 is30days, not variablecalendar month.

**exposure:** Actual native position quantity times same completed-bar close, divided bynativepaired equity; native side2LONG side3SHORT. Gross/share/net-directional not beta-adjusted. No realizedPnL inference.

**OHLC:** 67.54771031869252420136632742% is a separate conditional favorable-to-later-adverse bound. No samebar extremaordering or historicalpath assumption.

**unknown:** Signedfunding, realized perasset PnL and detailed venue fidelity remain UNKNOWN; reportstatus NOT_FAITHFUL_DIAGNOSTIC and ranking_eligible false inherited.

Checks:
| Check | Value |
|---|---|
| trace_sha256 | f9b59944ac969f5441babdf2103637f7cd179c6d18971c7bf95c0e2c46e38a0b |
| raw_sha256 | 4dbfaf0d228f27ebc5e24157b613b0ddd279bffa2d163d042684bdad13bbec1b |
| trace_rows | 3153600 |
| interval_native_rows | 3153598 |
| interval_native_with_seed | 3153599 |
| sampled_minutes | 1051200 |
| monotone_timestamps | True |
| contiguous_bar_opens | True |
| reproduced_all_native_DD_percent | 66.31878024969152066570091116 |
| expected_DD_percent | 66.31878024969152066570091116 |
| DD_exact_match | True |
| months | 24 |
| days | 730 |
| daily_monthly_exact_chain | True |
| drawdown_csv_rows | 1223 |
| daily_curve_rows | 730 |
| export_repair | Last unrecovered episode has an extra end_observation field; recovered directly from durable JSON top10. No second trace pass. |

The all-native curve includes 3153598 exported interval samples plus the initial seed, consistent with the existing 3153599-sample summary. Two post-boundary rows are separate settlement observations. OHLC conditional bound remains separate from observed native close DD.

## Global drawdown excursions

An excursion begins when equity falls below the attained global high-water mark and ends at its first recovery to or above that mark. Equal high-water observations reset the recorded peak timestamp to the latest attainment. CSV includes every excursion, including unrecovered terminal excursion. Clock durations use timestamps; zero-duration callback excursions may occur because native phases share timestamps.

Episodes: 1223; unrecovered: 1. All-native maximum DD 66.3187802497%. Minimum relative to seed: 4,530.57414701 at 2024-10-03T15:44:00+00:00; loss below seed 54.69425853%.

### Largest ten by percentage
| ID | Peak UTC | Peak equity | Trough UTC | Trough equity | DD % | DD amount | Peak→trough days | Recovery UTC | Peak→recovery/end days |
|---|---|---|---|---|---|---|---|---|---|
| 37 | 2024-09-11T14:00:00+00:00 | 13,451.34 | 2024-10-03T15:44:00+00:00 | 4,530.57 | 66.3188 | 8,920.76 | 22.0722 | 2024-10-11T02:53:00+00:00 | 29.5368 |
| 776 | 2025-04-11T01:00:00+00:00 | 915,175.73 | 2025-06-06T15:17:00+00:00 | 367,509.65 | 59.8427 | 547,666.08 | 56.5951 | 2025-08-24T19:38:00+00:00 | 135.7764 |
| 943 | 2025-10-22T21:29:00+00:00 | 2,088,471.56 | 2025-11-28T14:28:00+00:00 | 937,712.13 | 55.1006 | 1,150,759.44 | 36.7076 | 2025-12-01T04:10:00+00:00 | 39.2785 |
| 452 | 2024-12-31T17:10:00+00:00 | 187,955.73 | 2025-01-01T09:41:00+00:00 | 108,690.13 | 42.1725 | 79,265.60 | 0.6882 | 2025-01-02T01:08:00+00:00 | 1.3319 |
| 1223 | 2026-07-06T13:39:00+00:00 | 9,361,910.10 | 2026-08-18T03:33:00+00:00 | 5,543,599.77 | 40.7856 | 3,818,310.33 | 42.5792 | UNRECOVERED | 56.4312 |
| 589 | 2025-01-21T18:38:00+00:00 | 537,132.65 | 2025-02-04T22:12:00+00:00 | 320,840.05 | 40.2680 | 216,292.60 | 14.1486 | 2025-03-09T22:09:00+00:00 | 47.1465 |
| 435 | 2024-12-29T14:06:00+00:00 | 163,474.02 | 2024-12-30T16:50:00+00:00 | 101,395.34 | 37.9746 | 62,078.68 | 1.1139 | 2024-12-30T20:03:00+00:00 | 1.2479 |
| 995 | 2026-02-08T00:43:00+00:00 | 2,784,096.13 | 2026-02-08T23:08:00+00:00 | 1,783,557.59 | 35.9376 | 1,000,538.54 | 0.9340 | 2026-02-09T10:32:00+00:00 | 1.4090 |
| 436 | 2024-12-30T20:03:00+00:00 | 163,495.34 | 2024-12-31T05:18:00+00:00 | 110,806.08 | 32.2268 | 52,689.25 | 0.3854 | 2024-12-31T13:28:00+00:00 | 0.7257 |
| 777 | 2025-08-24T19:38:00+00:00 | 930,699.84 | 2025-09-18T17:13:00+00:00 | 641,758.64 | 31.0456 | 288,941.20 | 24.8993 | 2025-09-22T05:56:00+00:00 | 28.4292 |

### Largest ten by amount
| ID | Peak UTC | Peak equity | Trough UTC | Trough equity | DD % | DD amount | Peak→trough days | Recovery UTC | Peak→recovery/end days |
|---|---|---|---|---|---|---|---|---|---|
| 1223 | 2026-07-06T13:39:00+00:00 | 9,361,910.10 | 2026-08-18T03:33:00+00:00 | 5,543,599.77 | 40.7856 | 3,818,310.33 | 42.5792 | UNRECOVERED | 56.4312 |
| 1220 | 2026-05-15T02:54:00+00:00 | 9,344,768.15 | 2026-05-17T23:42:00+00:00 | 7,654,288.54 | 18.0901 | 1,690,479.62 | 2.8667 | 2026-07-06T13:32:00+00:00 | 52.4431 |
| 1098 | 2026-03-24T07:59:00+00:00 | 6,028,023.08 | 2026-03-27T02:11:00+00:00 | 4,739,508.29 | 21.3754 | 1,288,514.79 | 2.7583 | 2026-03-27T14:29:00+00:00 | 3.2708 |
| 943 | 2025-10-22T21:29:00+00:00 | 2,088,471.56 | 2025-11-28T14:28:00+00:00 | 937,712.13 | 55.1006 | 1,150,759.44 | 36.7076 | 2025-12-01T04:10:00+00:00 | 39.2785 |
| 1052 | 2026-03-05T10:56:00+00:00 | 4,627,231.21 | 2026-03-06T02:26:00+00:00 | 3,529,023.81 | 23.7336 | 1,098,207.40 | 0.6458 | 2026-03-06T14:10:00+00:00 | 1.1347 |
| 1076 | 2026-03-11T12:09:00+00:00 | 5,157,683.93 | 2026-03-11T17:31:00+00:00 | 4,143,906.60 | 19.6557 | 1,013,777.32 | 0.2236 | 2026-03-16T04:55:00+00:00 | 4.6986 |
| 995 | 2026-02-08T00:43:00+00:00 | 2,784,096.13 | 2026-02-08T23:08:00+00:00 | 1,783,557.59 | 35.9376 | 1,000,538.54 | 0.9340 | 2026-02-09T10:32:00+00:00 | 1.4090 |
| 1128 | 2026-04-08T13:18:00+00:00 | 7,052,434.69 | 2026-04-09T01:24:00+00:00 | 6,104,890.87 | 13.4357 | 947,543.82 | 0.5042 | 2026-04-09T22:18:00+00:00 | 1.3750 |
| 1000 | 2026-02-09T14:13:00+00:00 | 2,927,648.96 | 2026-02-09T20:09:00+00:00 | 2,107,433.28 | 28.0162 | 820,215.68 | 0.2472 | 2026-02-10T14:41:00+00:00 | 1.0194 |
| 1168 | 2026-04-21T10:55:00+00:00 | 8,137,445.59 | 2026-04-21T19:45:00+00:00 | 7,356,165.73 | 9.6010 | 781,279.86 | 0.3681 | 2026-04-22T02:31:00+00:00 | 0.6500 |

### Longest ten by clock duration
| ID | Peak UTC | Peak equity | Trough UTC | Trough equity | DD % | DD amount | Peak→trough days | Recovery UTC | Peak→recovery/end days |
|---|---|---|---|---|---|---|---|---|---|
| 776 | 2025-04-11T01:00:00+00:00 | 915,175.73 | 2025-06-06T15:17:00+00:00 | 367,509.65 | 59.8427 | 547,666.08 | 56.5951 | 2025-08-24T19:38:00+00:00 | 135.7764 |
| 1223 | 2026-07-06T13:39:00+00:00 | 9,361,910.10 | 2026-08-18T03:33:00+00:00 | 5,543,599.77 | 40.7856 | 3,818,310.33 | 42.5792 | UNRECOVERED | 56.4312 |
| 1220 | 2026-05-15T02:54:00+00:00 | 9,344,768.15 | 2026-05-17T23:42:00+00:00 | 7,654,288.54 | 18.0901 | 1,690,479.62 | 2.8667 | 2026-07-06T13:32:00+00:00 | 52.4431 |
| 589 | 2025-01-21T18:38:00+00:00 | 537,132.65 | 2025-02-04T22:12:00+00:00 | 320,840.05 | 40.2680 | 216,292.60 | 14.1486 | 2025-03-09T22:09:00+00:00 | 47.1465 |
| 943 | 2025-10-22T21:29:00+00:00 | 2,088,471.56 | 2025-11-28T14:28:00+00:00 | 937,712.13 | 55.1006 | 1,150,759.44 | 36.7076 | 2025-12-01T04:10:00+00:00 | 39.2785 |
| 957 | 2025-12-01T15:45:00+00:00 | 2,408,094.24 | 2026-01-03T07:29:00+00:00 | 2,116,519.56 | 12.1081 | 291,574.68 | 32.6556 | 2026-01-05T00:50:00+00:00 | 34.3785 |
| 37 | 2024-09-11T14:00:00+00:00 | 13,451.34 | 2024-10-03T15:44:00+00:00 | 4,530.57 | 66.3188 | 8,920.76 | 22.0722 | 2024-10-11T02:53:00+00:00 | 29.5368 |
| 777 | 2025-08-24T19:38:00+00:00 | 930,699.84 | 2025-09-18T17:13:00+00:00 | 641,758.64 | 31.0456 | 288,941.20 | 24.8993 | 2025-09-22T05:56:00+00:00 | 28.4292 |
| 991 | 2026-01-20T01:27:00+00:00 | 2,726,371.85 | 2026-01-23T17:38:00+00:00 | 2,008,309.06 | 26.3377 | 718,062.79 | 3.6743 | 2026-02-08T00:23:00+00:00 | 18.9556 |
| 275 | 2024-11-27T20:30:00+00:00 | 70,691.74 | 2024-12-11T01:59:00+00:00 | 67,458.89 | 4.5732 | 3,232.85 | 13.2285 | 2024-12-11T02:43:00+00:00 | 13.2590 |

## Time underwater and threshold stress

All-native global high-water elapsed duration, reconstructed from the complete exported excursion boundaries without a second trace pass:
| Measure | Value |
|---|---|
| basis | Union of first-underwater native observation to first native recovery intervals; hold-last-observed native HWM state between timestamps. Zero-duration callback excursions contribute zero elapsed time. Distinct from paired post-SOL sampled peak/time. |
| minutes | 1047507 |
| days | 727.4354166666666666666666667 |
| percent_interval | 99.64868721461187214611872146 |
| longest_minutes | 195517 |
| longest_days | 135.7756944444444444444444444 |
| longest_episode_id | 776 |
| longest_start | 2025-04-11T01:01:00+00:00 |
| longest_end | 2025-08-24T19:38:00+00:00 |

These duration statistics use one paired post-SOL sample per minute and its sampled global high-water mark; the all-native peak can differ slightly due to callback ordering. Threshold all-native entry counts are reported separately. Each sampled minute contributes one minute; maximum duration is sample-count duration, not a claim of intraminute exposure certainty.

| Measure | Value |
|---|---|
| minutes | 940316 |
| percent | 89.45167427701674277016742770 |
| longest_minutes | 236255 |
| longest_days | 164.0659722222222222222222222 |
| longest_start | 2025-04-11T01:01:00+00:00 |
| longest_end | 2025-09-22T02:35:00+00:00 |

| DD threshold % | All-native entries | Paired-minute entries | Minutes at/below threshold | Days | % of interval | Longest minutes | Longest days | Longest start UTC | Longest last sample UTC |
|---|---|---|---|---|---|---|---|---|---|
| 10 | 1124 | 1189 | 481857 | 334.6229 | 45.8388 | 195094 | 135.4819 | 2025-04-11T08:03:00+00:00 | 2025-08-24T19:36:00+00:00 |
| 20 | 543 | 526 | 336348 | 233.5750 | 31.9966 | 162252 | 112.6750 | 2025-04-12T03:01:00+00:00 | 2025-08-02T19:12:00+00:00 |
| 30 | 481 | 468 | 232158 | 161.2208 | 22.0850 | 94477 | 65.6090 | 2025-05-19T14:30:00+00:00 | 2025-07-24T05:06:00+00:00 |
| 40 | 331 | 336 | 85400 | 59.3056 | 8.1240 | 31344 | 21.7667 | 2025-06-03T16:01:00+00:00 | 2025-06-25T10:24:00+00:00 |
| 50 | 153 | 155 | 14667 | 10.1854 | 1.3953 | 5224 | 3.6278 | 2025-06-06T03:20:00+00:00 | 2025-06-09T18:23:00+00:00 |
| 60 | 3 | 3 | 26 | 0.0181 | 0.0025 | 21 | 0.0146 | 2024-10-03T15:27:00+00:00 | 2024-10-03T15:47:00+00:00 |

## Worst equity changes

Returns use native equity, including marked open positions, not cash-only changes. Amount and percentage minima can occur in different windows. Rolling 30 days is 43,200 minutes; calendar months are reported separately.

| Rolling minutes | Metric | Value (% or USDT) | Start UTC | Start E | End UTC | End E |
|---|---|---|---|---|---|---|
| 1 | return | -8.20464028 | 2026-02-08T23:05:00+00:00 | 2,013,217.97 | 2026-02-08T23:06:00+00:00 | 1,848,040.67 |
| 1 | change | -228,129.76080000 | 2026-03-11T14:02:00+00:00 | 4,621,990.96 | 2026-03-11T14:03:00+00:00 | 4,393,861.20 |
| 60 | return | -30.96835639 | 2024-10-03T07:37:00+00:00 | 10,570.37 | 2024-10-03T08:37:00+00:00 | 7,296.90 |
| 60 | change | -719,793.16740000 | 2026-03-11T12:40:00+00:00 | 5,004,481.66 | 2026-03-11T13:40:00+00:00 | 4,284,688.49 |
| 1440 | return | -50.11960605 | 2024-10-02T15:44:00+00:00 | 9,082.88 | 2024-10-03T15:44:00+00:00 | 4,530.57 |
| 1440 | change | -1,065,592.28716031 | 2026-07-30T15:27:00+00:00 | 7,369,801.22 | 2026-07-31T15:27:00+00:00 | 6,304,208.93 |
| 10080 | return | -55.22937496 | 2025-04-10T18:22:00+00:00 | 889,082.04 | 2025-04-17T18:22:00+00:00 | 398,047.59 |
| 10080 | change | -2,191,099.60542683 | 2026-07-24T15:27:00+00:00 | 8,495,308.54 | 2026-07-31T15:27:00+00:00 | 6,304,208.93 |
| 43200 | return | -53.72844467 | 2024-09-03T15:44:00+00:00 | 9,791.27 | 2024-10-03T15:44:00+00:00 | 4,530.57 |
| 43200 | change | -3,262,628.90898204 | 2026-07-08T08:38:00+00:00 | 9,222,742.27 | 2026-08-07T08:38:00+00:00 | 5,960,113.36 |

### Worst ten calendar day returns
| Period | Start E | End E | Change | Return % | Within-period minute DD % |
|---|---|---|---|---|---|
| 2024-10-03 | 9,900.57 | 7,055.35 | -2,845.22 | -28.7379 | 60.4751 |
| 2025-11-26 | 1,881,182.35 | 1,363,533.70 | -517,648.65 | -27.5172 | 35.0210 |
| 2024-09-17 | 10,548.07 | 8,122.36 | -2,425.71 | -22.9967 | 37.2329 |
| 2025-04-11 | 889,082.04 | 703,721.35 | -185,360.69 | -20.8485 | 27.7259 |
| 2025-02-04 | 447,906.73 | 359,327.12 | -88,579.61 | -19.7764 | 29.4505 |
| 2024-12-29 | 153,269.46 | 125,148.69 | -28,120.77 | -18.3473 | 27.4340 |
| 2025-06-06 | 482,348.54 | 395,002.74 | -87,345.80 | -18.1084 | 24.8585 |
| 2025-10-12 | 1,765,536.10 | 1,494,873.16 | -270,662.94 | -15.3304 | 20.9033 |
| 2026-03-05 | 4,370,676.67 | 3,720,029.81 | -650,646.86 | -14.8866 | 20.4751 |
| 2026-01-20 | 2,693,706.22 | 2,313,434.53 | -380,271.69 | -14.1170 | 16.7311 |

### Worst ten calendar hour returns
| Period | Start E | End E | Change | Return % | Within-period minute DD % |
|---|---|---|---|---|---|
| 2024-10-03T08 | 9,420.24 | 6,763.16 | -2,657.08 | -28.2061 | 28.5701 |
| 2024-10-03T14 | 7,456.62 | 5,829.68 | -1,626.94 | -21.8188 | 29.7503 |
| 2024-12-30T21 | 154,435.34 | 121,555.34 | -32,880.00 | -21.2905 | 21.8562 |
| 2025-11-26T17 | 1,811,568.16 | 1,468,829.91 | -342,738.25 | -18.9194 | 20.7825 |
| 2024-12-30T13 | 145,338.90 | 119,838.90 | -25,500.00 | -17.5452 | 18.9484 |
| 2024-09-17T14 | 9,634.90 | 8,188.09 | -1,446.81 | -15.0164 | 16.0399 |
| 2024-11-23T04 | 34,357.72 | 29,460.00 | -4,897.72 | -14.2551 | 19.6040 |
| 2024-11-22T03 | 33,434.77 | 28,736.54 | -4,698.22 | -14.0519 | 20.9094 |
| 2025-10-11T02 | 1,718,344.70 | 1,485,472.14 | -232,872.57 | -13.5521 | 13.7807 |
| 2025-02-04T21 | 380,192.66 | 328,892.18 | -51,300.48 | -13.4933 | 13.4933 |

### Worst ten calendar week returns
| Period | Start E | End E | Change | Return % | Within-period minute DD % |
|---|---|---|---|---|---|
| 2025-04-07 | 798,166.00 | 553,759.01 | -244,407.00 | -30.6211 | 42.2746 |
| 2025-11-24 | 1,881,182.35 | 1,384,898.15 | -496,284.20 | -26.3815 | 54.6786 |
| 2025-10-20 | 1,867,362.41 | 1,431,203.83 | -436,158.57 | -23.3569 | 34.8402 |
| 2025-04-14 | 553,759.01 | 426,740.96 | -127,018.05 | -22.9374 | 30.5232 |
| 2026-07-27 | 8,128,779.66 | 6,295,850.66 | -1,832,929.00 | -22.5486 | 24.1402 |
| 2025-06-02 | 538,479.63 | 424,252.41 | -114,227.22 | -21.2129 | 33.3360 |
| 2024-09-16 | 11,748.60 | 9,715.42 | -2,033.18 | -17.3057 | 40.8379 |
| 2026-05-11 | 9,234,281.38 | 7,889,942.54 | -1,344,338.84 | -14.5581 | 18.0901 |
| 2025-01-27 | 466,769.09 | 400,523.16 | -66,245.93 | -14.1924 | 27.6840 |
| 2026-02-02 | 2,664,602.92 | 2,347,260.27 | -317,342.65 | -11.9096 | 35.9376 |

### Worst ten calendar month returns
| Period | Start E | End E | Change | Return % | Within-period minute DD % |
|---|---|---|---|---|---|
| 2025-04 | 751,876.81 | 475,637.29 | -276,239.52 | -36.7400 | 56.5815 |
| 2026-07 | 8,986,291.51 | 6,464,812.37 | -2,521,479.14 | -28.0592 | 32.6611 |
| 2025-11 | 1,639,528.47 | 1,384,898.15 | -254,630.32 | -15.5307 | 54.6786 |
| 2026-08 | 6,464,812.37 | 6,090,649.46 | -374,162.91 | -5.7877 | 16.5559 |
| 2025-02 | 469,130.45 | 446,870.02 | -22,260.42 | -4.7450 | 32.3012 |
| 2024-09 | 10,000.00 | 9,715.42 | -284.58 | -2.8458 | 47.8657 |
| 2026-05 | 8,601,896.94 | 8,431,200.66 | -170,696.28 | -1.9844 | 18.0901 |
| 2025-06 | 523,051.51 | 551,390.87 | 28,339.36 | 5.4181 | 33.3360 |
| 2026-06 | 8,431,200.66 | 8,986,291.51 | 555,090.84 | 6.5838 | 4.7741 |
| 2025-05 | 475,637.29 | 523,051.51 | 47,414.22 | 9.9686 | 29.6059 |

## All 24 calendar months

Start/end native equity compounds exactly through all months to the final interval marked value. Monthly within-period DD is measured from the larger of period-start equity and subsequent paired-minute peaks, and differs from global DD. Positive/negative/flat day counts use UTC daily equity changes. End cash plus native marked unrealized equals end equity; no funding or realized per-asset components are invented.

| Month | Start E | End E | Return % | Min E | Max E | Within-month DD % | +days | −days | 0days | End cash | End native U |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2024-09 | 10,000.00 | 9,715.42 | -2.8458 | 6,999.91 | 13,426.67 | 47.8657 | 6 | 6 | 18 | 9,715.42 | 0.00 |
| 2024-10 | 9,715.42 | 24,159.93 | 148.6761 | 4,530.57 | 24,159.93 | 60.4751 | 12 | 6 | 13 | 24,159.93 | 0.00 |
| 2024-11 | 24,159.93 | 69,642.58 | 188.2566 | 19,885.36 | 70,691.74 | 30.7026 | 10 | 7 | 13 | 69,642.58 | 0.00 |
| 2024-12 | 69,642.58 | 118,744.23 | 70.5052 | 61,891.88 | 187,955.73 | 37.9746 | 8 | 5 | 18 | 107,534.23 | 11,210.00 |
| 2025-01 | 118,744.23 | 469,130.45 | 295.0764 | 108,690.13 | 537,132.65 | 24.0543 | 18 | 7 | 6 | 467,159.63 | 1,970.81 |
| 2025-02 | 469,130.45 | 446,870.02 | -4.7450 | 320,840.05 | 473,922.91 | 32.3012 | 10 | 9 | 9 | 446,870.02 | 0.00 |
| 2025-03 | 446,870.02 | 751,876.81 | 68.2540 | 419,255.95 | 782,345.71 | 17.8812 | 14 | 8 | 9 | 783,516.81 | -31,640.00 |
| 2025-04 | 751,876.81 | 475,637.29 | -36.7400 | 397,355.19 | 915,175.73 | 56.5815 | 8 | 13 | 9 | 475,637.29 | 0.00 |
| 2025-05 | 475,637.29 | 523,051.51 | 9.9686 | 444,465.07 | 658,890.43 | 29.6059 | 16 | 14 | 1 | 555,347.14 | -32,295.63 |
| 2025-06 | 523,051.51 | 551,390.87 | 5.4181 | 367,509.65 | 577,066.68 | 33.3360 | 16 | 11 | 3 | 521,540.37 | 29,850.51 |
| 2025-07 | 551,390.87 | 696,176.48 | 26.2583 | 521,003.47 | 698,507.63 | 9.6203 | 13 | 6 | 12 | 606,856.48 | 89,320.00 |
| 2025-08 | 696,176.48 | 842,025.81 | 20.9501 | 516,422.48 | 893,334.18 | 29.9801 | 8 | 13 | 10 | 842,025.81 | 0.00 |
| 2025-09 | 842,025.81 | 1,200,125.81 | 42.5284 | 641,758.64 | 1,241,636.20 | 26.5799 | 11 | 11 | 8 | 1,214,047.72 | -13,921.91 |
| 2025-10 | 1,200,125.81 | 1,639,528.47 | 36.6130 | 1,195,294.39 | 2,088,471.56 | 39.7494 | 14 | 11 | 6 | 1,639,528.47 | 0.00 |
| 2025-11 | 1,639,528.47 | 1,384,898.15 | -15.5307 | 937,712.13 | 2,069,026.35 | 54.6786 | 5 | 2 | 23 | 1,876,626.84 | -491,728.69 |
| 2025-12 | 1,384,898.15 | 2,236,365.46 | 61.4823 | 1,376,262.25 | 2,408,094.24 | 12.8503 | 1 | 0 | 30 | 2,236,365.46 | 0.00 |
| 2026-01 | 2,236,365.46 | 2,664,602.92 | 19.1488 | 2,008,309.06 | 2,726,371.85 | 26.3377 | 9 | 11 | 11 | 2,664,602.92 | 0.00 |
| 2026-02 | 2,664,602.92 | 4,370,676.67 | 64.0273 | 1,783,557.59 | 4,532,569.68 | 35.9376 | 6 | 1 | 21 | 4,370,676.67 | 0.00 |
| 2026-03 | 4,370,676.67 | 5,899,180.91 | 34.9718 | 3,529,023.81 | 6,056,326.47 | 23.7336 | 7 | 8 | 16 | 5,899,180.91 | 0.00 |
| 2026-04 | 5,899,180.91 | 8,601,896.94 | 45.8151 | 5,681,410.81 | 8,726,177.69 | 13.4357 | 9 | 2 | 19 | 8,465,953.23 | 135,943.72 |
| 2026-05 | 8,601,896.94 | 8,431,200.66 | -1.9844 | 7,654,288.54 | 9,344,768.15 | 18.0901 | 8 | 12 | 11 | 8,452,890.66 | -21,690.00 |
| 2026-06 | 8,431,200.66 | 8,986,291.51 | 6.5838 | 8,134,578.33 | 9,079,421.20 | 4.7741 | 2 | 2 | 26 | 8,986,291.51 | 0.00 |
| 2026-07 | 8,986,291.51 | 6,464,812.37 | -28.0592 | 6,304,208.93 | 9,361,910.10 | 32.6611 | 10 | 18 | 3 | 6,464,812.37 | 0.00 |
| 2026-08 | 6,464,812.37 | 6,090,649.46 | -5.7877 | 5,543,599.77 | 6,643,490.86 | 16.5559 | 13 | 10 | 8 | 5,990,509.00 | 100,140.46 |

### Terminal marked-to-settled reconciliation

| Measure | Value |
|---|---|
| Final interval UTC | 2026-09-01T00:00:00+00:00 |
| Final interval native marked E | 6090649.46221444 |
| Final interval cash | 5990509.00011444 |
| Final interval native U | 100140.46210000 |
| Actual settled TOTAL | 6077107.23887483 |
| Marked→settled delta | -13542.22333961 |
| August2026 settled variant return % | -5.997159807430906013460571060 |
| Raw settlement metadata | {"boundary_timestamp": "2026-09-01T00:00:00+00:00", "convention": "TERMINAL_FILLS_AT_END_EXCLUSIVE_REPORTED_SEPARATELY_EXCLUDED_FROM_INTERVAL_RETURNS", "fill_count": 1, "interval_cash_total_before_settlement": "5990509.00011444", "settled_cash_total": "6077107.23887483"} |

Native settlement bridge: actual terminal fee 9527.33973961, actual native cash increment before fee 96125.57850000, residual versus final native U -4014.88360000. Exact arithmetic equality verified: True. Cash/equity/fee arithmetic only. Residual labels the difference between final native marked U and actual boundary cash increment before terminalfee. Do not infer signedfunding or reconstruct PnL using rawOHLCprices; nativePnL mark normalization can differ from exportedOHLCprecision.

The settled variant replaces only the last monthly endpoint with actual settled TOTAL. It is shown separately, so boundary settlement costs are not hidden in a purported interval return. The old artifact marked_equity_series.monthly_returns remains UNKNOWN; these calendar returns are newly derived from durable paired native samples.

## Native exposure and concentration

Minutes and percentages refer to the full 730-day interval, including flat time. Asset long/short categories overlap with portfolio BTC-only/SOL-only/both categories; these rows must not all be summed. Net directional notionals use raw dollar directions, without a beta claim.

| State | Minutes | Days | % of interval |
|---|---|---|---|
| flat | 474550 | 329.5486 | 45.1436 |
| BTC_short | 193827 | 134.6021 | 18.4386 |
| BTC_only | 375248 | 260.5889 | 35.6971 |
| BTC_long | 249600 | 173.3333 | 23.7443 |
| SOL_long | 83709 | 58.1312 | 7.9632 |
| both | 68179 | 47.3465 | 6.4858 |
| both_opposite_direction | 68179 | 47.3465 | 6.4858 |
| SOL_only | 133223 | 92.5160 | 12.6734 |
| SOL_short | 117693 | 81.7312 | 11.1961 |

| Extreme | Value (ratio or USDT) | UTC | Native E | Cash | Native U | Actual positions |
|---|---|---|---|---|---|---|
| gross_notional | 30,607,886.10656000 | 2026-03-20T08:13:00+00:00 | 4566698.40520576 | 5137404.50760576 | -570706.10240000 | BTC SHORT 429.296 basis 69968.50000000001 mark 71297.86 |
| gross_notional_to_equity | 33.45631283 | 2024-10-03T15:44:00+00:00 | 4530.57414701 | 9651.60074701 | -5121.02660000 | BTC SHORT 0.724 basis 60887.25 mark 60209.94; SOL LONG 810.9 basis 140.09 mark 133.166 |
| net_directional_notional_to_equity | 16.81685578 | 2025-11-28T14:28:00+00:00 | 937712.12544458 | 1875928.59584458 | -938216.47040000 | BTC SHORT 169.664 basis 87414.85 mark 92944.7 |
| SOL_notional_to_equity | 23.83457502 | 2024-10-03T15:44:00+00:00 | 4530.57414701 | 9651.60074701 | -5121.02660000 | BTC SHORT 0.724 basis 60887.25 mark 60209.94; SOL LONG 810.9 basis 140.09 mark 133.166 |
| BTC_notional_to_equity | 16.81685578 | 2025-11-28T14:28:00+00:00 | 937712.12544458 | 1875928.59584458 | -938216.47040000 | BTC SHORT 169.664 basis 87414.85 mark 92944.7 |
| SOL_share_gross | 1.00000000 | 2024-10-11T00:01:00+00:00 | 11795.25145342 | 11795.25145342 | 0E-8 | SOL LONG 891.6 basis 138.97 mark 138.965 |
| BTC_share_gross | 1.00000000 | 2024-09-02T00:01:00+00:00 | 9987.23275075 | 9987.54875075 | -0.31600000 | BTC SHORT 0.395 basis 57313.0 mark 57313.78 |
| paired_SOL_share_gross | 0.72275736 | 2024-10-03T03:24:00+00:00 | 11364.76367038 | 9643.22407038 | 1721.53960000 | BTC SHORT 0.724 basis 60887.25 mark 61231.1; SOL LONG 810.9 basis 140.09 mark 142.52 |
| paired_BTC_share_gross | 0.99565115 | 2026-07-20T00:02:00+00:00 | 8089974.12865135 | 7924027.80865135 | 165946.32000000 | BTC LONG 269.880 basis 63935.8 mark 64549.83; SOL SHORT 1000.0 basis 76.33 mark 76.091 |

## Files and limits

Full excursions: risk-drawdowns.csv. All 730 daily NAV/cash/U/returns/extrema: risk-daily.csv. Monthly: risk-monthly.csv. Weekly: risk-weekly.csv. Small plot source: risk-daily-curve.csv. Exact values, detailed native minimum/maximum position context, top excursion metadata and thresholds: risk-statistics.json. Reproducible bounded-memory pass: risk-analysis.py.

No assumption of intrabar extrema ordering; no historical venue mark-tick path reconstruction. Signed funding and realized per-asset PnL remain unknown. Calendar sampled extrema and time-underwater measures are explicit, and are not substituted for the verified all-native DD metric.

## Daily-return distribution and annualized diagnostics

These use 730 UTC paired native daily returns, 365 days/year, zero risk-free rate and zero minimum acceptable return. Sharpe uses arithmetic daily mean/sample standard deviation; Sortino uses square root of mean squared negative daily returns, including zero contribution from nonnegative days. Historical quantiles use linear interpolation; lower-tail mean averages actual observations at/below the 5% quantile. These are descriptive, not a normality assumption or forecast. Settled CAGR/Calmar use actual terminal TOTAL, while daily return statistics exclude terminal settlement.

| Metric | Value |
|---|---|
| basis | UTC paired native daily equity returns, 730observations, 365days/year, zero risk-free andzero MAR. Historical distribution only, no forecast/normality claim. CAGR uses actualsettledTOTAL, daily return distribution excludes terminalsettlement. |
| count | 730 |
| mean_daily_return_percent | 1.1424881960641733 |
| median_daily_return_percent | 0.0 |
| std_daily_return_percent | 7.694604005792666 |
| annualized_volatility_percent | 147.00520311939843 |
| annualized_sharpe_zero_rf | 2.836690013106045 |
| annualized_sortino_zero_MAR | 6.307935972935313 |
| settled_CAGR_percent | 2365.1789466233135 |
| settled_Calmar_all_native_DD | 35.6637884128503 |
| historical_daily_5pct_quantile_percent | -7.729835056995834 |
| historical_daily_lower_tail_mean_percent | -12.85744686664279 |
| lower_tail_observations | 37 |
| positive_days | 234 |
| negative_days | 193 |
| flat_days | 303 |

Partial calendar years, with native interval endpoints:

| Year | First day | Last day | Days | Start equity | End equity | Return % |
|---|---|---|---|---|---|---|
| 2024 | 2024-09-01 | 2024-12-31 | 122 | 10000 | 118744.23171154 | 1087.442317115400 |
| 2025 | 2025-01-01 | 2025-12-31 | 365 | 118744.23171154 | 2236365.45841725 | 1783.346606553446420255656329 |
| 2026 | 2026-01-01 | 2026-08-31 | 243 | 2236365.45841725 | 6090649.46221444 | 172.3458922731258159367610181 |

Exact native excursion-minimum markers are provided in risk-native-dd-excursion-points.csv. These are exact trough points, not a daily all-phase drawdown envelope. Full daily sign runs, quantiles, weekday descriptors and best/worst days are in risk-return-distribution.json; apparent weekday differences have no significance test and are not an optimization recommendation.

Final interval drawdown from native peak 9361910.09938506: 34.94223510419624495806410690%; after actual terminal settlement: 35.08688745821211534316623679%. These are current end-of-run drawdowns, not maximum historical drawdown.
