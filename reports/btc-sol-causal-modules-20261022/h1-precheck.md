# H1: bounded saved-price precheck

Analysis only; native runs0; alternative TOTAL/DD/PnL not computed.

{
  "intervals": 105,
  "touch_order": {
    "MINUS_FIRST": 15,
    "PLUS_ONLY": 16,
    "MINUS_ONLY": 37,
    "NEITHER": 19,
    "PLUS_FIRST": 18
  },
  "conditional_add_reference": 49,
  "half_only_due_no_valid_add": 56,
  "ordinary_fill_censors_before_deadline": 24,
  "conditional_add_delay_minutes": {
    "n": 49,
    "median": 37.0,
    "p75": 68.0,
    "p90": 166.20000000000005,
    "max": 232.0,
    "min": 3.0
  },
  "price_cost_vs_passive_target_percent_second_half": {
    "n": 49,
    "median": 0.5129637422485673,
    "p75": 0.5847327910434655,
    "p90": 0.6675232119648696,
    "max": 1.460220859515823,
    "min": 0.38482840902477405
  },
  "price_cost_vs_original_second_fill_percent": {
    "n": 49,
    "median": 0.4593494524808959,
    "p75": 0.5133632731676098,
    "p90": 0.6492312119275117,
    "max": 1.460288246095784,
    "min": -1.3092792805296178
  },
  "fee_premium_taker_minus_maker_second_notional_fraction": 0.00035,
  "winner": {
    "intervals": 57,
    "conditional_add": 30,
    "touch_order": {
      "MINUS_FIRST": 10,
      "PLUS_ONLY": 10,
      "PLUS_FIRST": 10,
      "MINUS_ONLY": 12,
      "NEITHER": 15
    }
  },
  "loser": {
    "intervals": 48,
    "conditional_add": 19,
    "touch_order": {
      "MINUS_ONLY": 25,
      "NEITHER": 4,
      "PLUS_ONLY": 6,
      "MINUS_FIRST": 5,
      "PLUS_FIRST": 8
    }
  },
  "original_deadline": {
    "intervals": 17,
    "winners": 12,
    "winning_conditional_add": 9
  }
}

Exact parentdeadline, expiry equalityexcluded; close triggers strictly after first-half terminal. Ordinary actual fill truncates window; intent eligibilityUNKNOWN. All reference prices are next1mclose, not guaranteed fills. Original winner labels are diagnostic ex funding. BTC97–103 and all winning deadline cases are retained individually in JSON/CSV. Half-only control is selection only, not alternative equity.


Targets five of seven losingBTC97–103 by notadding, yet19/48losersstilladd and27/57originalwinnerslose secondhalf. Winningdeadline9/12retainconditionaladd;BTC48/69/96counterexamples. Costvsoldpassive median.51296%ofsecondhalfreferenceP0 plusfeeratepremium. No economicpass established; nativecapital/TP/SOLrights unknown afterchange.

nice19 requested but macOS denied priority change. Single scan20.0s; peakRSS160.7MiB; SHA verified. No additional price scan.
