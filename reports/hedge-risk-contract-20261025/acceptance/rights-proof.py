"""Pure normalization of externally evidenced actual native BTC release fills."""
from decimal import Decimal as D, InvalidOperation

def rights_proof(raw):
    out={'status':'UNKNOWN','actual_releases_semantics':'distinct native BTC release orders with positive actual fills; never grants, submits or acceptance','raw_counts':{k:raw.get(k,'UNKNOWN') for k in ['grants','submits','accepted','denials']}}
    if raw.get('status')!='PASS' or raw.get('native_fill_coverage_complete') is not True:
        out['reason']='Missing complete native fill/rights proof';return out
    fills=raw.get('native_release_fills')
    if not isinstance(fills,list):out['reason']='Missing native_release_fills list';return out
    unique={}
    try:
        for f in fills:
            if f.get('release_order') is not True or 'BTC' not in f['instrument_id']:
                raise ValueError('Not a proven BTC release fill')
            tid=f['native_trade_id'];oid=f['client_order_id'];qty=D(f['quantity'])
            if not isinstance(tid,str) or not tid or not isinstance(oid,str) or not oid or not qty.is_finite() or qty<=0:
                raise ValueError('Missing native fill identity or nonpositive quantity')
            value=(oid,qty,f['instrument_id'])
            if tid in unique and unique[tid]!=value:raise ValueError('Conflicting native trade ID')
            unique[tid]=value
        orders=sorted({v[0] for v in unique.values()})
        alias=raw.get('actual_releases')
        if alias is not None and (type(alias) is not int or alias!=len(orders)):
            raise ValueError('actual_releases must equal distinct positive-filled release orders')
    except (KeyError,TypeError,ValueError,InvalidOperation) as exc:
        out['reason']=str(exc);return out
    out.update(status='PASS',actual_releases=len(orders),positive_filled_release_orders=len(orders),positive_native_release_trade_count=len(unique),positive_native_release_BTC_quantity=str(sum((v[1] for v in unique.values()),D(0))),native_trade_ids=sorted(unique),client_order_ids=orders,native_fill_coverage_complete=True,economic_mechanism_tested=bool(orders))
    return out
