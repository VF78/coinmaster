from pathlib import Path
from decimal import Decimal as D
import json
from test_native_fixture import fixture_quotes
from coinmaster.research.native_fixture import build_engine,FundingInstruction,BTC_PERP,SOL_PERP,SIM
from coinmaster.ledger.journal import NativeEventJournal
r=Path(__file__).parent
db=r/'funding-persistence-final.sqlite'
assert not db.exists(),'FRESH_NAMESPACE_REQUIRED'
journal=NativeEventJournal(str(db))
events=(FundingInstruction('btc-positive',BTC_PERP.id,D('.01'),6,D('80999.5'),'synthetic_mid',True),FundingInstruction('sol-negative',SOL_PERP.id,D('-.01'),6,D('159.95'),'synthetic_mid',True),FundingInstruction('btc-positive',BTC_PERP.id,D('.01'),6,D('80999.5'),'synthetic_mid',True))
plain=build_engine();funded=build_engine(events,funding_journal=journal)
def cash(e):return e.cache.account_for_venue(SIM).balance_total().as_decimal()
snapshots=[]
try:
 quotes=fixture_quotes()
 for label,block in [('before_funding',[q for q in quotes if q.ts_event<=5]),('after_funding',[q for q in quotes if q.ts_event==6]),('after_later_native_closes',[q for q in quotes if q.ts_event>6])]:
  for e in (plain,funded):e.add_data(block);e.run(streaming=True);e.clear_data()
  a,b=cash(plain),cash(funded)
  snapshots.append(dict(boundary=label,baseline_native_cash=str(a),funded_native_cash=str(b),funding_delta=str(b-a),baseline_orders=len(plain.cache.orders()),funded_orders=len(funded.cache.orders()),funded_open_positions=len(funded.cache.positions_open()),journal_rows=len(journal.funding_audit())))
 assert D(snapshots[0]['funding_delta'])==0
 expected=-D('.6')*D('80999.5')*D('.01')-D(500)*D('159.95')*D('.01')
 assert expected==D('-1285.747')
 assert D(snapshots[1]['funding_delta'])==D(snapshots[2]['funding_delta'])==expected
 assert snapshots[2]['funded_open_positions']==0 and snapshots[2]['funded_orders']==5
 assert [x[0] for x in journal.funding_audit()]==['btc-positive','sol-negative']
 report=dict(status='PASS_NATIVE_FUNDING_PERSISTS_THROUGH_LATER_FILLS',after_engine_run_boundary='All snapshots taken after native run returns, outside callbacks; no cash reconstruction',expected_signed_delta=str(expected),snapshots=snapshots,journal='funding-persistence-final.sqlite',same_order_and_commission_path=([(o.instrument_id,o.side,o.quantity,o.filled_qty,o.avg_px,tuple(o.commissions())) for o in plain.cache.orders()]==[(o.instrument_id,o.side,o.quantity,o.filled_qty,o.avg_px,tuple(o.commissions())) for o in funded.cache.orders()]),scope='Small native fixture only; no market history/economic replay/S0result')
 assert report['same_order_and_commission_path']
 (r/'funding-persistence.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
finally:
 for e in (plain,funded):e.end();e.dispose()
 journal.close()

