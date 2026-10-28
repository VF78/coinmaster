"""Read-only selected-field extraction. No engine, order matching, or PnL reconstruction."""
import csv, gzip, json, hashlib, sqlite3
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime, timezone
import pyarrow.parquet as pq

BASE=Path('/Users/vf/Documents/ChatGPT/Coinmaster')
M=BASE/'research-worktrees/btc-pattern-pilot-m2-20261021'
OUT=M/'reports/e4-c1-fast-pilot-20261028/evidence'
OLD=M/'reports/residual-recovery-20261023'
R=BASE/'runtime/var/research-jobs/residual-recovery-20261023/C1_CORRECTED/result'
J=next(R.glob('*-direction.json'))
DATA=BASE/'runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023/inputs/data/normalized'
doc=json.load(open(J)); audit=doc['c1_audit']
funding=sqlite3.connect('file:'+str(next(R.glob('*funding.sqlite')))+'?mode=ro',uri=True)
groups=list(csv.DictReader(open(OLD/'owner-C1-CORRECTED-groups.csv')))
actions=list(csv.DictReader(open(OLD/'owner-C1-CORRECTED-actions.csv')))
H4=14400000000000; MIN=60000000000
def ns(s):return int(datetime.fromisoformat(s).timestamp())*1000000000
def utc(n):return datetime.fromtimestamp(n/1e9,timezone.utc).isoformat()
def ev(g,name,kind=None):return next((e for e in audit if e.get('group')==g and e['event']==name and (kind is None or e.get('kind')==kind)),None)
def write(name,rows):
    if not rows:return
    with open(OUT/name,'w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
wanted=set();windows=[]
for g in groups:
    ident=g['group'];cut=ev(ident,'ATTEMPT_SUBMIT','CUT');term=ev(ident,'ATTEMPT_TERMINAL','CUT');fill=ev(ident,'ACTUAL_FILL','CUT')
    restore=ev(ident,'ATTEMPT_SUBMIT','RESTORE');revoke=ev(ident,'TOKEN_REVOKED')
    end=(restore or revoke)['timestamp_ns']
    bars=list(range((fill['timestamp_ns']//H4+1)*H4,end+1,H4))
    windows.append(dict(g=g,cut=cut,term=term,fill=fill,restore=restore,revoke=revoke,end=end,bars=bars))
    wanted.add(cut['timestamp_ns'])
    for t in bars:
        wanted.update((t-MIN,t,t+MIN,t+2*MIN))
receipts={};peak=D(10000);count=0;months=set()
with gzip.open(R/'minute-native-settled-receipts.csv.gz','rt') as f:
    for r in csv.DictReader(f):
        count+=1;t=int(r['receipt_ns']);e=D(r['paired_close_equity']);peak=max(peak,e);months.add(utc(int(r['source_quote_ns']))[:7])
        if t in wanted:
            receipts[t]={k:r[k] for k in ('source_quote_ns','receipt_ns','fill_epoch','cash','paired_close_equity')}
            receipts[t].update(H=str(peak),DD=str(1-e/peak))
times={int(t//1000000-60000) for t in wanted}
execution={}
for symbol in ('BTCUSDT','SOLUSDT'):
    table=pq.read_table(DATA/f'bybit-{symbol}-execution-1m.parquet',columns=['open_time_ms','close'],filters=[('open_time_ms','in',sorted(times))])
    execution[symbol]={int(x['open_time_ms']):x['close'] for x in table.to_pylist()}
rows=[];decisions=[];confirm_checks=[]
for w in windows:
    g=w['g'];symbol=g['instrument'].split('-')[0];side=int(g['side']);vwap=D(g['cut_VWAP']);earlier=[];potential=[]
    for t in w['bars']:
        c=receipts.get(t);close=execution[symbol].get(t//1000000-60000);r=D(close) if close else None
        complete=t-H4>max(w['fill']['timestamp_ns'],w['term']['timestamp_ns'])
        reclaim=r is not None and side*(r-vwap)>0
        dd35=c is not None and D(c['DD'])<=D('.35');dd40=c is not None and D(c['DD'])<=D('.40')
        actual=next((a for a in audit if a['event']=='CLOSED_4H_RECLAIM' and a.get('group')==g['group'] and a['timestamp_ns']==t),None)
        if actual:confirm_checks.append(dict(index=g['index'],timestamp_ns=t,native_DD=actual['DD'],extracted_DD=c['DD'],native_close=actual['close'],extracted_close=close,exact_DD=actual['DD']==c['DD'],exact_close=D(actual['close'])==r))
        quote=[]
        for qt in (t+MIN,t+2*MIN):
            qc=receipts.get(qt);px=execution[symbol].get(qt//1000000-60000)
            quote.append(dict(timestamp_ns=qt,utc=utc(qt),checkpoint=qc,raw_execution_close=px,price_reclaim=(side*(D(px)-vwap)>0) if px else None,DD35=(D(qc['DD'])<=D('.35')) if qc else None,DD40=(D(qc['DD'])<=D('.40')) if qc else None))
        ronly=complete and reclaim and dd40 and not dd35
        funding_at_bar=funding.execute('select instrument_id,ts_event from funding_events where ts_event=?',(t,)).fetchall()
        if ronly and t<w['end']:earlier.append(t)
        if complete and reclaim and dd40 and t<w['end']:potential.append(t)
        blockers=[]
        if not complete:blockers.append('BAR_NOT_ENTIRELY_AFTER_LAST_CUT_FILL_AND_TERMINAL')
        if not reclaim:blockers.append('NO_CUT_VWAP_RECLAIM')
        if c is None:blockers.append('CHECKPOINT_MISSING')
        elif not dd40:blockers.append('DD_ABOVE_40')
        elif not dd35:blockers.append('DD35_ONLY_BLOCKER_OBSERVED')
        if t>=w['end']:blockers.append('RESTORE_OR_REVOCATION_ENDPOINT_PRIORITY')
        if funding_at_bar:blockers.append('FUNDING_ACCOUNT_MUTATION_ORDER_NEEDS_CURRENT_MONEY_PROOF')
        rows.append(dict(index=g['index'],group=g['group'],h4_close_utc=utc(t),h4_open_utc=utc(t-H4),after_cut_terminal_and_last_fill=complete,execution_close=close,cut_vwap=str(vwap),signed_reclaim=reclaim,checkpoint_E=c['paired_close_equity'] if c else 'UNKNOWN',checkpoint_cash=c['cash'] if c else 'UNKNOWN',checkpoint_H=c['H'] if c else 'UNKNOWN',checkpoint_DD=c['DD'] if c else 'UNKNOWN',DD35=dd35,DD40=dd40,threshold_only_candidate=ronly,actual_CLOSED_4H_RECLAIM=bool(actual),blockers=';'.join(blockers),fresh_quote_evidence=json.dumps(quote,separators=(',',':')),owner_ACK_margin_ordinary_priority='PROVEN_NATIVE_SUBMIT' if actual else 'UNKNOWN_NOT_LOGGED_WHEN_BAR_REJECTED'))
    cut=w['cut'];claim=ev(g['group'],'CLAIM');restore=w['restore']
    pair=D(g['matched_cut_restore_native_cashflow_ex_fees']) if g['matched_cut_restore_native_cashflow_ex_fees'] else None
    fees=D(g['cut_fee'])+D(g['restore_fee'])
    # Normalization only of actual observed intervention costs, no alternate equity path.
    decisions.append(dict(index=g['index'],group=g['group'],instrument=g['instrument'],claim_utc=g['claim_utc'],cut_utc=utc(w['fill']['timestamp_ns']),cut_terminal_utc=utc(w['term']['timestamp_ns']),window_end_utc=utc(w['end']),window_end_kind='RESTORE' if restore else 'REVOKE',held_lots=claim['frozen_held_lots'],requested_cut_lots=cut['lots'],actual_cut_lots=w['fill']['lots'],step=cut['step'],actual_cut_quantity=g['actual_cut_quantity'],actual_cut_vwap=g['cut_VWAP'],actual_cut_fee=g['cut_fee'],cut_checkpoint_cash=receipts[cut['timestamp_ns']]['cash'],cut_E=cut['E'],cut_H=cut['H'],cut_DD=cut['DD'],cut_source_ns=cut['source_quote_ns'],cut_receipt_ns=cut['receipt_ns'],actual_restore_quantity=g['restored_quantity'],actual_restore_vwap=g['restore_VWAP'],actual_restore_fee=g['restore_fee'],actual_pair_gap_cashflow=g['matched_cut_restore_native_cashflow_ex_fees'],actual_intervention_fees=str(fees),pair_gap_cost_over_cut_E=str(-pair/D(cut['E'])) if pair is not None else '',fees_over_cut_E=str(fees/D(cut['E'])),revocation_reason=g['revocation_reasons'],h4_rows=len(w['bars']),DD40_only_candidate_count=len(earlier),DD40_only_first_utc=utc(earlier[0]) if earlier else '',R_reachability='UNKNOWN_ADMISSION_AT_EARLIER_THRESHOLD_CANDIDATE' if earlier else 'NO_ACTION_DELTA_PRICE_DD_SCREEN',screen_scope='ALL_H4_THROUGH_RESTORE_OR_REVOKE;PRICE_DD_ONLY;OWNER_ACK_MARGIN_UNKNOWN_UNLESS_NATIVE_SUBMIT',later_signed_unit_path=g['unit_later_exit_minus_cut_signed'],G_global35_saved_path='KEEP_FIRST_AUGUST' if int(g['index'])==5 else ('SUPPRESS_SAVED_PATH_NO35_REARM' if int(g['index'])>5 else 'OTHER_PERIOD_NOT_INFERRED')))
for r in rows:
    t=ns(r['h4_close_utc'])
    r['actual_funding_postings_at_H4']=json.dumps(funding.execute('select instrument_id,ts_event from funding_events where ts_event=?',(t,)).fetchall())
    q=json.loads(r['fresh_quote_evidence'])
    r['quote_only_DD35_to40_crossing']=r['DD35'] and any(x['DD40'] and not x['DD35'] for x in q)
for r in decisions:
    if r['DD40_only_candidate_count']:r['R_reachability']='UNKNOWN_CURRENT_MONEY_OWNER_ADMISSION_AT_EARLIER_THRESHOLD_CANDIDATE'
write('h4_restore_windows.csv',rows);write('e4_c1_decisions.csv',decisions);write('successful_confirmation_crosscheck.csv',confirm_checks)
selected=[{k:v for k,v in e.items() if k not in ('rights','rights_before','rights_after','positions')} for e in audit]
(OUT/'native_c1_selected_audit.json').write_text(json.dumps(selected,indent=2))
(OUT/'extraction_summary.json').write_text(json.dumps(dict(native_receipts_streamed=count,source_months=sorted(months),groups=len(groups),h4_rows=len(rows),confirmation_crosschecks=confirm_checks,price_DD_only_no_action=sum(x['R_reachability'].startswith('NO_ACTION') for x in decisions),threshold_candidate_groups=[x['index'] for x in decisions if x['DD40_only_candidate_count']],engine_runs=0,new_matching_or_PnL_engine=False,coherent_event_DD_status='UNKNOWN: minute phased close samples exist; fill-by-fill pre-fill/pre-open equity not proven',signed_asset_funding=doc['funding'],cash_bridge_not_funding='53801.142665296518712',C1_source='78cb85aca1cf5c2e4455f5c5ddf02851cfb40076',E4_source='bd04c9b3858bcda40060a08eff488849c69af5d8',data_hash=doc['data_hash'],policy_hash=doc['policy_hash'],config_hash=doc['config_hash']),indent=2))
pins={}
for p in [J,R/'minute-native-settled-receipts.csv.gz',R/'minute-native-risk.csv.gz',*OLD.glob('owner-C1-CORRECTED-*.csv'),OLD/'owner-C1-CORRECTED-postmortem.json',*(DATA/f'bybit-{s}-execution-1m.parquet' for s in ('BTCUSDT','SOLUSDT'))]:
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    pins[str(p)]=h.hexdigest()
(OUT/'input_hashes.json').write_text(json.dumps(pins,indent=2))
print(json.dumps(dict(groups=len(groups),h4_rows=len(rows),threshold_candidates=[(x['index'],x['DD40_only_candidate_count'],x['DD40_only_first_utc']) for x in decisions],confirmation_checks=confirm_checks),indent=2))
