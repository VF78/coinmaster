"""Explicit native historical DP policy and metadata-only lot diagnostic.

This module does not create an engine, query a venue or implement PnL.
"""
from decimal import Decimal


def native_marked_deposit_equity(strategy):
    """Read existing native cash/UPNL only at complete fresh paired marks."""
    config=strategy.config;now=strategy.clock.timestamp_ns()
    marks=[strategy._latest_marks.get(i) for i in (config.btc_id,config.sol_id)]
    if any(m is None or not 0<=now-m.ts_event<=config.max_mark_age_ns for m in marks):return None
    if marks[0].ts_event!=marks[1].ts_event:return None
    account=strategy.cache.account_for_venue(config.btc_id.venue)
    if account is None:return None
    if any(str(currency)!=config.deposit_currency for currency in account.balances_total()):
        raise ValueError("RESEARCH_DP_NATIVE_CURRENCY_MISMATCH")
    for position in strategy.cache.positions_open():
        if position.instrument_id not in (config.btc_id,config.sol_id):raise ValueError("RESEARCH_DP_FOREIGN_POSITION")
        instrument=strategy.cache.instrument(position.instrument_id)
        if str(instrument.settlement_currency)!=config.deposit_currency:raise ValueError("RESEARCH_DP_NATIVE_CURRENCY_MISMATCH")
    return strategy._v3_equity()  # Existing native account + position.unrealized_pnl.


def metadata_lot_constraints(metadata, *, btc_only=False):
    if isinstance(metadata,dict) and isinstance(metadata.get("assets"),list):
        assets={item["name"]:item for item in metadata["assets"] if item.get("name") in ("BTC","SOL")}
        metadata={coin:dict(id=coin+"-USD-PERP.HYPERLIQUID",size_precision=item["szDecimals"],
            size_increment=format(Decimal(1).scaleb(-item["szDecimals"]),"f"),min_quantity=format(Decimal(1).scaleb(-item["szDecimals"]),"f")) for coin,item in assets.items()}
    if not isinstance(metadata,dict) or set(metadata)!={"BTC","SOL"}:raise ValueError("HL_METADATA_BTC_SOL_REQUIRED")
    result={}
    for coin,item in metadata.items():
        precision=item.get("size_precision");step=Decimal(str(item.get("size_increment")));minimum=Decimal(str(item.get("min_quantity")))
        if (item.get("id")!=coin+"-USD-PERP.HYPERLIQUID" or type(precision) is not int or precision<0
            or not step.is_finite() or step!=Decimal(1).scaleb(-precision)
            or not minimum.is_finite() or minimum<step or minimum%step):raise ValueError("HL_NATIVE_LOT_METADATA_INVALID")
        if coin=="BTC" and precision!=5:raise ValueError("HL_BTC_CURRENT_PRECISION_5_REQUIRED")
        result[coin]=dict(step=format(step,"f"),min_quantity=format(minimum,"f"),size_precision=precision)
    if btc_only:
        result["SOL"]=dict(step="0.1",min_quantity=None,size_precision=1)
    return result


def research_qualification(mode,quantity_model,metadata,runtime,reader,account_id):
    if mode=="legacy_reference":
        if quantity_model!="legacy_bybit" or any(x is not None for x in (metadata,runtime,reader)):
            raise ValueError("LEGACY_REFERENCE_MUST_REMAIN_EXPLICITLY_UNMODIFIED")
        return {},{}
    if mode!="live_qualification" or quantity_model not in ("legacy_bybit","hl_lot_diagnostic","btc_lot_diagnostic"):
        raise ValueError("EXPLICIT_QUALIFICATION_MODE_REQUIRED")
    if runtime is None or not callable(reader) or not account_id:raise ValueError("QUALIFICATION_DP55_RUNTIME_READER_REQUIRED")
    if runtime.deposit_currency!="USDT":raise ValueError("RESEARCH_DP_NATIVE_CURRENCY_MISMATCH")
    if runtime.deposit_protection_state(instance_id=runtime.owner,account_id=account_id) is not None or runtime.all_submissions():
        raise ValueError("QUALIFICATION_REQUIRES_FRESH_DP_STORE")
    constraints=metadata_lot_constraints(metadata,btc_only=quantity_model=="btc_lot_diagnostic") if quantity_model in ("hl_lot_diagnostic","btc_lot_diagnostic") else {}
    if quantity_model=="legacy_bybit" and metadata is not None:raise ValueError("LEGACY_BYBIT_LOTS_CANNOT_ACCEPT_HL_METADATA")
    def initialize_allowed():
        return runtime.deposit_protection_state(instance_id=runtime.owner,account_id=account_id) is None and not runtime.all_submissions()
    return dict(deposit_runtime=runtime,deposit_instance_id=runtime.owner,deposit_account_id=account_id,
        deposit_currency="USDT",deposit_drawdown_limit_percent=55,deposit_high_water_basis="OBSERVED_NATIVE_EQUITY_PEAK",deposit_check_interval_secs=60,deposit_observe_on_quote=True,
        deposit_equity_reader=reader,deposit_initialization_allowed=initialize_allowed,market_exit_reduce_only=True),constraints


def verified_flat_calendar_returns(cash_rows, initial, start, end, terminal_cash):
    """Calendar carry-forward derived from native mutations and verified terminal cash.

    This produces report rows only, never account events or cash postings.
    """
    from datetime import datetime
    from decimal import localcontext
    months={};last=Decimal(initial)
    for point in cash_rows:
        stamp=datetime.fromisoformat(point["timestamp"])
        if start<=stamp<end:
            last=Decimal(point["total"]);months[stamp.strftime("%Y-%m")]=last
    if last!=Decimal(terminal_cash):raise ValueError("DP_FLAT_TERMINAL_NATIVE_CASH_MISMATCH")
    cursor=start.replace(day=1,hour=0,minute=0,second=0,microsecond=0);prior=Decimal(initial);rows=[]
    while cursor<end:
        month=cursor.strftime("%Y-%m");total=months.get(month,prior)
        with localcontext() as context:
            context.prec=80
            rows.append(dict(month=month,total=str(total),**{"return":str(total/prior-1)}))
        prior=total
        cursor=cursor.replace(year=cursor.year+(cursor.month==12),month=1 if cursor.month==12 else cursor.month+1)
    return rows
