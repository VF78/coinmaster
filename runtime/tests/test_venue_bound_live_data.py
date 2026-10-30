"""Real native bars/data callbacks; no TradingNode or BacktestEngine."""
import asyncio
import ast
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from nautilus_trader.model.data import Bar
from nautilus_trader.model.identifiers import InstrumentId, TraderId
from nautilus_trader.model.objects import Price, Quantity
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.component import TestClock, MessageBus

from coinmaster.ops.venue_data import binding_for_execution, refresh_hl_warmup, load_hl_warmup, DAY_MS, _paired_rows
from coinmaster.ops.hl_closed_bars import normalize_hl_bar, ClosedHyperliquidDataClientFactory
from coinmaster.ops.hyperliquid_testnet import hyperliquid_testnet_node_config, load_stageg_warmup_bundle
from coinmaster.ops.hl_live_worker import ClosedTradeClock
from coinmaster.ops.stage_g_config import load_testnet_instance_config
from coinmaster.domain.wave_overlay import Candidate
from coinmaster.strategy.live_recovery import recovery_policy_hash

ROOT = Path(__file__).parents[1]
HL = tuple(InstrumentId.from_str(s) for s in ("BTC-USD-PERP.HYPERLIQUID", "SOL-USD-PERP.HYPERLIQUID"))
BYBIT = tuple(InstrumentId.from_str(s) for s in ("BTCUSDT-LINEAR.BYBIT", "SOLUSDT-LINEAR.BYBIT"))
BINDING = binding_for_execution(HL)
MINUTE = 60_000_000_000
DAY = 86_400_000_000_000
NOW_MS = 1000 * DAY_MS + 10_000


def native_bar(index=0, *, minute=True, open_ns=DAY, init_ns=None):
    span = MINUTE if minute else DAY
    return Bar(BINDING.bar_type(index, minute=minute), Price.from_str("100.00"), Price.from_str("110.00"),
        Price.from_str("90.00"), Price.from_str("105.00"), Quantity.from_str("1.000"),
        open_ns, init_ns if init_ns is not None else open_ns + span + 7)


@pytest.mark.parametrize("ids,error", [(HL[:1],"INCONSISTENT"), ((HL[0], BYBIT[1]),"INCONSISTENT"),
    ((InstrumentId.from_str("BTC.X"), InstrumentId.from_str("SOL.X")),"UNSUPPORTED"), ((HL[1],HL[0]),"UNSUPPORTED")])
def test_binding_rejects_inconsistent_or_unsupported_execution(ids,error):
    with pytest.raises(ValueError, match=error): binding_for_execution(ids)


def test_source_binding_has_no_independent_signal_override():
    bybit = binding_for_execution(BYBIT)
    assert bybit.signal_ids == BYBIT and bybit.timestamp_basis == "CLOSE"
    assert BINDING.signal_ids == HL and BINDING.timestamp_basis == "OPEN"
    assert bybit.identity != BINDING.identity
    live = hyperliquid_testnet_node_config(trader_id="TEST-001", execution_mode="live")
    sandbox = hyperliquid_testnet_node_config(trader_id="TEST-001", execution_mode="sandbox", research_bybit_reference=True)
    assert "BYBIT-PUBLIC-SIGNAL" not in hyperliquid_testnet_node_config(trader_id="TEST-001").data_clients
    with pytest.raises(ValueError, match="REFUSES_REAL"):
        hyperliquid_testnet_node_config(trader_id="TEST-001", execution_mode="live", research_bybit_reference=True)
    assert set(live.data_clients) == {"HYPERLIQUID-MAINNET-DATA"}
    assert "BYBIT-PUBLIC-SIGNAL" in sandbox.data_clients
    instance = load_testnet_instance_config(ROOT / "configs/hl-stageg-live.instance.json")
    assert "/data/hyperliquid/current/" in str(instance.signal_warmup_manifest)


@pytest.mark.parametrize("minute",[True,False])
def test_native_open_stamps_close_once_and_preserve_receipt_prices(minute):
    bar=native_bar(minute=minute); span=MINUTE if minute else DAY
    normalized=normalize_hl_bar(bar,received_ns=bar.ts_init+4)
    assert normalized.ts_event == bar.ts_event+span and normalized.ts_init == bar.ts_init
    assert normalized.open == bar.open and normalized.volume == bar.volume and normalized.bar_type == bar.bar_type
    http=normalize_hl_bar(native_bar(minute=minute,init_ns=DAY),received_ns=DAY+span+100,historical=True)
    assert http.ts_event == DAY+span and http.ts_init == DAY+span+100
    with pytest.raises(ValueError,match="UNCLOSED"):
        normalize_hl_bar(normalized,received_ns=normalized.ts_init+4)


@pytest.mark.parametrize("minute",[True,False])
def test_forming_future_or_bad_receipt_cannot_enter_clock(minute):
    bar=native_bar(minute=minute)
    for received in (bar.ts_event,bar.ts_init-1):
        with pytest.raises(ValueError,match="UNCLOSED"):
            normalize_hl_bar(bar,received_ns=received)
    with pytest.raises(ValueError,match="UNCLOSED"):
        normalize_hl_bar(native_bar(open_ns=DAY+1,minute=minute),received_ns=3*DAY)


def test_actual_stock_data_callbacks_emit_close_stamps_with_http_receipt():
    loop=asyncio.new_event_loop();clock=TestClock();clock.set_time(3*DAY)
    bus=MessageBus(trader_id=TraderId("TEST-001"),clock=clock); cache=Cache()
    config=hyperliquid_testnet_node_config(trader_id="TEST-001",execution_mode="live")
    client=ClosedHyperliquidDataClientFactory.create(loop,"HL-DATA",config.data_clients["HYPERLIQUID-MAINNET-DATA"],bus,cache,clock)
    data=[];responses=[]
    bus.register(endpoint="DataEngine.process",handler=data.append)
    bus.register(endpoint="DataEngine.response",handler=responses.append)
    ws=native_bar();client._handle_data(ws)
    assert data[0].ts_event == DAY+MINUTE and data[0].ts_init == ws.ts_init
    # Stock HTTP callback path; open-stamped ts_init must become actual NOW.
    client._handle_bars(ws.bar_type,[native_bar(init_ns=DAY)],UUID4(),None,None,{})
    assert responses[0].data[0].ts_event == DAY+MINUTE and responses[0].data[0].ts_init == 3*DAY
    loop.close()


def history(coin, *, count=1000, leading=5):
    rows=[]
    for i in range(count):
        rows.append(dict(t=i*DAY_MS,T=(i+1)*DAY_MS-1,s=coin,i="1d",o="100",h="110",l="90",c="105",
            v="0" if i<leading or i==500 else "1",n=0 if i<leading or i==500 else 1))
    return json.dumps(rows).encode()


def fetch(coin,interval,start,end):
    assert interval=="1d" and start==0 and end==1000*DAY_MS-1
    return history(coin,leading=5 if coin=="BTC" else 8),NOW_MS


def test_source_specific_atomic_manifest_prefix_only_and_raw_hash(tmp_path):
    root=tmp_path/"hyperliquid"
    path=refresh_hl_warmup(root,binding=BINDING,now_ms=NOW_MS,fetch=fetch)
    rows,state=load_hl_warmup(path,binding=BINDING,now_ms=NOW_MS)
    assert state=="READY" and len(rows["BTCUSDT"])==992
    assert rows["BTCUSDT"][0]["open_time_ms"]==8*DAY_MS
    assert any(r["open_time_ms"]==500*DAY_MS and r["trades"]==0 for r in rows["BTCUSDT"])
    assert load_hl_warmup(path,binding=binding_for_execution(BYBIT),now_ms=NOW_MS)[1]!="READY"
    assert load_hl_warmup(path,binding=BINDING,now_ms=NOW_MS+DAY_MS)[1]!="READY"
    bundle,state=load_stageg_warmup_bundle(path,now_ns=NOW_MS*1_000_000,data_binding=BINDING)
    assert state=="READY" and bundle.rows==992
    # No fetch or other venue fallback for a valid same-day immutable artifact.
    assert refresh_hl_warmup(root,binding=BINDING,now_ms=NOW_MS,fetch=lambda *a:pytest.fail("unneeded fetch"))==path
    raw=path.parent/"BTC-1d.json";raw.write_bytes(b"[]")
    assert load_hl_warmup(path,binding=BINDING,now_ms=NOW_MS)[1]!="READY"


@pytest.mark.parametrize("defect",["empty","missing","duplicate","reordered","short","future_receipt"])
def test_bad_history_denies_and_does_not_promote(tmp_path,defect):
    root=tmp_path/"hyperliquid"
    def broken(coin,*args):
        rows=json.loads(history(coin))
        if defect=="empty":rows=[]
        elif defect=="missing":rows.pop(500)
        elif defect=="duplicate":rows.insert(500,rows[500])
        elif defect=="reordered":rows[500],rows[501]=rows[501],rows[500]
        elif defect=="short":rows=rows[-700:]
        return json.dumps(rows).encode(), NOW_MS+DAY_MS if defect=="future_receipt" else NOW_MS
    with pytest.raises(ValueError):refresh_hl_warmup(root,binding=BINDING,now_ms=NOW_MS,fetch=broken)
    assert not (root/"current").exists()


def test_network_failure_preserves_predecessor_without_fallback(tmp_path):
    root=tmp_path/"hyperliquid";path=refresh_hl_warmup(root,binding=BINDING,now_ms=NOW_MS,fetch=fetch)
    old=(root/"current").readlink()
    with pytest.raises(OSError):
        refresh_hl_warmup(root,binding=BINDING,now_ms=NOW_MS+DAY_MS,fetch=lambda *a:(_ for _ in ()).throw(OSError("DENY")))
    assert (root/"current").readlink()==old
    assert load_hl_warmup(path,binding=BINDING,now_ms=NOW_MS+DAY_MS)[1]!="READY"
    with pytest.raises(ValueError,match="SOURCE_SPECIFIC"):
        refresh_hl_warmup(tmp_path/"bybit",binding=BINDING,now_ms=NOW_MS,fetch=fetch)


def test_native_paired_midnight_late_duplicate_reorder_and_missing_history():
    c=ClosedTradeClock({});end=DAY;start=end-4*60*MINUTE;received=end+100
    for index in (0,1):
        # Late/out-of-order arrival within a window is acceptable; all 240
        # genuine minutes must exist before any H4 can become available.
        for open_ns in (hour+offset for hour in range(start,end,60*MINUTE)
                for offset in reversed(range(0,60*MINUTE,MINUTE))):
            native=normalize_hl_bar(native_bar(index,open_ns=open_ns,init_ns=received),received_ns=received)
            values=tuple(getattr(native,k).as_decimal() for k in ("open","high","low","close"))
            c.minute(str(HL[index]),native.ts_event,native.ts_init,received,values)
            c.minute(str(HL[index]),native.ts_event,native.ts_init,received+1,values)
    early=c.drain(received+10,tuple(map(str,HL)))
    assert all(b["hours"]==1 for b in early) and len(early)==4
    c.daily(str(HL[0]),end,received+20)
    assert c.drain(received+30,tuple(map(str,HL)))==[]
    c.daily(str(HL[1]),end,received+40)
    bars=c.drain(received+41,tuple(map(str,HL)))
    assert sum(b["hours"]==4 for b in bars)==2 and sum(b["hours"]==1 for b in bars+early)==4
    assert all(b["available_ns"]==received+40 for b in bars if b["hours"]==4)
    assert c.drain(received+42,tuple(map(str,HL)))==[]
    missing=ClosedTradeClock({})
    for open_ns in range(start,end-MINUTE,MINUTE):
        missing.minute(str(HL[0]),open_ns+MINUTE,received,received,(Decimal(100),Decimal(110),Decimal(90),Decimal(105)))
    assert missing.drain(received+1,tuple(map(str,HL)))==[]


def policy_config(*,live,signals=HL):
    return SimpleNamespace(research_residual_recovery=True,btc_id=HL[0],sol_id=HL[1],
        btc_signal_id=signals[0],sol_signal_id=signals[1],execution_policy_version="hl-mainnet-native-owned-v1" if live else "research-only-hl-rules-proxy",
        live_account_mode="unifiedAccount")


def test_checkpoint_policy_changes_source_and_rejects_crossvenue_live_research_stays_bybit():
    candidate=Candidate()
    live=recovery_policy_hash(policy_config(live=True),candidate)
    research=recovery_policy_hash(policy_config(live=False,signals=BYBIT),candidate)
    assert live!=research
    with pytest.raises(ValueError,match="SIGNAL_EXECUTION_VENUE_MISMATCH"):
        recovery_policy_hash(policy_config(live=True,signals=BYBIT),candidate)
    # Frozen economic and Bybit ingestion source must be byte-identical to parent.
    import subprocess
    files=("coinmaster/domain/wave_overlay.py","coinmaster/strategy/wave_overlay.py",
        "coinmaster/strategy/residual_recovery.py","coinmaster/strategy/hedge_band.py","coinmaster/strategy/next_band.py",
        "coinmaster/research/bybit_data.py")
    for name in files:
        parent=subprocess.check_output(["git","show","4ca0d87993f28c20fb039840551c04e051378582:runtime/"+name],cwd=ROOT)
        assert (ROOT/name).read_bytes()==parent


def test_ordinary_sandbox_default_route_is_same_venue_and_research_is_explicit():
    from coinmaster.ops.hyperliquid_testnet import assert_native_testnet_only
    config=hyperliquid_testnet_node_config(trader_id="TEST-001")
    assert_native_testnet_only(config)
    research=hyperliquid_testnet_node_config(trader_id="TEST-001",research_bybit_reference=True)
    assert_native_testnet_only(research,research_bybit_reference=True)
    with pytest.raises(RuntimeError,match="SINGLE_NATIVE_ROUTE"):
        assert_native_testnet_only(research)
    instance=load_testnet_instance_config(ROOT/"configs/hl-stageg-testnet.instance.json")
    assert "/data/hyperliquid/current/" in str(instance.signal_warmup_manifest)
