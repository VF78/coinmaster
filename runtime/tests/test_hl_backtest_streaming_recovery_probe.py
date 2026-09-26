"""Disposable comparison: native BacktestEngine streaming can rebuild an open HL TP.

This exercises one native SimulatedExchange with ordered, fsynced public inputs.
It is not a production feed journal, strategy recovery, or deploy gate.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from decimal import Decimal

from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.currencies import USDC
from nautilus_trader.model.data import BarSpecification, BarType, QuoteTick, TradeTick
from nautilus_trader.model.enums import AccountType, AggressorSide, AggregationSource, BarAggregation, OmsType, PriceType
from nautilus_trader.model.identifiers import ClientId, InstrumentId, TradeId
from nautilus_trader.model.objects import Money, Price, Quantity

from coinmaster.ops.hl_sandbox_money import HyperliquidUsdcFeeModel, model_fx_pair_and_quote
from coinmaster.ops.hyperliquid_testnet import BTC_PERP, SOL_PERP, SANDBOX_LEVERAGES
from coinmaster.strategy.wave_overlay import WaveOverlayStrategyConfig
from coinmaster.venues.marks import venue_mark_data_type
from test_hl_sandbox_open_replay import HL_BTC, HL_SOL, VENUE, StableOrderProbe, quote, snapshot


def _open_journal(path):
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.execute("CREATE TABLE inputs (seq INTEGER PRIMARY KEY, payload TEXT NOT NULL, previous TEXT NOT NULL, digest TEXT NOT NULL)")
    db.commit()
    return db


def _append(db, event):
    seq, previous = db.execute("SELECT seq,digest FROM inputs ORDER BY seq DESC LIMIT 1").fetchone() or (0, "0" * 64)
    payload = json.dumps(type(event).to_dict(event), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256((previous + payload).encode()).hexdigest()
    db.execute("INSERT INTO inputs VALUES (?,?,?,?)", (seq + 1, payload, previous, digest))
    db.commit()


def _read(db):
    previous = "0" * 64
    events = []
    for expected, (seq, payload, linked, digest) in enumerate(db.execute("SELECT seq,payload,previous,digest FROM inputs ORDER BY seq"), start=1):
        if seq != expected or linked != previous or hashlib.sha256((linked + payload).encode()).hexdigest() != digest:
            raise ValueError("INPUT_CHAIN_INVALID")
        row = json.loads(payload)
        event_type = row.get("type")
        if event_type == "QuoteTick":
            event = QuoteTick.from_dict(row)
        elif event_type == "TradeTick":
            event = TradeTick.from_dict(row)
        else:
            raise ValueError("INPUT_TYPE_UNSUPPORTED")
        events.append(event)
        previous = digest
    return events


def _new_engine():
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(
        venue=VENUE, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN,
        starting_balances=[Money(10000, USDC)], base_currency=USDC,
        leverages=dict(SANDBOX_LEVERAGES), fee_model=HyperliquidUsdcFeeModel(),
        use_reduce_only=True, use_message_queue=False,
    )
    engine.add_instrument(HL_BTC)
    engine.add_instrument(HL_SOL)
    pair, _ = model_fx_pair_and_quote()
    engine.add_instrument(pair)
    spec = BarSpecification(1, BarAggregation.DAY, PriceType.LAST)
    strategy = StableOrderProbe(WaveOverlayStrategyConfig(
        btc_id=BTC_PERP, sol_id=SOL_PERP,
        btc_bar_type=BarType(InstrumentId.from_str("BTCUSDT-LINEAR.BYBIT"), spec, AggregationSource.EXTERNAL),
        sol_bar_type=BarType(InstrumentId.from_str("SOLUSDT-LINEAR.BYBIT"), spec, AggregationSource.EXTERNAL),
        btc_mark_data_type=venue_mark_data_type(BTC_PERP),
        sol_mark_data_type=venue_mark_data_type(SOL_PERP),
        mark_client_id=ClientId("HYPERLIQUID-MAINNET-DATA"),
        active_seed=Decimal("10000"),
    ))
    engine.add_strategy(strategy)
    return engine, strategy


def _advance(engine, event):
    engine.add_data([event], sort=True)
    engine.run(streaming=True)
    engine.clear_data()


def test_streaming_native_open_tp_rebuild_from_committed_inputs(tmp_path):
    db = _open_journal(tmp_path / "inputs.sqlite")
    live, live_strategy = _new_engine()
    restored = None
    try:
        _, fx = model_fx_pair_and_quote()
        prefix = (
            fx,
            quote(1, "59999.0", "60000.0"),
            quote(2, "60001.0", "60002.0"),
            quote(3, "60009.0", "60011.0"),
            TradeTick(BTC_PERP, Price.from_str("60010.0"), Quantity.from_str("0.00500"),
                      AggressorSide.BUYER, TradeId("PARTIAL-TRADE-1"), 4, 4),
        )
        for event in prefix:
            _append(db, event)
            _advance(live, event)
        boundary = snapshot(live, live_strategy)
        assert boundary["positions"] == [(str(BTC_PERP), "0.02500", True)]
        assert boundary["cash"] == ("9999.1949925", "9998.7249925", "0.47")
        assert any(order[0] == "CM-REPLAY-TP" and order[1:5] == ("PARTIALLY_FILLED", "0.03000", "0.00500", "0.02500") for order in boundary["orders"])

        restored, restored_strategy = _new_engine()
        for event in _read(db):
            _advance(restored, event)
        assert snapshot(restored, restored_strategy) == boundary

        future = (
            quote(5, "60009.0", "60011.0"),
            TradeTick(BTC_PERP, Price.from_str("60010.0"), Quantity.from_str("0.02500"),
                      AggressorSide.BUYER, TradeId("REMAINDER-TRADE-2"), 6, 6),
        )
        for event in future:
            _append(db, event)
            _advance(live, event)
            _advance(restored, _read(db)[-1])
        final = snapshot(live, live_strategy)
        assert snapshot(restored, restored_strategy) == final
        assert final["next_decisions"] == ["HOLD_WORKING_PARTIAL_TP"]
        assert final["positions"] == []
        assert final["cash"] == ("9999.219955", "9999.219955", "0")
        assert len(final["fills"]) == 3

        db.execute("UPDATE inputs SET payload=replace(payload,'60010','60011') WHERE seq=5")
        db.commit()
        try:
            _read(db)
        except ValueError as error:
            assert str(error) == "INPUT_CHAIN_INVALID"
        else:
            raise AssertionError("CORRUPT_INPUT_ACCEPTED")
    finally:
        for engine in (live, restored):
            if engine is not None:
                engine.end()
                engine.dispose()
        db.close()
