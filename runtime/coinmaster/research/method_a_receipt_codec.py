"""Read-only explicit codec for persisted CODE0 owner receipt metadata."""
from dataclasses import asdict
from nautilus_trader.model.enums import OrderSide
from coinmaster.strategy.method_a_risk import Features


def receipt_owner_values(owner):
    values=dict(owner)
    values['instrument']=str(values['instrument'])
    if 'code0_route' in values:
        if not isinstance(values['code0_route'],dict):raise TypeError('UNKNOWN_CODE0_RECEIPT_ROUTE')
        route=dict(values['code0_route'])
        if type(route.get('feature')) is not Features:raise TypeError('UNKNOWN_CODE0_RECEIPT_FEATURE')
        if type(route.get('side')) is not OrderSide or route['side'] not in (OrderSide.BUY,OrderSide.SELL):raise TypeError('UNKNOWN_CODE0_RECEIPT_SIDE')
        route['feature']=asdict(route['feature'])
        route['side']=route['side'].name
        values['code0_route']=route
    return values
