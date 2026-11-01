"""Actual fill-audit callback to unchanged report consumers, supplied facts only.

No OrderFilled event, Engine or Strategy instance is fabricated/constructed.
"""
import ast,json
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace as N
import pytest
from coinmaster.strategy.cm2_native import CM2Strategy
from coinmaster.research.native_baseline import native_fee_attribution


class ID(str):venue='SYNTHETIC_VENUE'


def audit_adapter():
    btc=ID('SYNTHETIC_BTC')
    return N(config=N(btc_id=btc,sol_id=ID('SYNTHETIC_SOL'),execution_policy_hash='SYNTHETIC_SOURCE'),
        _seen_trade_ids=set(),_order_audit={'owned':{'purpose':'DRAIN','reason':'SUPPLIED_FACTS_ONLY',
            'parent_id':None,'level':None,'admission':None}},fill_audit=[],reference=N(parent=None),
        _liquidating=False,liquidation_audit=[],_chain_audit=lambda *a:None,
        _terminal_event=lambda *a,**kw:None,_persist_checkpoint=lambda:None)


def supplied_fill(f,identity,*,liquidity,quantity,price,commission):
    amount=lambda value:N(as_decimal=lambda:D(value))
    return N(trade_id=identity,client_order_id='owned',instrument_id=f.config.btc_id,
        last_qty=amount(quantity),last_px=amount(price),commission=N(as_decimal=lambda:D(commission),currency='USDC'),
        ts_event=100,liquidity_side=N(name=liquidity),order_side=N(name='SELL'))


def test_actual_callback_audit_notional_and_unchanged_native_fee_consumer():
    f=audit_adapter()
    inputs=[('maker','MAKER','2','100','.0288'),('taker','TAKER','.25','100.5','.010854'),
        ('unknown','UNOBSERVED','3','50','.01')]
    for identity,side,q,p,fee in inputs:
        event=supplied_fill(f,identity,liquidity=side,quantity=q,price=p,commission=fee)
        CM2Strategy.on_order_filled(f,event);CM2Strategy.on_order_filled(f,event)  # duplicate fact stays once
    assert len(f.fill_audit)==3
    assert [r['notional'] for r in f.fill_audit]==['200','25.125','150']
    total=sum((D(row['commission']) for row in f.fill_audit),D(0))
    attributed=native_fee_attribution(f.fill_audit,total)
    assert attributed['reconciled'] is True and D(attributed['audited_total'])==total
    assert attributed['maker']['count']==1 and attributed['taker']['count']==1 and attributed['unknown']['count']==1
    assert attributed['unknown']['fees']=='.01' or D(attributed['unknown']['fees'])==D('.01')
    assert f.fill_audit[2]['native_liquidity_side']=='UNOBSERVED'  # never relabeled taker/maker
    assert json.loads(json.dumps(f.fill_audit))==f.fill_audit
    with pytest.raises(ValueError,match='NATIVE_FEE_AUDIT_RECONCILIATION_MISMATCH'):
        native_fee_attribution(f.fill_audit,total+D('.00000001'))


def test_all_shared_baseline_adapter_and_fee_row_literal_fields_exist():
    source=Path(__file__).parents[1]/'coinmaster';native=ast.parse((source/'strategy/cm2_native.py').read_text())
    strategy=next(n for n in native.body if isinstance(n,ast.ClassDef) and n.name=='CM2Strategy')
    reporting=next(n for n in strategy.body if isinstance(n,ast.FunctionDef) and n.name=='reporting_state')
    returned=next(n.value.args[0] for n in reporting.body if isinstance(n,ast.Return))
    supplied={key.value for key in returned.keys if isinstance(key,ast.Constant)}
    baseline=ast.parse((source/'research/native_baseline.py').read_text())
    required={n.slice.value for n in ast.walk(baseline) if isinstance(n,ast.Subscript)
        and isinstance(n.value,ast.Name) and n.value.id=='adapter' and isinstance(n.slice,ast.Constant)}
    assert required<=supplied
    consumer=next(n for n in baseline.body if isinstance(n,ast.FunctionDef) and n.name=='native_fee_attribution')
    row_fields={n.slice.value for n in ast.walk(consumer) if isinstance(n,ast.Subscript)
        and isinstance(n.value,ast.Name) and n.value.id=='row' and isinstance(n.slice,ast.Constant)}
    f=audit_adapter();CM2Strategy.on_order_filled(f,supplied_fill(f,'schema',liquidity='UNKNOWN',quantity='1',price='10',commission='.01'))
    assert row_fields<=set(f.fill_audit[0])
    assert required=={'entry_sizing_audit','fill_audit','liquidation_lockout','liquidations','marked_equity_checkpoints',
        'pre_submit_tier_margin_gate_blocks','terminal_lifecycle','terminal_open_orders'}
