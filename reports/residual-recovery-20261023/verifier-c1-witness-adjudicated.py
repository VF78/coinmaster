"""Read-only C1 observer validation; no native imports, no engine or old trace."""
from collections import Counter,defaultdict
from decimal import Decimal as D
import ast
from nautilus_trader.model.objects import Price

def exact_native_domain_price(logged,native):
    # Exact pinned Price.__float__ source transform, plus same native precision.
    native_price=Price.from_str(str(native));actual=D(str(logged));wire=D(str(native))
    quantum=D(1).scaleb(-native_price.precision)
    return actual in (wire,D(str(float(native_price)))) and actual.quantize(quantum)==wire.quantize(quantum)


def validate_c1(d,filled_orders):
    events=d.get('c1_audit');terminal=d.get('c1_terminal_state');fail=[];unknown=[];checks=Counter();groups={};proposed=None;receipts={};submits={};bindings={};fills=defaultdict(list);seen_trades=set();livegroup=None
    def ck(name,condition,seq=None):
        checks[name]+=1
        if not condition:fail.append({'check':name,'sequence':seq})
    def integer_map(v):return {str(k):int(n) for k,n in v.items()}
    def difference(a,b):
        a,b=integer_map(a),integer_map(b)
        return {k:b.get(k,0)-a.get(k,0) for k in set(a)|set(b)}
    def rights(before,after,kind,lots,asset,seq):
        for k in ['btc_targets','btc_filled','sol_rights','sol_right_fraction','sol_consumed','PLANREF','H']:
            ck('rights_preserved_'+k,before[k]==after[k],seq)
        key='btc_retired' if asset.startswith('BTC') else 'sol_held_lots'
        changes=difference(before[key],after[key]);sign=(1 if kind=='CUT' else -1)*(1 if key=='btc_retired' else -1)
        ck('actual_fill_owned_level_lots',sum(changes.values())==sign*lots and all(v*sign>=0 for v in changes.values()),seq)
        other='sol_held_lots' if key=='btc_retired' else 'btc_retired';ck('other_asset_owned_levels_unchanged',before[other]==after[other],seq)
    if not isinstance(events,list) or not isinstance(terminal,dict):return {'status':'NOT_PROVEN','failed_checks':[],'unproven':['c1_audit/c1_terminal_state absent'],'mechanism_acceptance':False}
    previous=-1
    for index,r in enumerate(events,1):
        seq=r.get('sequence');ts=int(r['timestamp_ns']);event=r['event'];group=r.get('group')
        ck('sequence_contiguous',seq==index,seq);ck('timestamps_nondecreasing',ts>=previous,seq);previous=ts
        if event=='PROPOSED_DECISION':
            proposed=r
            ck('causal_proposed_checkpoint',int(r['source_quote_ns'])<int(r['receipt_ns'])==ts,seq)
            E,H,dd,c=D(r['E']),D(r['H']),D(r['DD']),D(r['cushion'])
            ck('proposal_positive_money',E>0 and H>=E,seq);ck('proposal_DD_trigger',dd>=D('.4') and abs(dd-(1-E/H))<=D('1e-26'),seq)
            ck('proposal_cushion_exact',c==max(D(0),E-D('.5')*H),seq);ck('open_loss_dominates',D(r['selected_loss'])>c,seq)
            ck('proposal_complete_gates',all(r['gates'].get(k) is True for k in ['parent_complete','no_competing_owner','checkpoint_epoch','open_loss_dominates','native_half_exists']),seq)
        elif event=='CLAIM':
            ck('claim_preceded_by_proposal',proposed is not None,seq)
            if proposed is None:continue
            ck('claim_one_per_group',group not in groups and livegroup is None,seq)
            held=int(r['frozen_held_lots']);target=int(r['frozen_target_lots']);ck('fixed_half_remaining_target',held>1 and target==held-held//2,seq)
            pos=next((p for p in proposed['positions'] if p['instrument_id']==proposed['selected']),None)
            ck('selected_native_position_exists',pos is not None,seq)
            asset=proposed['selected'].split('USDT')[0];ck('valid_native_position_side',str(pos['side']) in ('2','3'),seq);side=1 if str(pos['side'])=='2' else -1
            groups[group]={'claim':r,'proposal':proposed,'asset':asset,'side':side,'cut_cap':held-target,'cut':0,'restore':0,'credit':0,'revoked':False,'released':False,'terminal_cut':None,'last_cut_fill':None,'confirmation':None,'attempts':Counter(),'orders':Counter(),'cut_value':D(0),'bucket':{}}
            livegroup=group;proposed=None
        elif event in ('GROUP_FLAT_RESET','TERMINAL_FLAT_CONFIRMED'):
            ck('flat_reset_known_group',group in groups,seq)
            if group in groups:groups[group]['credit']=0;groups[group]['released']=True
            livegroup=None
            if event=='TERMINAL_FLAT_CONFIRMED':
                for k in ['native_positions','native_orders','native_inflight','pending','queued']:ck('native_terminal_zero_'+k,r[k]==0,seq)
        elif group in groups:
            g=groups[group]
            if event=='TOKEN_REVOKED':g['revoked']=True;g['credit']=0
            elif event=='REVOKED_HOLD_RELEASE':ck('release_only_revoked',g['revoked'],seq);g['released']=True
            elif event=='ATTEMPT_SUBMIT':
                kind=r['kind'];intent=r['intent_id'];g['step']=D(r['step']);ck('intent_unique',intent not in submits,seq);ck('no_submit_after_revoke_or_release',not g['revoked'] and not g['released'],seq)
                ck('attempt_checkpoint_causal',int(r['source_quote_ns'])<int(r['receipt_ns'])<=ts,seq);ck('attempt_after_claim',ts>int(g['claim']['timestamp_ns']),seq)
                g['attempts'][kind]+=1;submits[intent]=(group,kind,r)
                if kind=='CUT':ck('one_cut_proposal',g['attempts'][kind]<=1,seq);ck('cut_within_fixed_target',0<int(r['lots'])<=g['cut_cap'],seq)
                elif kind=='RESTORE':
                    ck('restore_with_actual_credit',int(r['lots'])==g['credit'] and g['credit']>0,seq)
                    ck('restore_after_confirmation',g['confirmation'] is not None and ts>int(g['confirmation']['timestamp_ns']),seq)
                    ck('logged_confirmation_matches',r['confirmation'] is not None and g['confirmation'] is not None and int(r['confirmation']['close_ns'])==int(g['confirmation']['timestamp_ns']),seq)
                else:ck('known_attempt_kind',False,seq)
                required=['instrument','side','original_side','step','bid','ask','quote_ns','E','H','DD','current_fill_epoch','account_event_ns','pending_ids','native_open_orders','native_inflight_orders','queued_intents','native_admission']
                absent=[k for k in required if k not in r]
                if absent:unknown.append({'sequence':seq,'predicate':'same_quote_native_admission_and_reclaim','missing':absent})
                else:
                    ck('fresh_epoch_at_attempt',int(r['fill_epoch'])==int(r['current_fill_epoch']),seq)
                    ck('current_quote_time',int(r['quote_ns'])==ts,seq)
                    ck('native_account_event_not_newer_than_checkpoint',int(r['account_event_ns'])<=int(r['source_quote_ns']),seq)
                    ck('attempt_no_competing_native_owner',not r['pending_ids'] and all(int(r[k])==0 for k in ['native_open_orders','native_inflight_orders','queued_intents']),seq)
                    ck('attempt_frozen_instrument_side',r['instrument']==g['proposal']['selected'] and int(r['original_side'])==g['side'] and int(r['side'])==g['side']*(1 if kind=='RESTORE' else -1),seq)
                    E,H,dd=D(r['E']),D(r['H']),D(r['DD']);ck('attempt_money_DD_consistent',E>0 and H>=E and abs(dd-(1-E/H))<=D('1e-26'),seq)
                    if kind=='RESTORE':
                        ck('current_restore_DD',dd<=D('.35'),seq)
                        executable=D(r['ask'] if g['side']==1 else r['bid']);vwap=g['cut_value']/D(g['cut'])
                        ck('current_executable_reclaim',g['side']*(executable-vwap)>0 and D(r['cut_actual_vwap'])==vwap,seq)
                        ck('native_restore_admission_witness',r['native_admission']=='PASSED_EXISTING_INCREASE_GATES',seq)
                    else:ck('native_cut_reduceonly_bypass',r['native_admission']=='REDUCE_ONLY_BYPASS',seq)
            elif event=='SUBMIT_OUTCOME':
                intent=r['intent_id'];ck('submit_outcome_known_intent',intent in submits,seq)
                ck('submit_outcome_bound_native_order',not r['native_submitted'] or bindings.get(intent)==r['order_id'],seq)
            elif event=='NATIVE_ORDER_SUBMITTED':
                intent=r['intent_id'];ck('native_order_has_attempt',intent in submits,seq)
                if intent in submits:
                    ck('native_order_kind_matches',r['kind']==submits[intent][1],seq);g['orders'][r['kind']]+=1;ck('one_native_attempt_per_kind',g['orders'][r['kind']]<=1,seq);bindings[intent]=r['order_id']
            elif event=='NATIVE_FILL_RECEIPT':
                intent=r['intent_id'];trade=r['trade_id'];ck('native_trade_unique',trade not in seen_trades,seq);seen_trades.add(trade)
                ck('fill_bound_to_submitted_native_order',intent in bindings and bindings[intent]==r['order_id'],seq)
                receipts.setdefault(intent,[]).append(r)
            elif event=='ACTUAL_FILL':
                intent=r['intent_id'];kind=r['kind'];lots=int(r['lots']);q=receipts.get(intent,[])
                ck('actual_fill_has_native_receipt',bool(q),seq);ck('positive_fill_lots',lots>0,seq)
                if q:
                    native=q.pop(0);ck('fill_price_time_matches_native',exact_native_domain_price(r['price'],native['price']) and ts==int(native['timestamp_ns']),seq);ck('actual_lots_match_native_quantity',D(native['quantity'])==D(lots)*g['step'],seq);fills[intent].append(native)
                ck('fill_attempt_kind_bound',intent in submits and submits[intent][1]==kind,seq)
                rights(r['rights_before'],r['rights_after'],kind,lots,g['asset'],seq)
                ck('credit_before_actual_fill_exact',int(r['credit_before'])==g['credit'],seq)
                if kind=='CUT':
                    g['cut']+=lots;g['cut_value']+=D(lots)*D(r['price']);g['last_cut_fill']=ts
                    ck('cut_actual_within_cap',g['cut']<=g['cut_cap'],seq)
                    if not g['revoked']:g['credit']+=lots
                else:g['restore']+=lots;g['credit']=max(0,g['credit']-lots);ck('restore_not_above_actual_cut',g['restore']<=g['cut'],seq)
                ck('credit_exact_after_actual_fill',int(r['credit'])==g['credit'],seq)
                bucket=integer_map(r['bucket']);ck('bucket_tracks_actual_unrestored_lots',sum(bucket.values())==g['cut']-g['restore'] and all(n>=0 for n in bucket.values()),seq);g['bucket']=bucket
                ck('attempt_counter_caps',int(r['cut_attempts'])<=1 and int(r['restore_attempts'])<=1,seq)
            elif event=='ATTEMPT_TERMINAL':
                intent=r['intent_id'];kind=r['kind'];ck('terminal_known_intent',intent in submits,seq)
                if kind=='CUT':g['terminal_cut']=ts
                else:g['credit']=0;g['released']=not g['revoked']
                ck('terminal_credit_exact',int(r['credit'])==g['credit'],seq)
            elif event=='CLOSED_4H_RECLAIM':
                op=int(r['open_ns']);ck('bar_fully_postcut_terminal',g['terminal_cut'] is not None and g['last_cut_fill'] is not None and op>max(g['terminal_cut'],g['last_cut_fill']),seq)
                ck('four_hour_closed_bar',ts-op==14_400_000_000_000,seq);ck('confirmation_DD',D(r['DD'])<=D('.35'),seq)
                ck('confirmation_after_actual_cut',g['cut']>0,seq)
                if g['cut']:ck('confirmation_price_reclaims',g['side']*(D(r['close'])-g['cut_value']/D(g['cut']))>0,seq)
                g['confirmation']=r
    orders={r['client_order_id']:r for r in filled_orders}
    for intent,actual in fills.items():
        orderid=bindings[intent];order=orders.get(orderid);ck('actual_C1_order_in_native_fills',order is not None)
        if order:
            qty=sum((D(r['quantity']) for r in actual),D(0));fees=sum((D(r['commission'].rsplit(' ',1)[0]) for r in actual),D(0));nativefees=sum((D(x.rsplit(' ',1)[0]) for x in ast.literal_eval(order['commissions'])),D(0))
            ck('native_C1_quantity_exact',qty==D(order['filled_qty']));ck('native_C1_fees_exact',fees==nativefees)
            ck('native_CUT_reduceonly_RESTORE_increase',(order['is_reduce_only']=='True')==(submits[intent][1]=='CUT'))
    ck('no_unconsumed_native_fill_receipts',not any(receipts.values()))
    for key in ['native_positions','native_orders','native_inflight','pending','queued','credit']:ck('final_state_zero_'+key,int(terminal.get(key,-1))==0)
    ck('final_no_active_hold',terminal.get('active_hold') is False)
    denials=Counter()
    for key,row in d.get('c1_denial_counts',{}).items():
        _,month,_=ast.literal_eval(key);denials[month]+=int(row['count']);ck('denials_positive_ordered',int(row['count'])>0 and int(row['first_ns'])<=int(row['last_ns']));ck('denials_have_failed_gate',not all(row['gates'].values()))
    qualifications=['Internal tier/margin/admission implementation and worst-native-open-loss selection proved by frozen source and focused fixtures; saved observer proves returned decisions, not independent native reexecution.']
    if not any(r['event']=='ATTEMPT_SUBMIT' and r['kind']=='RESTORE' for r in events):qualifications.append('No historical restore attempt: restoration code path remains source/fixture proof, not historical execution evidence.')
    return {'status':'FAIL' if fail else ('NOT_PROVEN' if unknown else 'PASS'),'checks_evaluated':dict(checks),'failed_checks':fail,'unproven':unknown,'qualifications':qualifications,'monthly_denial_counts':dict(denials),'event_counts':dict(Counter(r['event'] for r in events)),'groups':len(groups),'native_C1_cut_orders':sum(g['orders']['CUT'] for g in groups.values()),'native_C1_restore_orders':sum(g['orders']['RESTORE'] for g in groups.values()),'actual_cut_lots':sum(g['cut'] for g in groups.values()),'actual_restored_lots':sum(g['restore'] for g in groups.values()),'mechanism_acceptance':not fail and not unknown}
