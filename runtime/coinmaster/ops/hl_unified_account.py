"""Bounded USDC-only Unified projection, public venue facts, no PnL/cash posting."""
from decimal import Decimal,InvalidOperation
from coinmaster.ops.hl_info_receipt import IncompleteInfoReport

UNIFIED='unifiedAccount'
EQUITY_BASIS='HYPERLIQUID_UNIFIED_SPOT_USDC_REPORTED_TOTAL_V1'
HOLD_BASIS='HYPERLIQUID_SPOT_USDC_HOLD_PROXY_NOT_LIQUIDATION_MM_V1'


def amount(value):
    try:result=Decimal(str(value))
    except (InvalidOperation,ValueError,TypeError):raise IncompleteInfoReport('UNIFIED_BALANCE_MALFORMED') from None
    if not result.is_finite():raise IncompleteInfoReport('UNIFIED_BALANCE_NONFINITE')
    return result


def spot_usdc(raw):
    if not isinstance(raw,dict) or not isinstance(raw.get('balances'),list):raise IncompleteInfoReport('UNIFIED_SPOT_BALANCES_MISSING')
    seen=set();total=hold=Decimal(0)
    for row in raw['balances']:
        if not isinstance(row,dict) or not isinstance(row.get('coin'),str) or row['coin'] in seen:raise IncompleteInfoReport('UNIFIED_SPOT_DUPLICATE_OR_MALFORMED')
        seen.add(row['coin']);value=amount(row.get('total'));locked=amount(row.get('hold'))
        if not 0<=locked<=value:raise IncompleteInfoReport('UNIFIED_SPOT_HOLD_INVALID')
        if row['coin']=='USDC':total,hold=value,locked
        elif value or locked:raise IncompleteInfoReport('UNIFIED_OTHER_COLLATERAL_UNSUPPORTED')
    return total,hold,total-hold


def native_spot_usdc_dicts(native_balances):
    """Decode stock request_spot_balances objects; zero clears prior cache facts."""
    seen=set();selected=None
    if not isinstance(native_balances,(list,tuple)):raise IncompleteInfoReport('UNIFIED_NATIVE_BALANCES_MALFORMED')
    for native in native_balances:
        row=native.to_dict()
        if not isinstance(row,dict) or not isinstance(row.get('currency'),str) or row['currency'] in seen:raise IncompleteInfoReport('UNIFIED_NATIVE_DUPLICATE_BALANCE')
        seen.add(row['currency']);total=amount(row.get('total'));hold=amount(row.get('locked'));free=amount(row.get('free'))
        if not 0<=hold<=total or free!=total-hold:raise IncompleteInfoReport('UNIFIED_NATIVE_BALANCE_IDENTITY')
        if row['currency']=='USDC':selected=dict(currency='USDC',total=str(total),locked=str(hold),free=str(free))
        elif total or hold or free:raise IncompleteInfoReport('UNIFIED_NATIVE_OTHER_COLLATERAL')
    selected=selected or dict(currency='USDC',total='0',locked='0',free='0')
    margin=dict(currency='USDC',initial=selected['locked'],maintenance=selected['locked'],instrument_id=None)
    return selected,margin


def default_dex_state(raw):
    if not isinstance(raw,list) or not raw:raise IncompleteInfoReport('UNIFIED_ALL_DEX_STATES_MISSING')
    seen=set();default=None
    for item in raw:
        if not isinstance(item,(list,tuple)) or len(item)!=2 or not isinstance(item[0],str) or item[0] in seen:raise IncompleteInfoReport('UNIFIED_DEX_STATE_MALFORMED')
        dex,state=item;seen.add(dex)
        if not isinstance(state,dict) or not isinstance(state.get('assetPositions'),list):raise IncompleteInfoReport('UNIFIED_DEX_POSITION_SET_UNKNOWN')
        for row in state['assetPositions']:
            position=row.get('position') if isinstance(row,dict) else None
            if not isinstance(position,dict):raise IncompleteInfoReport('UNIFIED_POSITION_MALFORMED')
            size=amount(position.get('szi'))
            if size and (dex or position.get('coin') not in ('BTC','SOL')):raise IncompleteInfoReport('UNIFIED_FOREIGN_DEX_EXPOSURE')
            if size and position.get('leverage',{}).get('type')!='cross':raise IncompleteInfoReport('UNIFIED_ISOLATED_EXPOSURE')
        if not dex:default=state
    if default is None:raise IncompleteInfoReport('UNIFIED_DEFAULT_DEX_MISSING')
    return default


def native_unified_money(raw_spot,all_dex,*,native_account,native_positions,account_id,strategy_id=None):
    total,hold,free=spot_usdc(raw_spot);state=default_dex_state(all_dex)
    if native_account is None or str(native_account.id)!=account_id or native_account.base_currency is not None:raise IncompleteInfoReport('UNIFIED_NATIVE_ACCOUNT_SCOPE')
    expected={}
    for row in state['assetPositions']:
        pos=row['position'];size=amount(pos['szi'])
        if not size:continue
        coin=pos['coin']
        if coin in expected:raise IncompleteInfoReport('UNIFIED_POSITION_DUPLICATE')
        expected[coin]=size
    actual={}
    for pos in native_positions:
        coin=str(pos.instrument_id).split('-USD-PERP.')[0]
        if coin not in ('BTC','SOL') or coin in actual or str(pos.account_id)!=account_id or (strategy_id is not None and str(pos.strategy_id)!=strategy_id):raise IncompleteInfoReport('UNIFIED_NATIVE_POSITION_SCOPE')
        actual[coin]=pos.quantity.as_decimal()*(1 if pos.is_long else -1)
    if expected!=actual:raise IncompleteInfoReport('UNIFIED_NATIVE_POSITION_MISMATCH')
    return total,hold,free,tuple(sorted(actual.items()))
