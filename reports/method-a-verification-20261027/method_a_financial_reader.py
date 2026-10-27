"""Stdlib-only Method-A native artifact reader. No engine or inferred PnL.

Decimal50 ES20/daily/parent/coherent/funding blocks retain metricca815 semantics.
Native PositionClosed.realized_pnl is NET settlement-currency commissions.
Cash residual default is strict zero; nonzero is UNKNOWN, never funding.
"""
from pathlib import Path
from decimal import Decimal as D,getcontext
from datetime import datetime,timezone,timedelta
from collections import Counter
from tempfile import TemporaryDirectory
import argparse,csv,gzip,json,sqlite3
import prefix_common as c
from method_a_financial_binding import bind
getcontext().prec=50
TERMINAL={'FILLED','CANCELED','EXPIRED','REJECTED','DENIED'}


def es(losses):
    if not losses:return None
    s=sorted(losses,reverse=True);q=D(len(s))/5;k=int(q);f=q-k
    return str((sum(s[:k],D(0))+(f*s[k] if f else D(0)))/q)


def native_cash_residual(terminal,native_realized_net_fees,signed_native_funding):
    return D(terminal)-D(10000)-D(native_realized_net_fees)-D(signed_native_funding)


def money(value):
    amount,currency=value.rsplit(' ',1)
    return D(amount.replace('_','')),currency


def insert_unique(db,table,key,body,issues):
    encoded=json.dumps(body,sort_keys=True,separators=(',',':'))
    old=db.execute('SELECT body FROM '+table+' WHERE id=?',(key,)).fetchone()
    if old:
        if old[0]!=encoded:issues['conflicting_'+table]+=1
        return False
    db.execute('INSERT INTO '+table+' VALUES (?,?)',(key,encoded));return True


def profile_read(path,db,owners,label):
    bad=Counter();counts=Counter();last=None;state_hash=None;seq=0;quote_frames=0;checked_tp=0;first_cash=None
    for table in ('fills','closed','position_trades','order_context'):
        db.execute('CREATE TABLE '+table+' (id TEXT PRIMARY KEY,body TEXT NOT NULL)')
    db.execute('CREATE TABLE quotes (ns INTEGER,instrument TEXT,PRIMARY KEY(ns,instrument))')
    db.execute('CREATE TABLE parent_actual (id TEXT PRIMARY KEY,entry TEXT,tp0 TEXT,tp1 TEXT,tp2 TEXT)')
    for line in gzip.open(path,'rt'):
        row=json.loads(line);seq+=1;phase=row['phase'];counts[phase]+=1
        if row['sequence']!=seq:bad['profile_sequence_gap']+=1
        if 'state' in row:
            state=row['state']
            # Producer uses default ensure_ascii=True; native identities/fields
            # are ASCII. Recompute its exact serialization regardless.
            import hashlib
            digest=hashlib.sha256(json.dumps(state,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
            if digest!=row['state_sha256']:bad['profile_state_hash']+=1
            last=state;state_hash=digest
            if state is not None:
                if first_cash is None and state['native_cash'] is not None:first_cash=money(state['native_cash'])
                for oid,context in state['owned_pending'].items():insert_unique(db,'order_context',oid,context,bad)
        elif row.get('state_ref_sha256')!=state_hash or row['state_sha256']!=state_hash:bad['profile_state_reference']+=1
        state=last
        if state is None:
            bad['profile_state_missing']+=1;continue
        for oid,order in state['active_orders'].items():
            if oid not in owners:bad['unmapped_native_active_order']+=1
            if not order['strategy']:bad['native_strategy_missing']+=1
        if phase=='BEFORE_NATIVE_MATCHING_INPUT':
            quote_frames+=1;tick=row['input'];ns=int(tick['event_ns'])
            if ns!=int(row['event_ns']):bad['quote_clock_binding']+=1
            db.execute('INSERT OR IGNORE INTO quotes VALUES (?,?)',(ns,tick['instrument']))
            if label=='P1':
                positions=[x for x in state['positions'] if x['instrument'].startswith('BTCUSDT-PERP.')]
                if len(positions)>1:bad['multiple_native_BTC_positions']+=1
                held=sum((D(x['quantity']) for x in positions),D(0));ep=state['episode'];ma=state['method_a']
                if held:
                    checked_tp+=1
                    if ep is None or ma is None:bad['P1_missing_native_TP_state']+=1;continue
                    entry=D(ep['entry_qty_exact'])/D('.001')
                    if entry!=entry.to_integral_value():bad['P1_noninteger_entry']+=1;continue
                    n=int(entry);first=n*17//80;two=n*17//40;grants={0:first,1:two-first,2:n-two}
                    actual_grants={int(k):v for k,v in ep['target_lots'].items()}
                    filled={int(k):v for k,v in ep['actual_tp_filled_lots'].items()};retired={int(k):v for k,v in ep['risk_retired_lots'].items()}
                    desired={i:grants[i]-filled.get(i,0)-retired.get(i,0) for i in range(3)}
                    if actual_grants!=grants or any(v<0 for v in desired.values()) or D(sum(desired.values()))*D('.001')!=held:bad['P1_grant_inventory_conservation']+=1
                    actual={}
                    for oid,owner in state['method_a_active_owners'].items():
                        if owner['parent']!=ep['id']:continue
                        order=state['active_orders'].get(oid)
                        if order is None:bad['P1_owner_order_missing']+=1;continue
                        level=int(owner['level'])
                        if level in actual:bad['P1_duplicate_target_owner']+=1
                        if order['status'] not in ('ACCEPTED','PARTIALLY_FILLED') or not order['reduce_only'] or not owner['ack'] or oid in state['method_a_commands']:bad['P1_actual_latest_ACK_missing']+=1
                        actual[level]=D(order['leaves'])/D('.001')
                    if actual!={i:D(v) for i,v in desired.items() if v>0} or ma['coverage_ready'] is not True or ma['expected_cancels']:bad['P1_actual_TP_coverage']+=1
                    observed=db.execute('SELECT entry,tp0,tp1,tp2 FROM parent_actual WHERE id=?',(ep['id'],)).fetchone()
                    if observed is None or D(observed[0])!=D(ep['entry_qty_exact']):bad['P1_actual_entry_grant_source']+=1
                    if observed is not None and any(D(observed[i+1])!=D(filled.get(i,0))*D('.001') for i in range(3)):bad['P1_actual_TP_consumption_source']+=1
        if phase=='AFTER_STRATEGY_on_order_filled' and row['native_event_type']=='OrderFilled':
            oid=row['client_order_id'];context=db.execute('SELECT body FROM order_context WHERE id=?',(oid,)).fetchone()
            context=json.loads(context[0]) if context else {};raw=owners.get(oid,{})
            action=context.get('action',raw.get('action'));parent=context.get('parent');level=context.get('level',raw.get('level'))
            commission,currency=money(row['commission'])
            value=dict(native_event_id=row['native_event_id'],oid=oid,parent=parent,action=action,level=level,qty=row['last_qty'],
                commission=str(commission),currency=currency,ns=row['event_ns'])
            fresh=insert_unique(db,'fills',row['trade_id'],value,bad)
            if fresh and parent is not None and action in ('BTC_ENTRY','BTC_REDUCE'):
                db.execute('INSERT OR IGNORE INTO parent_actual VALUES (?,?,?,?,?)',(parent,'0','0','0','0'))
                column='entry' if action=='BTC_ENTRY' else 'tp'+str(level)
                if column not in ('entry','tp0','tp1','tp2'):bad['native_TP_level_unknown']+=1
                else:
                    old=db.execute('SELECT '+column+' FROM parent_actual WHERE id=?',(parent,)).fetchone()[0]
                    db.execute('UPDATE parent_actual SET '+column+'=? WHERE id=?',(str(D(old)+D(row['last_qty'])),parent))
            if action in ('BTC_ENTRY','BTC_REDUCE','SOL_ADD') and parent is None:bad['fill_parent_owner_missing']+=1
            if action=='SOL_ADD' and level not in (None,''):
                ep=state['episode']
                if ep is None or int(level) not in ep['old_SOL_rights']:bad['old_SOL_right_not_observed']+=1
        if phase=='AFTER_STRATEGY_on_position_event' and row['native_event_type']=='PositionClosed':
            event=row.get('native_position_closed_event');position=row.get('native_position')
            if event is None or position is None or not position['is_closed'] or event['realized_pnl'] is None:
                bad['closed_native_position_evidence_missing']+=1;continue
            if event['realized_pnl']!=position['realized_pnl']:bad['closed_native_event_cache_money_conflict']+=1
            value=dict(position_id=event['position_id'],realized=event['realized_pnl'],commissions=position['commissions'])
            if insert_unique(db,'closed',row['native_event_id'],value,bad):
                for fill in position['native_fill_history']:
                    insert_unique(db,'position_trades',fill['trade_id'],dict(closed_event=row['native_event_id'],native_event_id=fill['event_id'],oid=fill['client_order_id'],qty=fill['qty'],commission=fill['commission']),bad)
    interior=db.execute('SELECT instrument,COUNT(*),MIN(ns),MAX(ns) FROM quotes WHERE ns>? AND ns<? GROUP BY instrument',(c.START*10**6,c.END*10**6)).fetchall()
    universe=len(interior)==2 and all(count==195839 and first==1725148860000000000 and last==1736899140000000000 for _,count,first,last in interior)
    return dict(issues=dict(bad),complete_interior_quote_universe=universe,interior_quotes=interior,phase_counts=dict(counts),frames=seq,quote_frames=quote_frames,checked_P1_held_frames=checked_tp,first_native_cash=first_cash,last_state=last)


def analyze(bound):
    a=bound['report'];o=a['coherent_native_observer'];label=bound['gate']['label'];roles=bound['roles'];extras=bound['extras']
    orders=list(csv.DictReader(roles['orders'].open()));raw=json.loads(extras['raw_native'].read_text());owners=raw['native_order_events']
    parents=sorted(a['split_cover_audit']['parents'],key=lambda x:int(x['start_ns']));cycles=[]
    for i,v in enumerate(parents):
        st=int(v['start_ns']);nxt=int(parents[i+1]['start_ns']) if i+1<len(parents) else 10**30
        oo=[x for x in orders if st<=int(x['ts_init'])<nxt];cutoff=max([int(x['ts_last']) for x in oo]+[st])
        cycles.append(dict(episode_id=v['episode_id'],start_ns=st,next_start_ns=nxt,closed=v['closed'],orders_terminal=all(x['status'] in TERMINAL for x in oo),order_quiescence_ns=cutoff,start=None,end=None))
    with TemporaryDirectory(prefix='method-a-financial-links-',dir=bound['output'].parent) as directory:
        db=sqlite3.connect(str(Path(directory)/'native-links.sqlite'))
        profile=profile_read(extras['protection_profile'],db,owners,label)
        db.execute('CREATE TABLE coherent_fill (id TEXT PRIMARY KEY,pre INTEGER,post INTEGER)')
        db.execute('CREATE TABLE funding_pre (id TEXT PRIMARY KEY,cash TEXT)')
        funding=[];daily={};n=0;terminalrow=None;bad=Counter();prevseq=0;last_epoch=0;kinds=Counter();last_settled_ns=None;first_settled_ns=None;settled_gaps=0
        peaks={'settled':D(10000),'event':D(10000)};dds={'settled':D(0),'event':D(0)}
        for line in gzip.open(roles['coherent'],'rt'):
            r=json.loads(line);n+=1;k=r['kind'];kinds[k]+=1;ns=int(r['event_ns']);eq=r['equity'];pos=r['positions']
            if r['sequence']!=prevseq+1:bad['sequence_gap']+=1
            prevseq=r['sequence']
            if r['epoch']<last_epoch or r['epoch']>last_epoch+1:bad['epoch_gap']+=1
            last_epoch=r['epoch']
            if k in ('PRE_FILL_LAST_COMMITTED_NATIVE_COPY','POST_FILL_COMMITTED_NATIVE'):
                db.execute('INSERT OR IGNORE INTO coherent_fill VALUES (?,0,0)',(r['native_id'],))
                db.execute('UPDATE coherent_fill SET '+('pre' if k.startswith('PRE_') else 'post')+'=1 WHERE id=?',(r['native_id'],))
            if eq is not None:
                bucket='settled' if k=='SETTLED_PRE_NEXT_SOURCE_WATERMARK' else 'event';value=D(eq);peaks[bucket]=max(peaks[bucket],value);dds[bucket]=max(dds[bucket],(1-value/peaks[bucket])*100)
            if eq is None:bad['missing_equity']+=1
            elif D(eq)!=D(r['cash'])+sum((D(x['native_upnl']) for x in pos),D(0)):bad['cash_upnl_bridge']+=1
            if k=='SETTLED_PRE_NEXT_SOURCE_WATERMARK':
                if last_settled_ns is not None and ns-last_settled_ns!=60000000000:settled_gaps+=1
                last_settled_ns=ns
                if first_settled_ns is None:first_settled_ns=ns
                retention=r.get('prior_source_retention')
                if retention and (int(retention['source_ns'])!=ns or retention['state_epoch']!=r['state_epoch'] or int(retention['first_new_mutation_ns'])<=ns):bad['retention_proof']+=1
                day=datetime.fromtimestamp(ns//10**9,timezone.utc).date().isoformat()
                if '2024-09-01'<=day<='2025-01-14' and (day not in daily or ns>daily[day]['source_ns']):daily[day]=dict(source_ns=ns,equity=eq,sequence=r['sequence'])
            if k=='DIRECT_NATIVE_AFTER_ENGINE_END_RETURNED':terminalrow=r
            if k=='PRE_FUNDING_COMMITTED_NATIVE_COPY':db.execute('INSERT OR REPLACE INTO funding_pre VALUES (?,?)',(r['native_id'],r['cash']))
            if k=='POST_FUNDING_ACCOUNT_NATIVE':
                before=db.execute('SELECT cash FROM funding_pre WHERE id=?',(r['native_id'],)).fetchone();funding.append((r['native_id'],None if before is None else before[0],r['cash']))
            for cycle in cycles:
                if k=='PRE_FILL_LAST_COMMITTED_NATIVE_COPY' and ns==cycle['start_ns'] and cycle['start'] is None and not any('BTC' in x['instrument_id'] for x in pos):cycle['start']=dict(equity=eq,sequence=r['sequence'],event_ns=ns)
                if cycle['start'] and cycle['end'] is None and cycle['orders_terminal'] and cycle['closed'] and ns>=cycle['order_quiescence_ns'] and ns<=cycle['next_start_ns'] and not pos and r['sequence']>cycle['start']['sequence']:cycle['end']=dict(equity=eq,sequence=r['sequence'],event_ns=ns)
        endday='2025-01-14';target=int(datetime(2025,1,14,23,59,tzinfo=timezone.utc).timestamp()*10**9)
        if endday not in daily or daily[endday]['source_ns']<target:
            if terminalrow and not terminalrow['positions'] and all(x['status'] in TERMINAL for x in orders) and a['terminal_open_positions']==0 and o['status']=='PASS' and D(terminalrow['cash'])==D(a['terminal_total']):daily[endday]=dict(source_ns=None,equity=terminalrow['cash'],sequence=terminalrow['sequence'],basis='VALIDATED_DIRECT_TERMINAL_NATIVE_CASH_FLAT_ORDERS0')
        seed=D(10000);dreturns=[];missing=[]
        for i in range(136):
            day=(datetime(2024,9,1)+timedelta(days=i)).date().isoformat()
            if day not in daily:missing.append(day);continue
            if seed<=0:missing.append(day+':nonpositive_start');continue
            value=D(daily[day]['equity']);loss=1-value/seed;dreturns.append(dict(date=day,start=str(seed),end=str(value),loss=str(loss),**daily[day]));seed=value
        pl=[]
        for cycle in cycles:
            if cycle['start'] and cycle['end'] and D(cycle['start']['equity'])>0:cycle['loss']=str(1-D(cycle['end']['equity'])/D(cycle['start']['equity']));pl.append(D(cycle['loss']))
        funding_db=sqlite3.connect('file:'+str(roles['funding'].resolve())+'?mode=ro&immutable=1',uri=True)
        frows=funding_db.execute('select event_id,instrument_id,ts_event,before_total,after_total,signed_delta from funding_cash').fetchall();funding_db.close()
        fdb={x[0]:x for x in frows};fproof=all(e in fdb and before==fdb[e][3] and after==fdb[e][4] and D(after)-D(before)==D(fdb[e][5]) for e,before,after in funding) and len(funding)==len(frows)==a['funding']['count']
        signed=sum((D(x[5]) for x in frows),D(0));fees=sum((D(x['commission']) for x in a['fill_audit']),D(0))
        fill_count=db.execute('SELECT COUNT(*) FROM fills').fetchone()[0];closed_count=db.execute('SELECT COUNT(*) FROM closed').fetchone()[0]
        native_realized=sum((D(json.loads(x[0])['realized']['amount']) for x in db.execute('SELECT body FROM closed')),D(0))
        fill_fees=sum((D(json.loads(x[0])['commission']) for x in db.execute('SELECT body FROM fills')),D(0))
        currencies_ok=all(json.loads(x[0])['currency']=='USDT' for x in db.execute('SELECT body FROM fills')) and all(json.loads(x[0])['realized']['currency']=='USDT' for x in db.execute('SELECT body FROM closed'))
        history_conflicts=0
        for actual,history in db.execute('SELECT f.body,p.body FROM fills f JOIN position_trades p ON f.id=p.id'):
            actual=json.loads(actual);history=json.loads(history)
            if actual['native_event_id']!=history['native_event_id'] or actual['oid']!=history['oid'] or D(actual['qty'])!=D(history['qty']) or D(actual['commission'])!=D(history['commission']['amount']) or actual['currency']!=history['commission']['currency']:history_conflicts+=1
        history_count=db.execute('SELECT COUNT(*) FROM position_trades').fetchone()[0]
        missing_history=db.execute('SELECT COUNT(*) FROM fills WHERE id NOT IN (SELECT id FROM position_trades)').fetchone()[0]
        extra_history=db.execute('SELECT COUNT(*) FROM position_trades WHERE id NOT IN (SELECT id FROM fills)').fetchone()[0]
        coherent_count=db.execute('SELECT COUNT(*) FROM coherent_fill WHERE pre=1 AND post=1').fetchone()[0]
        unpaired=db.execute('SELECT COUNT(*) FROM coherent_fill WHERE pre=0 OR post=0').fetchone()[0]
        unmatched=db.execute('SELECT COUNT(*) FROM fills WHERE id NOT IN (SELECT id FROM coherent_fill)').fetchone()[0]
        residual=native_cash_residual(a['terminal_total'],native_realized,signed)
        first_cash=profile['first_native_cash'];last=profile['last_state']
        cashproof=(first_cash==(D(10000),'USDT') and fill_count==a['fills']==len(a['fill_audit']) and history_count==fill_count and missing_history==extra_history==0
            and currencies_ok and history_conflicts==0
            and fees==fill_fees==D(a['native_fees']) and residual==0 and a['transfers']=='0' and D(a['terminal_reserve'])==0)
        terminal=(a['terminal_open_positions']==0 and all(x['status'] in TERMINAL for x in orders) and bool(terminalrow) and not terminalrow['positions']
            and last is not None and not last['positions'] and not last['active_orders'] and not last['owned_pending'] and not last['method_a_commands'])
        registration=bound['profile']['actual_venue_registrations']
        venue=(len(registration)==1 and registration[0]['liquidity_consumption'] is False and registration[0]['bar_execution'] is True and 'CommittedNativeObserver' in registration[0]['modules_before_observer'])
        complete_range=(first_settled_ns==1725148860000000000 and last_settled_ns==1736899140000000000 and kinds['SETTLED_PRE_NEXT_SOURCE_WATERMARK']==195839
            and a['streaming']['processed_rows_per_source']==a['streaming']['expected_rows_per_source']==195840 and not settled_gaps and len(dreturns)==136 and not missing)
        native_epochs=(n==o['sequence_count'] and last_epoch==o['mutation_epochs']==a['fills']+a['funding']['count'])
        native_pairs=(coherent_count==a['fills'] and unpaired==unmatched==0 and fill_count==a['fills'])
        profile_good=(not profile['issues'] and profile['complete_interior_quote_universe'] and profile['frames']==bound['profile']['frames'] and profile['phase_counts']==bound['profile']['phase_counts'])
        gates=dict(actual_os_exit0='PASS',complete_cash_reconciliation='PASS' if cashproof else 'UNKNOWN',signed_asset_funding_reconciliation='PASS' if fproof and signed==D(a['funding']['signed_amount']) else 'UNKNOWN',
            native_fee_reconciliation='PASS' if fees==fill_fees==D(a['native_fees']) and currencies_ok else 'UNKNOWN',
            native_3TP='NOT_APPLICABLE_LEGACY_CONTROL' if label=='P0' else ('PASS' if profile_good and profile['checked_P1_held_frames']>0 and a.get('method_a_tp_audit') else 'UNKNOWN'),
            ownership='PASS' if profile_good and fill_count==a['fills'] else 'UNKNOWN',continuous_settled_coverage='PASS' if complete_range and not bad else 'UNKNOWN',
            coherent_prefill_preopen_event_coverage='PASS' if o['status']=='PASS' and not o['unknown'] and native_epochs and native_pairs and not bad else 'UNKNOWN',
            source_config_data_comparable='PASS' if venue else 'UNKNOWN',rights_audit_complete='PASS' if profile_good and native_pairs else 'UNKNOWN',
            terminal_positions0_orders0='PASS' if terminal else 'UNKNOWN',zero_model_liquidations='PASS' if a['liquidation_count']==0 else 'FAIL')
        qualified=all(value=='PASS' or (key=='native_3TP' and label=='P0' and value=='NOT_APPLICABLE_LEGACY_CONTROL') for key,value in gates.items())
        out=dict(label=label,source_commit=c.SOURCE,attempt_id=bound['gate']['attempt_id'],report_sha256=bound['gate']['report']['sha256'],prefix_only=True,
            accounting_qualified=qualified,qualification='VALID_ACCOUNTED_PREFIX' if qualified else 'UNKNOWN_OR_FAILED_BLOCKS_ACCEPTANCE',financial_gates=gates,
            actual_returncode=0,metric_contract_sha256=c.METRIC,engine_instances_created=0,terminal_total=a['terminal_total'],netprofit=str(D(a['terminal_total'])-10000),
            computed_DD_percent={key:str(value) for key,value in dds.items()},settled_DD_percent=str(dds['settled']),event_DD_percent=str(dds['event']),
            daily_count=len(dreturns),daily_missing=missing,daily_ES20=es([D(x['loss']) for x in dreturns]) if not missing else 'UNKNOWN',
            parent_count=len(cycles),parent_proven_count=len(pl),parent_ES20=es(pl) if len(pl)==len(cycles) else 'UNKNOWN',daily=dreturns,parents=cycles,
            stream_rows=n,stream_issues=dict(bad),settled_receipts=kinds['SETTLED_PRE_NEXT_SOURCE_WATERMARK'],first_settled_ns=first_settled_ns,last_settled_ns=last_settled_ns,
            native_fills=fill_count,native_closed_positions=closed_count,native_closed_realized_NET_fees=str(native_realized),native_actual_fill_fees=str(fill_fees),
            signed_funding=str(signed),funding_by_asset={asset:str(sum((D(x[5]) for x in frows if x[1]==asset),D(0))) for asset in sorted({x[1] for x in frows})},
            cash_reconciliation=dict(seed='10000',native_realized_NET_settlement_fees=str(native_realized),signed_funding=str(signed),terminal=a['terminal_total'],
                residual=str(residual),policy='STRICT_ZERO_DEFAULT_NONZERO_UNKNOWN_NO_TOLERANCE_NO_FUNDING_RECLASSIFICATION',all_fill_history_covered=missing_history==extra_history==0,
                missing_native_fill_history=missing_history,extra_native_fill_history=extra_history,native_fill_history_conflicts=history_conflicts,fee_convention='NATIVE_POSITION_REALIZED_PNL_ALREADY_INCLUDES_SETTLEMENT_CURRENCY_FEES_DO_NOT_SUBTRACT_AGAIN'),
            protection_profile={key:value for key,value in profile.items() if key not in ('last_state','first_native_cash')},
            physical_binding=bound['physical_binding'],root_gate_sha256=bound['root_gate_sha256'],
            performance_scope='ACCOUNTING_ONLY_CONTROL_DD_ABOVE50_RECORDED_NOT_REJECTED;NO_FULL_OOS_OR_GO_AUTHORITY',limitations='Actual native model/settled/coherent states only; intraminute and historical venue applicability remain UNKNOWN')
        for key in ('daily','parent'):
            value=out[key+'_ES20'];out[key+'_ES20_percent']=str(D(value)*100) if value not in (None,'UNKNOWN') else 'UNKNOWN'
        db.close();return out


def main():
    p=argparse.ArgumentParser();p.add_argument('--gate',required=True,type=Path);p.add_argument('--gate-sha256',required=True);args=p.parse_args()
    bound=bind(args.gate,args.gate_sha256);out=analyze(bound);c.write(bound['output'],out)
    print(json.dumps({key:out[key] for key in ('label','qualification','accounting_qualified','financial_gates','cash_reconciliation','engine_instances_created')},sort_keys=True))

if __name__=='__main__':main()
