"""Bounded M1 native lifecycle window. No archived fills or prefix replay.

Fresh seed/cold episode at window start is deliberate: this checks mechanics
on the named market windows, not archive cycle identity or economic attribution.
Root must ledger each invocation before launching it.
"""
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
import argparse
import json

WINDOWS={
    "31":("2025-04-11","2025-04-14"),
    "48":("2025-10-11","2025-10-17"),
    "65":("2026-04-02","2026-04-04"),
    "81":("2026-08-11","2026-08-19"),
}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--episode",choices=tuple(WINDOWS),required=True)
    parser.add_argument("--variant",choices=("R2","R3"),default="R2")
    parser.add_argument("--expected-e4-config",type=Path,required=True)
    parser.add_argument("--data-root",type=Path,required=True)
    parser.add_argument("--artifact-dir",type=Path,required=True)
    args=parser.parse_args()
    if args.artifact_dir.exists():
        raise ValueError("SHORT_CHECK_ARTIFACT_DIR_MUST_BE_NEW")
    from coinmaster.domain.wave_overlay import Candidate
    from coinmaster.research.native_baseline import run_native_diagnostic,ExecutionPolicy,FixedBaseFeePolicy,save_diagnostic_report
    from coinmaster.research.native_audit import audit_json_default
    c=json.loads(args.expected_e4_config.read_text())
    if c["candidate"]["ema_period"]!=34 or c["candidate"]["beta_days"]!=270 or c["research_btc_split_discount"]!="0.0025":
        raise ValueError("EXPECTED_EXACT_E4_CONFIG_REQUIRED")
    start,end=WINDOWS[args.episode]
    ms=lambda day:int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp()*1000)
    if args.episode=="81":
        # Explicit bounded admission fixture: all input D1 bars remain closed.
        # Delay the first causal decision to 20:00, then native q0/q1/fills.
        # Never seed archived orders, fills, equity, d3 or execution outcomes.
        import coinmaster.strategy.wave_overlay as strategy_module
        original_strategy=strategy_module.WaveOverlayStrategy
        late_ns=ms(start)*1_000_000+20*3_600_000_000_000
        midnight_ns=(ms(start)+86_400_000)*1_000_000
        class LateBoundary81(original_strategy):
            _bounded_late_started=False
            _bounded_midnight_recorded=False
            def _advance_current_day(self):
                if self.clock.timestamp_ns()<late_ns:
                    return
                return super()._advance_current_day()
            def on_quote_tick(self,tick):
                if tick.instrument_id==self.config.btc_id and tick.ts_event>=late_ns and not self._bounded_late_started:
                    self._bounded_late_started=True
                    # The regular wrapper activates D1 decisions only after
                    # the first in-window D1 close. This fixture deliberately
                    # exercises a late entry from the already closed seed.
                    if any(int(b.close_time.timestamp()*1_000_000_000)>tick.ts_event for b in self._bars):
                        raise ValueError("SHORT81_FUTURE_SEED_BAR")
                    equity=self._active_marked(self._latest_marks[self.config.btc_id],self._latest_marks[self.config.sol_id])
                    feature=self._current_signals[-1]
                    intents=self._domain.decide(self._bars,self._current_signals,len(self._bars)-1,equity,
                        btc_notional_multiplier=self._research_btc_entry_multiplier())
                    entries=[i for i in intents if i.action=="BTC_ENTRY"]
                    if len(entries)!=1:
                        raise ValueError("SHORT81_CLOSED_SEED_NO_VALID_CAUSAL_ENTRY")
                    for entry in entries:
                        self._queued_intents.append((entry,feature.sigma,len(self._bars)-1))
                        self._queued_intent_ready_ns[entry.id]=tick.ts_event+1
                    self._md_log("BOUNDED81_CAUSAL_SEED_ENTRY",tick.ts_event,
                        feature_close_ns=str(int(self._bars[-1].close_time.timestamp()*1_000_000_000)),
                        native_equity=str(equity),side=feature.side,
                        qualification="FRESH_NATIVE_EQUITY_CLOSED_FEATURE_DOMAIN_INTENT_NO_ARCHIVED_FILLS")
                if tick.instrument_id==self.config.btc_id and tick.ts_event>=midnight_ns and not self._bounded_midnight_recorded:
                    self._bounded_midnight_recorded=True
                    parent=self._split_parent
                    owned=[o for o in self.cache.orders_open() if o.instrument_id==self.config.btc_id and not o.is_reduce_only and o.order_type.name=="LIMIT"]
                    if parent and late_ns<=parent["start_ns"]<midnight_ns and owned and not parent["fallback"]:
                        self._md_log("BOUNDED81_MIDNIGHT_PENDING_SECOND",tick.ts_event,
                            actual_inventory=next((p.quantity.as_decimal() for p in self.cache.positions_open() if p.instrument_id==self.config.btc_id),Decimal(0)),
                            second_limit=str(owned[0].price),parent_start_ns=str(parent["start_ns"]),
                            qualification="EXPLICIT_LATE_CAUSAL_DECISION_FIXTURE_NATIVE_FILL")
                return super().on_quote_tick(tick)
        strategy_module.WaveOverlayStrategy=LateBoundary81
    result=run_native_diagnostic(args.data_root,include_funding=True,
        candidate=Candidate(**c["candidate"]),execution_policy=ExecutionPolicy(**c["execution_policy"]),
        fixed_base_fee_policy=FixedBaseFeePolicy(**c["fixed_base_fee_policy"]),
        trading_start_ms=ms(start),trading_end_ms=ms(end),
        initial_active_seed=Decimal("10000"),artifact_dir=args.artifact_dir,
        artifact_label="bounded-"+args.episode+"-"+args.variant,
        research_v0_execution_repairs=True,research_v0_zero_tp_netting=False,
        research_v0_deferred_selective_zero_tp=True,research_v0_selective_lifecycle_repairs=True,
        observe_minute_risk=True,research_btc_direction_sizing=True,research_btc_split50=True,
        research_btc_split_planref_v1=True,research_btc_split_tp_ioc=True,
        research_btc_split_discount="0.005",research_btc_real_u=True,
        research_btc_q_mode="LEGACY_Q_CONTROL" if args.variant=="R2" else "CLEAN_Q",
        research_sol_off=True,research_wait_4h=True,research_regime_reentry_band="0.5")
    result=json.loads(json.dumps(result,default=audit_json_default))
    result["short_check_qualification"]={
        "archive_window":args.episode,"window_start":start,"window_end_exclusive":end,
        "state":"COLD_START_NATIVE_LIFECYCLE_ONLY_NOT_ARCHIVED_EQUITY_OR_ENTRY_CALENDAR",
        "prewarm":"CLOSED_DAILY_FEATURES_ONLY_NO_EXECUTABLE_PREFIX",
        "matching":"GENUINE_EXISTING_NATIVE_M1_CLOSE_QUOTES",
        "not_economic_acceptance":True}
    events=result["market_redesign_audit"]["events"]
    plans=[r for r in events if r["event"]=="PLAN"]
    accepted=[r for r in events if r["event"]=="TARGET_ACCEPTED"]
    if args.episode=="81" and not any(r["event"]=="BOUNDED81_MIDNIGHT_PENDING_SECOND" for r in events):
        raise ValueError("SHORT81_DID_NOT_EXERCISE_NATIVE_LATE_ENTRY_PENDING_SECOND_ACROSS_MIDNIGHT")
    if not plans or any(Decimal(r["raw_causal_d3"])<=0 for r in plans) or len(accepted)<3:
        raise ValueError("SHORT_CHECK_DID_NOT_EXERCISE_VALID_ENTRY_AND_THREE_NATIVE_TARGET_ACCEPTANCES")
    if result["terminal_open_positions"] or result["terminal_lifecycle"]["status"]!="FLAT" or result["liquidation_count"]:
        raise ValueError("SHORT_CHECK_NOT_FLAT_OR_LIQUIDATED")
    if any(r["instrument"].startswith("SOL") for r in result["fill_audit"]):
        raise ValueError("SHORT_CHECK_SOL_FILL")
    path=save_diagnostic_report(args.data_root,result,"bounded-"+args.episode+"-"+args.variant,args.artifact_dir)
    print(json.dumps({"status":"BOUNDED_NATIVE_LIFECYCLE_COMPLETED","result":str(path),
        "plans":len(plans),"accepted_native_targets":len(accepted),
        "missing_three_tp_ns":result["market_redesign_audit"]["missing_three_tp_ns"],
        "qualification":result["short_check_qualification"]}))


if __name__=="__main__":
    main()
