"""One bounded native MODEL smoke, not an engine or venue test.

No Nautilus import/constructor at module load or --help. Root must freeze the
actual production provider API and allocate ONE execution before clearing GO.
Raw USD quote is a negative reference; production output must settle in USDC.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT_MODEL_GO = True
NORMALIZER_MODULE = "coinmaster.ops.hl_unified_instruments"
NORMALIZER_FUNCTION = "normalize_unified_pyo3_instrument"
NORMALIZER_SOURCE = "runtime/coinmaster/ops/hl_unified_instruments.py"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def preflight(args):
    if not ROOT_MODEL_GO or not all((NORMALIZER_MODULE, NORMALIZER_FUNCTION, NORMALIZER_SOURCE)):
        raise RuntimeError("STATIC_ONLY_FINAL_PRODUCTION_PROVIDER_API_AND_ROOT_MODEL_GO_REQUIRED")
    root = Path(__file__).resolve().parents[2]
    pinned = subprocess.check_output(["git", "show", args.source + ":" + NORMALIZER_SOURCE], cwd=root)
    if (root / NORMALIZER_SOURCE).read_bytes() != pinned:
        raise RuntimeError("PRODUCTION_PROVIDER_SOURCE_NOT_FROZEN")
    approval_path = args.approval_file.resolve(strict=True)
    artifact_path = args.artifact_dir.resolve()
    approval = json.loads(approval_path.read_text())
    expected = dict(kind="E4_C1_ENGINE_FREE_CURRENCY_MODEL", status="RUNNING", execution_limit=1,
                    model_object_limit=64, source_commit=args.source,
                    fixture_sha256=sha(Path(__file__).read_bytes()),
                    allocation_path=str(approval_path), artifact_dir=str(artifact_path))
    if any(approval.get(k) != v for k, v in expected.items()):
        raise RuntimeError("ROOT_SINGLE_EXECUTION_MODEL_ALLOCATION_REQUIRED")
    # One claim belongs to the canonical root allocation, never to a caller-
    # selected output directory. A different --artifact-dir cannot buy a rerun.
    claim_path = approval_path.with_name(approval_path.name + ".execution.claim")
    with claim_path.open("x") as stream:
        json.dump(expected, stream, sort_keys=True)
    return dict(source_commit=args.source, provider_source_sha256=sha(pinned),
                provider_source_path=str((root/NORMALIZER_SOURCE).resolve()),
                canonical_allocation_path=str(approval_path), canonical_claim_path=str(claim_path),
                fixture_sha256=expected["fixture_sha256"])


def run(result):
    # Import only stock model APIs and the actual production provider helper.
    # Never import a pytest module, node, execution client, matcher or backtester.
    from decimal import Decimal as D
    import socket
    from nautilus_trader.core.uuid import UUID4
    from nautilus_trader.core import nautilus_pyo3
    from nautilus_trader.model.currencies import BTC, SOL, USD, USDC
    from nautilus_trader.model.enums import AccountType, OrderSide, OrderType, LiquiditySide
    from nautilus_trader.model.events import AccountState, OrderFilled
    from nautilus_trader.model.identifiers import (AccountId, ClientOrderId, InstrumentId, PositionId,
        StrategyId, Symbol, TradeId, TraderId, VenueOrderId)
    from nautilus_trader.model.instruments import CryptoPerpetual
    from nautilus_trader.model.objects import AccountBalance, Money, Price, Quantity
    from nautilus_trader.model.position import Position
    from nautilus_trader.accounting.accounts.margin import MarginAccount

    if importlib.metadata.version("nautilus_trader") != "1.231.0":
        raise RuntimeError("NAUTILUS_1_231_0_REQUIRED")
    calls = result["counts"]
    owned = []
    def reserve(count=1):
        # Reserve BEFORE calling any constructor or helper returning a native
        # model. Even a future count error cannot construct object65 first.
        if calls["explicit_native_model_objects"] + count > 64:
            raise RuntimeError("MODEL_OBJECT_CAP_64_EXCEEDED")
        calls["explicit_native_model_objects"] += count
    def produce(label, callback, *a, **kw):
        reserve()
        value = callback(*a, **kw)
        owned.append(value)
        return value
    def produce_one_list(label, callback, *a, **kw):
        reserve()
        values = callback(*a, **kw)
        if not isinstance(values, list) or len(values) != 1:
            raise RuntimeError("EXPECTED_ONE_NATIVE_MODEL_RETURN:" + label)
        owned.extend(values)
        return values
    def model(cls, *a, **kw):
        return produce(cls.__name__, cls, *a, **kw)
    def no_network(*a, **kw):
        calls["network_attempts"] += 1
        raise RuntimeError("MODEL_SMOKE_NETWORK_FORBIDDEN")
    old_connect = socket.socket.connect
    socket.socket.connect = no_network
    try:
        production = importlib.import_module(NORMALIZER_MODULE)
        expected_origin = Path(result["provider_source_path"]).resolve(strict=True)
        actual_origin = Path(production.__file__).resolve(strict=True)
        if actual_origin != expected_origin or sha(actual_origin.read_bytes()) != result["provider_source_sha256"]:
            raise RuntimeError("IMPORTED_PRODUCTION_NORMALIZER_ORIGIN_OR_SHA_MISMATCH")
        normalize = getattr(production, NORMALIZER_FUNCTION)
        result["imported_provider_source_path"] = str(actual_origin)
        # Independent model positions reuse these three event UUIDs; no engine,
        # cache or journal merges the counterfactual raw/release cases.
        account_uuid = model(UUID4)
        opening_uuid = model(UUID4)
        closing_uuid = model(UUID4)
        account_id = model(AccountId, "HYPERLIQUID-model-smoke")
        trader_id = model(TraderId, "E4-C1-MODEL")
        strategy_id = model(StrategyId, "E4-C1-MODEL-001")
        position_id = model(PositionId, "E4-C1-MODEL-POSITION")
        entry_client = model(ClientOrderId, "E4-C1-MODEL-ENTRY")
        close_client = model(ClientOrderId, "E4-C1-MODEL-CLOSE")
        venue_order = model(VenueOrderId, "1")
        entry_trade = model(TradeId, "1")
        close_trade = model(TradeId, "2")
        fee = model(Money, D("0.01"), USDC)
        # Explicit reported balances, not a reconstructed cash/equity account.
        balance = model(AccountBalance, model(Money, D("100"), USDC), model(Money, D("30"), USDC),
                        model(Money, D("70"), USDC))
        stamp = time.time_ns()
        event = model(AccountState, account_id, AccountType.MARGIN, None, True, [balance], [], {}, account_uuid, stamp, stamp)
        account = model(MarginAccount, event)
        initial = (account.balance_total(USDC).as_decimal(), account.balance_locked(USDC).as_decimal(),
                   account.balance_free(USDC).as_decimal(), str(account.last_event.id))
        cases = result["cases"]

        def fill(inst, side, qty, price, *, closing=False):
            now = time.time_ns()
            return model(OrderFilled, trader_id, strategy_id, inst.id,
                close_client if closing else entry_client, venue_order, account_id,
                close_trade if closing else entry_trade, position_id, side, OrderType.LIMIT,
                qty, price, inst.quote_currency, fee, LiquiditySide.TAKER,
                closing_uuid if closing else opening_uuid, now, now)

        # Shared prices are exactly valid on BOTH preserved native tick grids.
        prices = [model(Price.from_str, v) for v in ("100.00", "110.00", "90.00")]
        for coin, base, tick, step in (("BTC", BTC, "0.1", "0.00001"), ("SOL", SOL, "0.01", "0.01")):
            # Exact stock default HL denomination: public ID USD, settlement USDC,
            # min notional10 USD and zero stock margin/fee rates. No FX instrument.
            raw = model(CryptoPerpetual, model(InstrumentId.from_str, coin+"-USD-PERP.HYPERLIQUID"),
                model(Symbol, coin), base, USD, USDC, False, len(tick.split(".")[1]), len(step.split(".")[1]),
                model(Price.from_str, tick), model(Quantity.from_str, step), 0, 0,
                min_quantity=model(Quantity.from_str, step), min_notional=model(Money, D("10"), USD),
                margin_init=D(0), margin_maint=D(0), maker_fee=D(0), taker_fee=D(0))
            # Public from_dict/to_dict only; actual production helper is the sole
            # place permitted to normalize quote/min-notional denomination.
            native_raw = produce("PyO3 raw instrument", nautilus_pyo3.CryptoPerpetual.from_dict, CryptoPerpetual.to_dict(raw))
            native_release = produce("production normalized instrument", normalize, native_raw)
            release = produce("Cython release instrument", CryptoPerpetual.from_dict, native_release.to_dict())
            assert str(raw.id) == str(release.id) == coin+"-USD-PERP.HYPERLIQUID"
            assert raw.price_increment == release.price_increment and raw.size_increment == release.size_increment
            assert raw.min_quantity == release.min_quantity
            assert release.quote_currency == release.settlement_currency == USDC
            assert release.min_notional.currency == USDC and release.min_notional.as_decimal() == D("10")
            assert raw.min_notional.currency == USD and raw.min_notional.as_decimal() == D("10")
            assert raw.margin_init == release.margin_init == raw.margin_maint == release.margin_maint == D(0)
            assert raw.maker_fee == release.maker_fee == raw.taker_fee == release.taker_fee == D(0)
            assert raw.get_cost_currency() == USD and release.get_cost_currency() == USDC
            assert all(p.as_decimal() % release.price_increment.as_decimal() == 0 for p in prices)
            qty = produce("open quantity", release.make_qty, D("2"))
            half = produce("partial quantity", release.make_qty, D("1"))
            raw_commission = None
            if coin == "BTC":
                raw_commission = produce("raw commission helper", account.calculate_commission, raw, qty, prices[0], LiquiditySide.TAKER)
                assert raw_commission.currency == USD
                raw_fill = fill(raw, OrderSide.BUY, qty, prices[0])
                raw_pos = model(Position, raw, raw_fill)
                raw_pnl = produce("raw native pnl", raw_pos.unrealized_pnl, prices[1])
                assert raw_pos.settlement_currency == raw_pnl.currency == USD
                assert raw_pnl.as_decimal() == D("20")
                assert raw_pos.realized_pnl.as_decimal() == D(0)  # USDC fee is missed by raw USD cost currency.
                assert raw_pos.commissions()[0].currency == USDC
                cases["raw_stock_negative_reference"] = dict(status="EXPECTED_LIMITATION", native_pnl=str(raw_pnl),
                    realized_pnl=str(raw_pos.realized_pnl), actual_fee=str(raw_pos.commissions()[0]),
                    helper_commission=str(raw_commission), production_money_authority=False)
            # Two representative native positions: BTC LONG and SOL SHORT.
            # Each exercises positive/negative marks and a partial close.
            for side in ((OrderSide.BUY,) if coin == "BTC" else (OrderSide.SELL,)):
                opening = fill(release, side, qty, prices[0])
                pos = model(Position, release, opening)
                pos_name = "LONG" if side == OrderSide.BUY else "SHORT"
                up = produce("native positive pnl", pos.unrealized_pnl, prices[1] if side == OrderSide.BUY else prices[2])
                down = produce("native negative pnl", pos.unrealized_pnl, prices[2] if side == OrderSide.BUY else prices[1])
                assert pos.settlement_currency == USDC and up.currency == down.currency == USDC
                assert up.as_decimal() == D("20") and down.as_decimal() == D("-20")
                assert pos.realized_pnl.currency == USDC and pos.realized_pnl.as_decimal() == D("-0.01")
                close_px = prices[1] if side == OrderSide.BUY else prices[2]
                closing = fill(release, OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY, half, close_px, closing=True)
                cashflow = produce_one_list("native close pnl", account.calculate_pnls, release, closing, pos)
                assert len(cashflow) == 1 and cashflow[0].currency == USDC and cashflow[0].as_decimal() == D("10")
                pos.apply(closing)
                assert pos.quantity.as_decimal() == D("1") and pos.realized_pnl.currency == USDC
                assert pos.realized_pnl.as_decimal() == D("9.98")
                assert sum((m.as_decimal() for m in pos.commissions()), D(0)) == D("0.02")
                assert all(m.currency == USDC for m in pos.commissions())
                cases[coin+"_"+pos_name] = dict(status="PASS", positive_pnl=str(up), negative_pnl=str(down),
                    partial_realized=str(pos.realized_pnl), native_close_cashflow=str(cashflow[0]),
                    commissions=[str(m) for m in pos.commissions()])
            # Native zero rates remain zero; they NEVER establish buying power.
            initial_margin = commission = None
            if coin == "BTC":
                initial_margin = produce("native margin helper", account.calculate_margin_init, release, qty, prices[0])
                commission = produce("native commission helper", account.calculate_commission, release, qty, prices[0], LiquiditySide.TAKER)
                assert initial_margin.currency == commission.currency == USDC
                assert initial_margin.as_decimal() == commission.as_decimal() == D(0)
            cases[coin+"_denomination"] = dict(status="PASS", id=str(release.id), raw_cost_currency=str(raw.get_cost_currency()),
                release_cost_currency=str(release.get_cost_currency()), raw_commission=str(raw_commission),
                release_margin=str(initial_margin), release_commission=str(commission), min_notional=str(release.min_notional),
                zero_margin_rates_preserved=True, buying_power_authority=False)
        assert initial == (account.balance_total(USDC).as_decimal(), account.balance_locked(USDC).as_decimal(),
                           account.balance_free(USDC).as_decimal(), str(account.last_event.id))
        cases["reported_AccountState_holds_preserved"] = dict(status="PASS", total="100", locked="30", free="70",
            native_cash_posted=False, unchanged_event_id=initial[3])
        assert calls["network_attempts"] == 0
    finally:
        socket.socket.connect = old_connect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--approval-file", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()
    result = dict(schema="e4-c1-engine-free-currency-model-v1", status="FAIL", started_ns=time.time_ns(), cases={},
        counts=dict(explicit_native_model_objects=0, network_attempts=0, trading_nodes=0, engines=0))
    try:
        result.update(preflight(args))
        run(result)
        result["status"] = "PASS"
    except BaseException as exc:
        result.update(error=repr(exc), traceback=traceback.format_exc())
    result["finished_ns"] = time.time_ns()
    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    (args.artifact_dir/"currency-model-result.json").write_text(json.dumps(result, indent=2, sort_keys=True))
    print(json.dumps(dict(status=result["status"], counts=result["counts"], error=result.get("error"))))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
