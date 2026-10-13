# Directed native confirmation routing diagnosis

Initial H1 run on7360fd0 is invalid for comparison of the intended hypothesis: reported311BTC/0SOLfills,514arms,zero stageorders/rejections. No score/winner interpretation.

Pinned Nautilus1.231 backtest engine processes and settles all same-timestamp input events, including executablequotes, before calling aggregated-bar close timers. `_on_confirmation_bar` therefore receives closedbar t after quote t; H1 equality `confirm[0]==quote_ns` cannot consume the nextquote t+60s. See engine.pyx1684–1736. This is independent source evidence, not a new trace scan or engine.

Initial focused native tests inserted tokens before quotes; the bare aggregate121min fixture checked completeOHLC but missed full event ordering. Required correction proof must combine actualbaseline sourcebars/marks/signals/quotes order, real native stage1 fill, actual BTC TP afterfirstSOLfill and real native stage2 fill.

Root bounds one H1 replacement after causal firstfreshquote-afteractualbarreceipt age<=60s correction, with unchanged2.5%/50%+sameqty/stages/exits/nativeadmission. No optimizer or combined candidate.

Frozen B1 has the same equality and aggregationpath; root currently keepsit unchanged while engine completes. Its actual entry/fill evidence must be checked; unchangedbranchhash alone doesnotprove validity.

2026-10-14 ROOT UPDATE: BOTH initial H1 and B1 runs are invalid for the intended comparison. Shared samequote equality cause confirmed; root stopped only invalid B1 research and preserved initial diagnostic artifacts. One shared causal receipt correction, two corrected individual native24m comparisons, no new trading hypothesis or optimizer. Independent exact-SHA review must prove real integrated H1 stage1/actual TP/stage2, natural B1 native entry and negative freshness/order cases. Original GO superseded for both routing paths.
