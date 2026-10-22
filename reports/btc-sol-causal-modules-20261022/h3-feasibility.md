# H3: actual-positive-TP2 feasibility

Analysis only; native0; no alternative portfolio PnL.

{
  "actual_positive_TP2_activations": 28,
  "trades": 28,
  "triggers": 10,
  "strict_next_close_before_original_exit": 10,
  "activated_after_first_historical_DD50": 27,
  "activation_to_trigger_hours": {
    "n": 10,
    "median": 22.80833333333333,
    "p75": 54.93333333333333,
    "p90": 97.35166666666666,
    "max": 146.56666666666666,
    "min": 8.716666666666667
  },
  "winner": {
    "activations": 17,
    "triggers": 2
  },
  "loser": {
    "activations": 11,
    "triggers": 8
  }
}

actual positive-price-vs-P0 TP2 fills only; full UTC4h bars opened at/after activation; max CLOSE signedreturn vsP0; 3percentagepoint giveback checked only atclosed4h close; next1mclose conditionalreference

Actual remaining quantity is read from saved native fills at trigger; half is theoretical request, not candidate fill. Closed4h close maxima exclude preactivation bars. Next1mclose conditional prices do not guarantee execution. Current DD at action isUNKNOWN; comparison to first historical DD50 only establishes chronology, not contemporaneous DD. Generic BTC_REDUCE is not imputed as positive TP2.


Feasibility only.10triggers8originallosing/2winning(BTC22/29).BTC35triggers19.9h afteractivation; its firsteligible4hpeak already−2.0813%vsP0, trigger−5.3542%, hence not protectionofalwayspositivebook. BTC43no3ppgiveback beforeexit;BTC67noactualTP2 andcannotactivate. NoevidenceofglobalDD<=50 or retainedTOTAL. CurrentDD/actualordereligibility/fillUNKNOWN.

nice19 requested but macOS denied priority change. Single scan20.0s; peakRSS160.7MiB; SHA verified. No additional price scan.
