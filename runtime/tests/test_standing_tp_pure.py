"""Engine-free checks for the exact opt-in registered standing-TP patch."""
from decimal import Decimal as D
from pathlib import Path
from inspect import signature
import ast,copy,json,hashlib
from coinmaster.strategy.standing_tp import standing_after_fill,marketable,StandingTPResearch
from coinmaster.strategy.market_redesign import target_lots
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy,WaveOverlayStrategyConfig
from coinmaster.research.a0_family import build_a0_kwargs,validate_native_a0
from coinmaster.research.native_baseline import run_native_diagnostic,build_native_strategy_config
from coinmaster.research.native_book import NativeBookWitness
from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP,MarkPriceUpdate
from nautilus_trader.backtest.models import LatencyModel
from nautilus_trader.backtest.modules import SimulationModule
from nautilus_trader.backtest.engine import SimulatedExchange,BacktestEngine
from nautilus_trader.model.book import OrderBook
from nautilus_trader.model.enums import BookType
from nautilus_trader.model.data import QuoteTick
from run_continuous_hedge_preflight import registered_fixture_context


def rejected(fn):
    try:fn()
    except (ValueError,AssertionError):return
    raise AssertionError('EXPECTED_REJECTION')


def proof():
    checks=[]
    def passed(name):checks.append(name)
    assert target_lots(752,set())=={0:159,1:159,2:434}
    assert standing_after_fill({0:159,1:159,2:434},0,159)=={0:0,1:159,2:434}
    assert target_lots(593,{0})=={1:160,2:433};passed('N752_PURE_ONLY_standing_not_renormalized')
    for held in range(5,8001):
        rights=target_lots(held,set())
        if rights[0]:
            after=standing_after_fill(rights,0,rights[0]);assert after[1]==rights[1] and after[2]==rights[2]
            assert sum(after.values())==held-rights[0]
    passed('7996_integer_standing_conservation_vectors')
    for qty in (-1,0,160):rejected(lambda:standing_after_fill({0:159},0,qty))
    rejected(lambda:standing_after_fill({0:159},1,1));passed('pre_fill_overfill_and_unknown_level_reject')
    assert marketable(-1,D(101),D(101),D(101)) and not marketable(-1,D(101),D(100),D(100))
    assert marketable(1,D(99),D(98),D(99)) and not marketable(1,D(99),D(100),D(100))
    rejected(lambda:marketable(-1,D(101),D(102),D(101)));passed('both_sides_actual_BBO_guard')
    kwargs={v:build_a0_kwargs(Path('.'),Path('.'),v,(),start_ms=0,end_ms=3600000)for v in ('R2_OFF','R2_C0','R2_A0')}
    assert all('research_btc_standing_tp'not in v for v in kwargs.values())
    from coinmaster.research.registered_control import native_kwargs_json_roundtrip
    # Exact outputs independently read from immutable source aaa31f8 before patch.
    old={'R2_OFF':'41041899264ed87ed66306077efe204098dd3c01d553be543a2cf6bf6a0b7b92','R2_C0':'ffde01ea59894e294f05cb832ec90b1741e28c0e4b2dd57974749fe625a7d4af','R2_A0':'55387e5febae189d19afca3fd96edc8a22fb071cc5f667f166722822eba783ad'}
    assert {v:hashlib.sha256(native_kwargs_json_roundtrip(k)[0].encode()).hexdigest()for v,k in kwargs.items()}==old
    for variant in ('R2_C0','R2_A0'):
        new=build_a0_kwargs(Path('.'),Path('.'),variant,(),start_ms=-86400000,end_ms=90600000,standing_tp=True)
        bound=signature(run_native_diagnostic).bind(**new);bound.apply_defaults();validate_native_a0(bound.arguments)
        assert new['research_paired_prefix']=='B2_F0' and new['research_btc_standing_tp']is True
        if variant=='R2_C0':control=new
        else:assert {k for k in new if new[k]!=control[k]}=={'research_a0_original_second','artifact_label'}
    rejected(lambda:build_a0_kwargs(Path('.'),Path('.'),'R2_OFF',(),standing_tp=True))
    rejected(lambda:build_a0_kwargs(Path('.'),Path('.'),'R2_A0',(),start_ms=-86400000,end_ms=90600000))
    rejected(lambda:build_a0_kwargs(Path('.'),Path('.'),'R2_A0',(),start_ms=-86400001,end_ms=90600000,standing_tp=True))
    passed('defaultOFF_exact_family_and_same_C0_A0_fix_roundtrip')
    cfg,context,_=registered_fixture_context('R2',start_ms=-86400000,end_ms=90600000)
    policy=cfg.margin_policy;policy.update_mark(MarkPriceUpdate(BTC_PERP.id,D(100),1));assert policy.margin_for(BTC_PERP.id,D(1),1)[0]>0
    rejected(lambda:policy.margin_for(BTC_PERP.id,D(1),121_000_000_002));policy.update_mark(MarkPriceUpdate(BTC_PERP.id,D(100),122_000_000_000));assert policy.margin_for(BTC_PERP.id,D(1),122_000_000_000)[0]>0
    passed('REAL_TierMarginPolicy_stale_DENY_fresh_recovery')
    context.update(signature(run_native_diagnostic).bind(**new).arguments)
    context.update(research_btc_standing_tp=True,research_native_book=NativeBookWitness())
    config=build_native_strategy_config(context);strategy=WaveOverlayStrategy(config)
    assert strategy._tier_allows_increase is not None and strategy.__class__._tier_allows_increase is WaveOverlayStrategy._tier_allows_increase
    assert config.research_btc_standing_tp and config.research_native_book is context['research_native_book']
    rejected(lambda:context['research_native_book'].bind(strategy));passed('REAL_config_provider_required_no_engine')
    latency=LatencyModel(base_latency_nanos=0,insert_latency_nanos=0,update_latency_nanos=0,cancel_latency_nanos=2_000_000_000)
    assert latency.base_latency_nanos==latency.insert_latency_nanos==latency.update_latency_nanos==0 and latency.cancel_latency_nanos==2_000_000_000
    assert signature(BacktestEngine.add_venue).parameters['use_message_queue'].default is True
    assert signature(BacktestEngine.add_venue).parameters['use_reduce_only'].default is True
    assert all(k in SimulatedExchange.__dict__ for k in ('get_book','latency_model','use_message_queue','oms_type')) and 'exchange'in SimulationModule.__dict__
    book=OrderBook(BTC_PERP.id,BookType.L1_MBP);q=QuoteTick(BTC_PERP.id,BTC_PERP.make_price(D(100)),BTC_PERP.make_price(D(100)),BTC_PERP.make_qty(D(1)),BTC_PERP.make_qty(D(1)),1,1);book.update_quote_tick(q)
    assert book.best_bid_price()==q.bid_price and book.best_ask_price()==q.ask_price and book.ts_last==q.ts_event
    witness=NativeBookWitness();witness.pre_process(q);assert witness.current[BTC_PERP.id]is q
    witness.process(1);witness.log_diagnostics(None);witness.reset();assert not witness.current and not witness.epochs
    passed('REAL_public_native_book_latency_default_RO_and_all_module_hooks')
    src=Path(__file__).resolve().parents[1]/'coinmaster'
    # Product import closure must not import any test helper.
    for path in (src/'strategy/standing_tp.py',src/'research/native_book.py'):
        tree=ast.parse(path.read_text());assert not any(isinstance(n,ast.ImportFrom) and n.module and (any(c.startswith('test_') for c in n.module.split('.')) or n.module.startswith('run_'))for n in ast.walk(tree))
        assert not any(isinstance(n,ast.Call)and isinstance(n.func,ast.Name)and n.func.id=='BacktestEngine'for n in ast.walk(tree))
    passed('product_dependency_closure_no_test_or_engine_constructor')
    from standing_tp_event_replay import replay_proof
    event_replay=replay_proof();passed('REAL_Cache_Order_event_product_method_replay_not_matching')
    return dict(event_replay=event_replay,status='ENGINE_FREE_PASS',checks=checks,check_groups=len(checks),engine_constructors=0,native_fills=0,limits='Pure/API proof only; physical4 essential native assertions remain mandatory.')

if __name__=='__main__':print(json.dumps(proof(),indent=2))
