"""Perps-only live money view from one strict, reconciled Hyperliquid Info receipt.

This does not post cash, funding, fees or PnL. Venue accountValue already
includes position value and all venue cash effects; adding native UPNL again
would double count. Unsupported account abstraction/margin modes fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Awaitable, Callable, Sequence

from nautilus_trader.model.currencies import USDC

from coinmaster.ops.hl_info_receipt import InfoReceipt, IncompleteInfoReport
from coinmaster.venues.effective_fees import CURRENT_HL_FEES, HL_FEE_RESERVE_BUFFER


def _amount(value: str, name: str) -> Decimal:
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise IncompleteInfoReport("LIVE_MONEY_BAD_" + name) from exc
    if not result.is_finite():
        raise IncompleteInfoReport("LIVE_MONEY_BAD_" + name)
    return result


@dataclass(frozen=True)
class SelectedCrossAsset:
    coin: str
    leverage: int
    mark: Decimal
    max_trade_sizes: tuple[Decimal,Decimal] | None = None
    available_to_trade: tuple[Decimal,Decimal] | None = None


async def collect_selected_cross_assets(
    info: Callable[[dict[str, Any]], Awaitable[Any]], *,
    account_ref: str, coins: frozenset[str], require_venue_limits: bool = False,
) -> tuple[SelectedCrossAsset, ...]:
    """Read the selected account's leverage/mark, never side-indexed capacity."""
    if not coins or not coins.issubset({"BTC", "SOL"}):
        raise IncompleteInfoReport("LIVE_ASSET_SCOPE_UNKNOWN")
    selected = []
    for coin in sorted(coins):
        try:
            raw = await info({"type": "activeAssetData", "user": account_ref, "coin": coin})
        except IncompleteInfoReport:
            raise
        except Exception as exc:
            raise IncompleteInfoReport("LIVE_ASSET_TRANSPORT_FAILED") from exc
        if (
            not isinstance(raw, dict) or not isinstance(raw.get("user"), str)
            or raw["user"].lower() != account_ref.lower()
            or raw.get("coin") != coin or not isinstance(raw.get("leverage"), dict)
            or raw["leverage"].get("type") != "cross"
            or type(raw["leverage"].get("value")) is not int
            or raw["leverage"]["value"] <= 0
        ):
            raise IncompleteInfoReport("LIVE_ASSET_ACCOUNT_OR_LEVERAGE_UNKNOWN")
        mark = _amount(raw.get("markPx"), "SELECTED_MARK")
        if mark <= 0:
            raise IncompleteInfoReport("LIVE_ASSET_MARK_UNKNOWN")
        limits=available=None
        if require_venue_limits:
            if (not isinstance(raw.get('maxTradeSzs'),list) or len(raw['maxTradeSzs'])!=2
                or not isinstance(raw.get('availableToTrade'),list) or len(raw['availableToTrade'])!=2):
                raise IncompleteInfoReport('LIVE_VENUE_TRADE_LIMITS_UNKNOWN')
            limits=tuple(_amount(v,'MAX_TRADE_SIZE') for v in raw['maxTradeSzs'])
            available=tuple(_amount(v,'AVAILABLE_TO_TRADE') for v in raw['availableToTrade'])
            if min(*limits,*available)<0:raise IncompleteInfoReport('LIVE_VENUE_TRADE_LIMITS_INVALID')
        selected.append(SelectedCrossAsset(coin,raw['leverage']['value'],mark,limits,available))
    return tuple(selected)


@dataclass(frozen=True)
class LivePerpsMoneyView:
    account: str
    dex: str
    end_ms: int
    equity: Decimal
    free_collateral: Decimal
    margin_used: Decimal
    raw_usd: Decimal
    selected_assets: tuple[SelectedCrossAsset, ...] = ()
    position_sizes: tuple[tuple[str, Decimal], ...] = ()
    native_revision: int | None = None
    account_mode: str = "disabled"
    equity_basis: str = "HYPERLIQUID_CLASSIC_PERPS_ACCOUNT_VALUE_V1"
    margin_basis: str = "CLASSIC_PERPS_REPORTED_MARGIN"

    def require_fresh(self, now_ms: int, max_age_ms: int) -> None:
        if (
            not isinstance(now_ms, int) or not isinstance(max_age_ms, int)
            or max_age_ms <= 0 or self.end_ms > now_ms + 1
            or now_ms - self.end_ms > max_age_ms
        ):
            raise IncompleteInfoReport("LIVE_MONEY_STALE_OR_UNKNOWN")


def live_perps_money_view(
    receipt: InfoReceipt, *, account_ref: str, dex: str, account_id: str,
    native_account, native_positions: Sequence[object], now_ms: int,
    max_age_ms: int = 10_000, selected_assets: tuple[SelectedCrossAsset, ...] = (),
    native_revision: int | None = None,
) -> LivePerpsMoneyView:
    if isinstance(receipt,InfoReceipt) and receipt.account_mode=='unifiedAccount':
        from coinmaster.ops.hl_unified_account import native_unified_money,EQUITY_BASIS,HOLD_BASIS
        if (receipt.account.lower()!=account_ref.lower() or dex!='' or receipt.dex!=dex
            or receipt.account_role!='user' or receipt.abstraction!='unifiedAccount' or receipt.dex_abstraction is not False
            or receipt.equity_basis!=EQUITY_BASIS):raise IncompleteInfoReport('UNIFIED_MODE_PROOF_UNKNOWN')
        total,hold,free,sizes=native_unified_money({'balances':list(receipt.spot_balances)},list(receipt.all_dex_states),
            native_account=native_account,native_positions=native_positions,account_id=account_id)
        if hold and not native_positions and not receipt.open_orders:raise IncompleteInfoReport('UNIFIED_UNATTRIBUTED_HOLD')
        require_native_unified_projection(native_account,total,hold,free)
        view=LivePerpsMoneyView(account_ref,dex,receipt.end_ms,total,free,hold,total,selected_assets,sizes,native_revision,
            'unifiedAccount',EQUITY_BASIS,HOLD_BASIS)
        view.require_fresh(now_ms,max_age_ms)
        return view
    if (
        not isinstance(receipt, InfoReceipt)
        or receipt.account.lower() != account_ref.lower() or receipt.dex != dex
        or receipt.account_role != "user" or receipt.abstraction != "disabled"
        or receipt.dex_abstraction is not False
        or len(receipt.account_summary) != 5
        or len(receipt.cross_account_summary) != 4
    ):
        raise IncompleteInfoReport("LIVE_MONEY_ACCOUNT_SCOPE_OR_MODE_UNKNOWN")
    equity, raw, margin, notional, free = (
        _amount(value, name) for value, name in zip(
            receipt.account_summary,
            ("EQUITY", "RAW_USD", "MARGIN", "NOTIONAL", "WITHDRAWABLE"),
        )
    )
    cross_equity, cross_raw, cross_margin, cross_notional = (
        _amount(value, name) for value, name in zip(
            receipt.cross_account_summary,
            ("CROSS_EQUITY", "CROSS_RAW_USD", "CROSS_MARGIN", "CROSS_NOTIONAL"),
        )
    )
    # A standard account with only cross-margin positions has identical
    # total/cross summaries. Isolated collateral cannot be mapped by this view.
    if (
        (equity, raw, margin, notional) !=
        (cross_equity, cross_raw, cross_margin, cross_notional)
        or equity <= 0 or margin < 0 or notional < 0 or free < 0
        or free > equity
    ):
        raise IncompleteInfoReport("LIVE_MONEY_SUMMARY_INCONSISTENT")
    if native_account is None or str(native_account.id) != account_id or native_account.base_currency is not None:
        raise IncompleteInfoReport("LIVE_MONEY_NATIVE_ACCOUNT_MISMATCH")
    native_total = native_account.balance_total(USDC)
    native_free = native_account.balance_free(USDC)
    # Pinned 1.231 preserves negative cross totalRawUsd. It only raises
    # nonnegative total to withdrawable; neither projection is venue equity.
    if (
        native_total is None or native_free is None
        or native_total.currency != USDC or native_free.currency != USDC
        or native_total.as_decimal() != (cross_raw if cross_raw < 0 else max(cross_raw, free))
        or native_free.as_decimal() != free
    ):
        raise IncompleteInfoReport("LIVE_MONEY_NATIVE_BALANCE_MISMATCH")
    raw_positions = {}
    position_notional = Decimal("0")
    for row in receipt.positions:
        size = _amount(row["szi"], "POSITION_SIZE")
        if size == 0:
            continue
        leverage = row.get("leverage")
        if not isinstance(leverage, dict) or leverage.get("type") != "cross":
            raise IncompleteInfoReport("LIVE_MONEY_ISOLATED_POSITION_UNSUPPORTED")
        entry = _amount(row.get("entryPx"), "POSITION_ENTRY")
        value = _amount(row.get("positionValue"), "POSITION_VALUE")
        upnl = _amount(row.get("unrealizedPnl"), "POSITION_UPNL")
        if entry <= 0 or value <= 0 or abs(
            upnl - (value - abs(size) * entry) * (1 if size > 0 else -1)
        ) > Decimal("0.000001"):
            raise IncompleteInfoReport("LIVE_MONEY_POSITION_UPNL_MISMATCH")
        position_notional += value
        coin = row["coin"]
        if coin in raw_positions:
            raise IncompleteInfoReport("LIVE_MONEY_DUPLICATE_POSITION")
        raw_positions[coin] = size
    native = {}
    for position in native_positions:
        if str(position.account_id) != account_id:
            raise IncompleteInfoReport("LIVE_MONEY_NATIVE_POSITION_ACCOUNT")
        coin = str(position.instrument_id).split("-USD-PERP.")[0]
        if coin in native or coin not in {"BTC", "SOL"}:
            raise IncompleteInfoReport("LIVE_MONEY_NATIVE_POSITION_SCOPE")
        qty = position.quantity.as_decimal()
        native[coin] = qty if position.is_long else -qty
    if position_notional != notional:
        raise IncompleteInfoReport("LIVE_MONEY_NOTIONAL_POSITION_MISMATCH")
    if raw_positions != native:
        raise IncompleteInfoReport("LIVE_MONEY_POSITION_MISMATCH")
    if selected_assets and (
        len(selected_assets) != 2 or {item.coin for item in selected_assets} != {"BTC", "SOL"}
    ):
        raise IncompleteInfoReport("LIVE_ASSET_SCOPE_UNKNOWN")
    view = LivePerpsMoneyView(
        account_ref, dex, receipt.end_ms, equity, free, margin, raw,
        selected_assets, tuple(sorted(raw_positions.items())), native_revision,
    )
    view.require_fresh(now_ms, max_age_ms)
    return view



def require_native_unified_projection(account,total,hold,free):
    balance=account.balance_total(USDC);available=account.balance_free(USDC)
    margin=account.margin_init_for_currency(USDC);maintenance=account.margin_maint_for_currency(USDC)
    if (balance is None or available is None or balance.currency!=USDC or available.currency!=USDC
        or balance.as_decimal()!=total or available.as_decimal()!=free
        or margin is None or maintenance is None or margin.currency!=USDC or maintenance.currency!=USDC
        or margin.as_decimal()!=hold or maintenance.as_decimal()!=hold):
        raise IncompleteInfoReport('UNIFIED_NATIVE_ACCOUNT_REFRESH_REQUIRED')


def prospective_cross_margin_core(
    *, equity, free_collateral, selected_assets, positions, pending_openings,
    coin, side, quantity, max_gross_multiple, fee_reserve_rate=HL_FEE_RESERVE_BUFFER,
):
    """Shared pure economic costs; venue-side availability is a separate live gate."""
    try:
        fee_reserve_rate=CURRENT_HL_FEES.reserve_taker(fee_reserve_rate)
    except (TypeError,ValueError):
        return None
    assets={item.coin:item for item in selected_assets}
    if (set(assets)!={"BTC","SOL"} or set(positions)-set(assets)
        or coin not in assets or side not in {"BUY","SELL"}
        or not quantity.is_finite() or quantity<=0 or max_gross_multiple<=0
        or not equity.is_finite() or not free_collateral.is_finite()):
        return None
    buys={name:Decimal(0) for name in assets};sells=dict(buys)
    fees_notional=quantity*assets[coin].mark
    for pending_coin,pending_side,leaves in pending_openings:
        if (pending_coin not in assets or pending_side not in {"BUY","SELL"}
            or not leaves.is_finite() or leaves<=0):return None
        (buys if pending_side=="BUY" else sells)[pending_coin]+=leaves
        fees_notional+=leaves*assets[pending_coin].mark
    (buys if side=="BUY" else sells)[coin]+=quantity
    opening_collateral=gross=Decimal(0)
    for name,item in assets.items():
        current=positions.get(name,Decimal(0))
        if not current.is_finite() or not item.mark.is_finite() or item.mark<=0 or item.leverage<=0:
            return None
        opening_collateral+=(buys[name]+sells[name])*item.mark/item.leverage
        gross+=max(abs(current+buys[name]),abs(current-sells[name]))*item.mark
    fee_reserve=fees_notional*fee_reserve_rate
    return dict(allowed=opening_collateral+fee_reserve<=free_collateral and gross<=equity*max_gross_multiple,
        assets=assets,buys=buys,sells=sells,opening_collateral=opening_collateral,
        fee_reserve=fee_reserve,gross=gross,fee_reserve_rate=fee_reserve_rate)


def prospective_cross_margin_ok(
    view: LivePerpsMoneyView, *, positions: dict[str,Decimal],
    pending_openings: Sequence[tuple[str,str,Decimal]], coin: str, side: str,
    quantity: Decimal, max_gross_multiple: Decimal,
    fee_reserve_rate: Decimal=HL_FEE_RESERVE_BUFFER,
) -> bool:
    """Common economic core plus mandatory authoritative Unified venue limits."""
    core=prospective_cross_margin_core(equity=view.equity,free_collateral=view.free_collateral,
        selected_assets=view.selected_assets,positions=positions,pending_openings=pending_openings,
        coin=coin,side=side,quantity=quantity,max_gross_multiple=max_gross_multiple,
        fee_reserve_rate=fee_reserve_rate)
    if core is None:return False
    assets,buys,sells=core["assets"],core["buys"],core["sells"]
    if view.account_mode=="unifiedAccount":
        asset=assets[coin];index=0 if side=="BUY" else 1
        if asset.max_trade_sizes is None or asset.available_to_trade is None:return False
        for name,item in assets.items():
            for which,pending in enumerate((buys[name],sells[name])):
                if pending and (item.max_trade_sizes is None or item.available_to_trade is None
                    or pending>item.max_trade_sizes[which] or item.available_to_trade[which]<0):return False
        reserve=core["opening_collateral"]+core["fee_reserve"]
        proposed=(buys if side=="BUY" else sells)[coin]
        if proposed>asset.max_trade_sizes[index] or reserve>asset.available_to_trade[index]:return False
        return core["allowed"]
    # Preserve the previously qualified non-Unified live account projection.
    prospective_im=sum(max(abs(positions.get(name,Decimal(0))+buys[name]),
        abs(positions.get(name,Decimal(0))-sells[name]))*item.mark/item.leverage for name,item in assets.items())
    return max(view.margin_used,prospective_im)+core["fee_reserve"]<=view.equity and core["gross"]<=view.equity*max_gross_multiple


def native_usdc_margin_core(strategy,instrument_id,side,quantity,ts_now):
    """Cached native cash+native UPNL; economic free E-held IM, no venue limits invented."""
    account=strategy.cache.account_for_venue(strategy.config.btc_id.venue)
    if account is None:return False
    cash=account.balance_total(USDC)
    if cash is None:return False
    equity=cash.as_decimal();held_im=Decimal(0);positions={};assets=[];pending=[]
    leverage=dict(strategy.config.native_hl_selected_leverage)
    ids=(strategy.config.btc_id,strategy.config.sol_id)
    try:
        for identifier,coin in zip(ids,("BTC","SOL")):
            mark=strategy._latest_marks.get(identifier)
            if mark is None or not 0<=ts_now-mark.ts_event<=strategy.config.max_mark_age_ns:return False
            selected=leverage[identifier]
            assets.append(SelectedCrossAsset(coin,selected,Decimal(mark.price)))
        for position in strategy.cache.positions_open():
            if position.instrument_id not in ids:return False
            coin="BTC" if position.instrument_id==ids[0] else "SOL"
            if coin in positions:return False
            instrument=strategy.cache.instrument(position.instrument_id)
            if instrument.quote_currency!=USDC or instrument.settlement_currency!=USDC:return False
            mark=strategy._latest_marks[position.instrument_id]
            pnl=position.unrealized_pnl(instrument.make_price(mark.price))
            if pnl.currency!=USDC:return False
            equity+=pnl.as_decimal()
            qty=position.quantity.as_decimal()
            positions[coin]=qty if position.is_long else -qty
            initial,_,_=strategy.config.margin_policy.margin_for(position.instrument_id,qty,ts_now)
            held_im+=initial
        owned_pending={str(order.client_order_id):order for order in
            (*strategy.cache.orders_open(),*strategy.cache.orders_inflight())}
        for order in owned_pending.values():
            if order.is_closed or order.is_reduce_only:continue
            if order.instrument_id not in ids:return False
            leaves=order.quantity.as_decimal()-order.filled_qty.as_decimal()
            pending.append(("BTC" if order.instrument_id==ids[0] else "SOL",order.side.name,leaves))
        coin="BTC" if instrument_id==ids[0] else "SOL" if instrument_id==ids[1] else ""
        core=prospective_cross_margin_core(equity=equity,free_collateral=equity-held_im,
            selected_assets=assets,positions=positions,pending_openings=tuple(pending),
            coin=coin,side=side.name,quantity=quantity,max_gross_multiple=strategy.config.max_gross_to_active)
        tier_reason=None
        if core is not None:
            for identifier,name in zip(ids,("BTC","SOL")):
                held=positions.get(name,Decimal(0))
                worst=max(abs(held+core["buys"][name]),abs(held-core["sells"][name]))
                if worst:
                    try:
                        strategy.config.margin_policy.margin_for(identifier,worst,ts_now)
                    except ValueError as error:
                        tier_reason="CURRENT_HL_PROSPECTIVE_TIER_DENIED:"+str(error)
                        core=dict(core,allowed=False)
                        break
        strategy._last_hl_admission_audit=dict(E=str(equity),economic_free_collateral=str(equity-held_im),
            public_tier_guard_reason=tier_reason or "CURRENT_HL_PROSPECTIVE_TIER_PASS",
            held_initial_margin=str(held_im),opening_collateral=None if core is None else str(core["opening_collateral"]),
            fee_reserve=None if core is None else str(core["fee_reserve"]),
            prospective_gross=None if core is None else str(core["gross"]),
            admission_allowed=bool(core is not None and core["allowed"]))
        if core is not None and not core["allowed"]:
            strategy.pre_submit_gate_blocks.append(dict(timestamp=str(ts_now),action="HL_ADMISSION_CORE",
                reason=tier_reason or "SHARED_ECONOMIC_HEADROOM_OR_GROSS_DENIED",**strategy._last_hl_admission_audit))
        return core is not None and core["allowed"]
    except (AttributeError,KeyError,RuntimeError,TypeError,ValueError):
        return False


@dataclass(frozen=True)
class CheapPortfolioObservation:
    """Observed money only. Never an order/recovery/certificate capability."""
    equity: Decimal
    raw_usd: Decimal
    free_collateral: Decimal
    margin_used: Decimal
    position_sizes: tuple
    native_revision: int
    fill_epoch: int
    ws_epoch: int
    generation_started_ns: int
    response_completed_ns: int
    source_available_ns: int
    native_account_event_id: str
    account_mode: str = "disabled"
    equity_basis: str = "HYPERLIQUID_CLASSIC_PERPS_ACCOUNT_VALUE_V1"

    def require_current(self,*,now_ns,revision,fill_epoch,ws_epoch):
        if (not self.generation_started_ns<=self.response_completed_ns<=now_ns
            or now_ns-self.generation_started_ns>9_000_000_000
            or (revision,fill_epoch,ws_epoch)!=(self.native_revision,self.fill_epoch,self.ws_epoch)):
            raise IncompleteInfoReport("PORTFOLIO_OBSERVATION_STALE_OR_MOVED")


def cheap_portfolio_observation(raw,*,account_id,native_account,native_positions,strategy_id,
                                revision,fill_epoch,ws_epoch,started_ns,completed_ns,available_ns):
    """One actual clearinghouseState response; no invented Info receipt or OHLC."""
    if not isinstance(raw,dict) or not isinstance(raw.get('assetPositions'),list):
        raise IncompleteInfoReport('PORTFOLIO_RESPONSE_MALFORMED')
    summary=raw.get('marginSummary');cross=raw.get('crossMarginSummary')
    if not isinstance(summary,dict) or not isinstance(cross,dict):raise IncompleteInfoReport('PORTFOLIO_SUMMARY_UNKNOWN')
    keys=('accountValue','totalRawUsd','totalMarginUsed','totalNtlPos')
    values=tuple(_amount(summary.get(k),k) for k in keys)
    if values!=tuple(_amount(cross.get(k),k) for k in keys):raise IncompleteInfoReport('PORTFOLIO_CROSS_MODE_UNKNOWN')
    equity,cash,margin,notional=values;free=_amount(raw.get('withdrawable'),'WITHDRAWABLE')
    if equity<=0 or margin<0 or notional<0 or not 0<=free<=equity:raise IncompleteInfoReport('PORTFOLIO_VALUES_INVALID')
    positions={};seen_coins=set();actual_notional=Decimal(0)
    for item in raw['assetPositions']:
        row=item.get('position') if isinstance(item,dict) else None
        if not isinstance(row,dict) or row.get('coin') not in ('BTC','SOL'):raise IncompleteInfoReport('PORTFOLIO_FOREIGN_POSITION')
        coin=row['coin'];size=_amount(row.get('szi'),'SIZE')
        if coin in seen_coins:raise IncompleteInfoReport('PORTFOLIO_DUPLICATE_POSITION')
        seen_coins.add(coin)
        if row.get('leverage',{}).get('type')!='cross':raise IncompleteInfoReport('PORTFOLIO_ISOLATED_UNSUPPORTED')
        value=_amount(row.get('positionValue'),'POSITION_VALUE')
        if value<0:raise IncompleteInfoReport('PORTFOLIO_POSITION_VALUE_INVALID')
        actual_notional+=value
        if size:positions[coin]=size
    native={}
    for position in native_positions:
        coin=str(position.instrument_id).split('-USD-PERP.')[0]
        if coin not in ('BTC','SOL') or coin in native or str(position.account_id)!=account_id or str(position.strategy_id)!=strategy_id:
            raise IncompleteInfoReport('PORTFOLIO_NATIVE_POSITION_SCOPE')
        native[coin]=position.quantity.as_decimal()*(1 if position.is_long else -1)
    if native!=positions or actual_notional!=notional:raise IncompleteInfoReport('PORTFOLIO_NATIVE_POSITION_MISMATCH')
    if native_account is None or str(native_account.id)!=account_id or native_account.base_currency is not None:
        raise IncompleteInfoReport('PORTFOLIO_NATIVE_ACCOUNT_UNKNOWN')
    total=native_account.balance_total(USDC);native_free=native_account.balance_free(USDC)
    if total is None or native_free is None or total.currency!=USDC or native_free.currency!=USDC or total.as_decimal()!=(cash if cash<0 else max(cash,free)) or native_free.as_decimal()!=free:
        raise IncompleteInfoReport('PORTFOLIO_ACCOUNT_REFRESH_REQUIRED')
    event_id=getattr(native_account.last_event,'id',None) or getattr(native_account.last_event,'event_id',None)
    if not event_id:raise IncompleteInfoReport('PORTFOLIO_ACCOUNT_EVENT_UNKNOWN')
    result=CheapPortfolioObservation(equity,cash,free,margin,tuple(sorted(native.items())),revision,fill_epoch,ws_epoch,
        started_ns,completed_ns,available_ns,str(event_id))
    result.require_current(now_ns=completed_ns,revision=revision,fill_epoch=fill_epoch,ws_epoch=ws_epoch)
    return result


def materialize_live_c1_input(observation,*,native_positions,native_marks,native_cache,account_event_id,
                              strategy_id,account_id,decision_ns,monotonic_ns,revision,fill_epoch,ws_epoch,max_mark_age_ns):
    """Read native PnL at real HL marks; no manufactured OHLC or cash additions."""
    from coinmaster.strategy.c1_inputs import C1PositionInput,C1DecisionInput
    if not isinstance(observation,CheapPortfolioObservation):raise IncompleteInfoReport('C1_LIVE_OBSERVATION_UNKNOWN')
    observation.require_current(now_ns=monotonic_ns,revision=revision,fill_epoch=fill_epoch,ws_epoch=ws_epoch)
    if str(account_event_id)!=observation.native_account_event_id:raise IncompleteInfoReport('C1_LIVE_ACCOUNT_EVENT_MOVED')
    rows=[];sizes={}
    for position in native_positions:
        instrument=str(position.instrument_id);coin=instrument.split('-USD-PERP.')[0]
        if coin not in ('BTC','SOL') or coin in sizes or str(position.account_id)!=account_id or str(position.strategy_id)!=strategy_id:
            raise IncompleteInfoReport('C1_LIVE_POSITION_SCOPE')
        mark=native_marks.get(position.instrument_id)
        if (mark is None or not 0<=decision_ns-mark.ts_event<=max_mark_age_ns
            or not 0<=decision_ns-mark.ts_init<=max_mark_age_ns):raise IncompleteInfoReport('C1_LIVE_MARK_STALE')
        price=Decimal(str(mark.price));native_instrument=native_cache.instrument(position.instrument_id)
        native_pnl=position.unrealized_pnl(native_instrument.make_price(price))
        if observation.account_mode=='unifiedAccount' and (native_pnl.currency!=USDC
            or native_instrument.quote_currency!=USDC or native_instrument.settlement_currency!=USDC):
            raise IncompleteInfoReport('UNIFIED_NATIVE_PNL_CURRENCY_UNSUPPORTED')
        pnl=native_pnl.as_decimal()
        quantity=position.quantity.as_decimal();sizes[coin]=quantity*(1 if position.is_long else -1)
        rows.append(C1PositionInput(instrument,str(position.id),position.ts_opened,position.is_long,quantity,
            native_instrument.size_increment.as_decimal(),price,mark.ts_event,pnl,str(getattr(native_pnl,'currency','UNKNOWN'))))
    if tuple(sorted(sizes.items()))!=observation.position_sizes:raise IncompleteInfoReport('C1_LIVE_POSITION_MOVED')
    return C1DecisionInput(observation.equity,observation.source_available_ns,decision_ns,fill_epoch,revision,ws_epoch,
        observation.native_account_event_id,tuple(sorted(rows,key=lambda row:row.instrument_id)),observation.equity_basis)


def cheap_unified_observation(raw_spot,all_dex,*,account_id,native_account,native_positions,strategy_id,
                              revision,fill_epoch,ws_epoch,started_ns,completed_ns,available_ns,native_open_orders=(),native_spot_money=None):
    from coinmaster.ops.hl_unified_account import native_unified_money,EQUITY_BASIS
    total,hold,free,sizes=native_unified_money(raw_spot,all_dex,native_account=native_account,
        native_positions=native_positions,account_id=account_id,strategy_id=strategy_id,native_spot_money=native_spot_money)
    for order in native_open_orders:
        if (str(order.account_id)!=account_id or str(order.strategy_id)!=strategy_id
            or str(order.instrument_id) not in ('BTC-USD-PERP.HYPERLIQUID','SOL-USD-PERP.HYPERLIQUID')):
            raise IncompleteInfoReport('UNIFIED_UNKNOWN_NATIVE_ORDER')
    if hold and not native_positions and not native_open_orders:raise IncompleteInfoReport('UNIFIED_UNATTRIBUTED_HOLD')
    require_native_unified_projection(native_account,total,hold,free)
    event_id=getattr(native_account.last_event,'id',None) or getattr(native_account.last_event,'event_id',None)
    if not event_id:raise IncompleteInfoReport('UNIFIED_NATIVE_ACCOUNT_EVENT_UNKNOWN')
    value=CheapPortfolioObservation(total,total,free,hold,sizes,revision,fill_epoch,ws_epoch,started_ns,completed_ns,
        available_ns,str(event_id),'unifiedAccount',EQUITY_BASIS)
    value.require_current(now_ns=completed_ns,revision=revision,fill_epoch=fill_epoch,ws_epoch=ws_epoch)
    return value


def native_lifecycle_feasible(instrument,quantity,price,*,tp_fractions=(),cut_divisor=4):
    """Conservative current-price lot proof; no rounding up or future-price promise."""
    step=instrument.size_increment.as_decimal()
    if any(not isinstance(v,Decimal) or not v.is_finite() or v<=0 for v in (quantity,price,step)):
        return False
    if quantity%step or type(cut_divisor) is not int or cut_divisor not in (2,4):return False
    minimum=instrument.min_quantity.as_decimal() if instrument.min_quantity is not None else step
    notional=instrument.min_notional
    if notional is not None and str(notional.currency)!='USDC':return False
    floor_notional=notional.as_decimal() if notional is not None else Decimal(0)
    def supported(lots):
        value=Decimal(lots)*step
        return value>=minimum and value*price>=floor_notional
    lots=int(quantity/step)
    if not supported(lots) or not supported(lots//cut_divisor):return False
    remaining=lots
    fractions=tuple(Decimal(str(value)) for value in tp_fractions)
    for index,fraction in enumerate(fractions):
        if not fraction.is_finite() or not 0<=fraction<=1:return False
        # Exact canonical domain allocation: the last target owns the native
        # remainder when configured fractions sum1; no additional lot is added.
        part=remaining if index==len(fractions)-1 and sum(fractions)==1 else int(Decimal(lots)*fraction)
        if not part:continue
        if part>remaining or not supported(part):return False
        remaining-=part
        if remaining and not supported(remaining):return False
    return True
