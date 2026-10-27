"""Engine-free Method-A proof; run only with engine tripwire installed first."""
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace as NS
from dataclasses import replace
from inspect import signature
import ast, hashlib, json, subprocess
from coinmaster.strategy.method_a_tp import cumulative_entitlement, MethodATpResearch
from coinmaster.strategy.market_redesign import u_prices
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy, WaveOverlayStrategyConfig
from coinmaster.research.native_baseline import run_native_diagnostic, build_native_strategy_config
from run_continuous_hedge_preflight import registered_fixture_context, snapshot_config


def proof():
    checks = []
    prior = {0: 0, 1: 0, 2: 0}
    for n in range(0, 8001):
        grants, leaves = cumulative_entitlement(n, {}, {})
        assert sum(grants.values()) == n and grants == leaves
        assert all(grants[i] >= prior[i] for i in range(3))
        if n >= 80:
            old, _ = cumulative_entitlement(n-80, {}, {})
            assert {i: grants[i]-old[i] for i in range(3)} == {0:17,1:17,2:46}
        for consumed in ({}, {0:grants[0]}, {0:grants[0],1:grants[1]}, dict(grants)):
            retired = {i: (grants[i]-consumed.get(i,0))//2 for i in range(3)}
            _, remaining = cumulative_entitlement(n, consumed, retired)
            assert sum(remaining.values())+sum(consumed.values())+sum(retired.values()) == n
            # New actual fills grant exactly the cumulative increment, including
            # a new entitlement on a previously consumed level, never old lots.
            bigger, after = cumulative_entitlement(n+83, consumed, retired)
            assert all(after[i]-remaining[i] == bigger[i]-grants[i] >= 0 for i in range(3))
        prior = grants
    checks.append('8001_vectors_period80_monotone_partial_consumed_retired_conservation')
    for n,filled,retired in ((-1,{},{}),(True,{},{}),(1,{0:1},{}),(80,{0:18},{}),(80,{0:1},{0:17}),(80,{0:-1},{}),(80,{0:True},{})):
        try: cumulative_entitlement(n,filled,retired)
        except ValueError: pass
        else: raise AssertionError('invalid grant consumption accepted')
    checks.append('invalid_noninteger_overconsumed_failclosed')
    for side in (1,-1):
        prices = u_prices(D(100),D('.03'),side,D('.1'),D('.00055'),D('.00055'))
        assert prices == tuple(D(100)+side*D(i) for i in (1,2,3))
    checks.append('both_sides_fixed_U_geometry_basefees')
    # Every defaultOFF method exits before consulting any domain/cache/state.
    class Disabled(MethodATpResearch):
        config = NS(research_method_a_tp=False)
    h=Disabled();before=dict(h.__dict__)
    h._ma_prepare(None,None,None,None,1);h._ma_reconcile(1)
    h._ma_after_fill(None,None);h._ma_terminal(None,None)
    assert h.__dict__ == before
    assert WaveOverlayStrategyConfig.__struct_defaults__
    defaults=signature(run_native_diagnostic).parameters
    assert defaults['research_method_a_tp'].default is False
    assert defaults['research_method_a_observer'].default is False
    checks.append('defaultOFF_zero_domain_cache_order_effects')
    cfg,context,_ = registered_fixture_context('R2')
    context.update(research_method_a_tp=True,research_btc_real_u=False,research_btc_q_mode=None,
        research_sol_off=False,research_btc_split_discount='.0025',
        candidate=replace(cfg.candidate,sol_overlay_enabled=True))
    method_config=build_native_strategy_config(context)
    s=WaveOverlayStrategy(method_config)
    assert s._ma_enabled() and not s._md_enabled() and not s._tp_enabled()
    assert s._domain.research_method_a_tp and not s._domain.research_real_u
    assert s.config.research_btc_split_discount == D('.0025') and s.config.candidate.sol_overlay_enabled
    checks.append('actual_native_config_P1_oldSOL_legacy_split_noR2_owner')
    root=Path(__file__).resolve().parents[2]
    base=subprocess.check_output(['git','show','a50af5433a0bbe00aecd6fec26e8d5c0321ced80:runtime/coinmaster/strategy/split_cover.py'],cwd=root)
    assert (root/'runtime/coinmaster/strategy/split_cover.py').read_bytes() == base
    checks.append('all_original_split_functions_exact_bytes_unchanged')
    source=(root/'runtime/coinmaster/research/native_baseline.py').read_text()
    tree=ast.parse(source)
    venue=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='add_venue' and any(k.arg=='liquidity_consumption' for k in n.keywords))
    values={k.arg:k.value for k in venue.keywords}
    flags=dict(research_paired_policy=False,research_h4_ema=None,research_h1_b1=None,
        research_sol_cover=None,research_conditional_sol=False,research_sol_risk_first=None,
        research_immediate_sol=None,research_alpha_cushion=False,research_chop_pair=False)
    for tp in (False,True):
        for observer in (False,True):
            scope=dict(flags,research_method_a_tp=tp,research_method_a_observer=observer)
            assert eval(compile(ast.Expression(values['liquidity_consumption']),'venue','eval'),{},scope) is False
            assert eval(compile(ast.Expression(values['bar_execution']),'venue','eval'),{},scope) is True
    checks.append('P0_P1_observer_only_flags_venue_consumptionFalse_barTrue')
    return dict(status='ENGINE_FREE_PASS',engine_constructors=0,checks=checks,
        rounding='cumulative cuts floor17A/80, floor17A/40 minus first, remaining',
        config=snapshot_config(method_config))

if __name__=='__main__':
    result=proof();print(json.dumps({k:v for k,v in result.items() if k!='config'},sort_keys=True))
