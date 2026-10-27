"""Stdlib-only Method-A native artifact reader. No engine or inferred PnL.

Decimal50 ES20/daily/parent/coherent/funding blocks retain metricca815 semantics.
Native PositionClosed.realized_pnl is NET settlement-currency commissions.
Cash residual default is strict zero; nonzero is UNKNOWN, never funding.
"""
from pathlib import Path
from decimal import Decimal as D,getcontext,localcontext,ROUND_CEILING,ROUND_FLOOR
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


def authorized_tp_prices(reference,d3,side):
    reference=D(reference);d3=D(str(d3));tick=D('.1')
    if side not in (-1,1) or not reference.is_finite() or not d3.is_finite() or reference<=0 or d3<=0:
        raise ValueError('INVALID_SOURCE_AUTHORIZED_TP_REFERENCE')
    # Accepted a4dd execution starts with Python Decimal's default precision28;
    # metric arithmetic remains Decimal50 outside this local source calculation.
    with localcontext() as ctx:
        ctx.prec=28
        rounding=ROUND_CEILING if side==1 else ROUND_FLOOR
        prices=tuple((reference*(1+side*d3*D(i)/3)/tick).to_integral_value(rounding=rounding)*tick for i in (1,2,3))
        if any(not price.is_finite() or price<=0 for price in prices) or not all(side*(right-left)>0 for left,right in zip((reference,)+prices,prices)):
            raise ValueError('SOURCE_TP_GEOMETRY_NOT_ORDERED_OUTWARD')
        if any(side*(price-reference)-reference*D('.00055')-price*D('.00055')<=0 for price in prices):
            raise ValueError('SOURCE_TP_NOT_POSITIVE_AFTER_BASE_FEES')
    return prices


def tp_order_errors(order,owner,ack,price,side):
    issues=[]
    if order.get('instrument')!='BTCUSDT-PERP.P1SIM':issues.append('P1_TP_wrong_instrument')
    expected='SELL' if side==1 else 'BUY'
    if order.get('side')!=expected or owner.get('side')!=expected:issues.append('P1_TP_wrong_exit_side')
    try:
        actual=D(order['price'])
        if not actual.is_finite() or actual<=0 or actual!=price:issues.append('P1_TP_not_authorized_native_price')
    except Exception:issues.append('P1_TP_price_missing_or_invalid')
    if ack is None:issues.append('P1_TP_native_ACK_price_missing')
    else:
        if ack.get('price')!=order.get('price') or ack.get('quantity')!=order.get('quantity'):issues.append('P1_TP_current_ACK_price_quantity_mismatch')
        if ack.get('instrument')!=order.get('instrument') or ack.get('side')!=expected:issues.append('P1_TP_native_ACK_owner_mismatch')
        if ack.get('strategy')!=order.get('strategy') or owner.get('strategy_id')!=order.get('strategy'):issues.append('P1_TP_strategy_identity_mismatch')
    return issues


def tp_authority(audit):
    references={};submits={};acks={}
    for row in audit or ():
        if row['event']=='ENTITLEMENT':
            key=(row['episode_id'],int(row['cumulative_entry_lots']))
            value=(int(row['timestamp_ns']),row['tp_reference'])
            if key in references and (references[key] is None or D(references[key][1])!=D(value[1])):references[key]=None
            elif key not in references or (references[key] is not None and value[0]<references[key][0]):references[key]=value
        elif row['event']=='MODIFY_SUBMIT':submits[(row['order_id'],str(row['sequence']))]=row
        elif row['event']=='LATEST_MODIFY_ACK':acks[row['native_event_id']]=row
    return dict(references=references,submits=submits,acks=acks)


def rights_evidence(db,report):
    parents={row['episode_id']:row for row in report['split_cover_audit']['parents']}
    entries={row['episode_id']:row for row in report['entry_sizing_audit']}
    total=0;facts=[];missing=set();failures=Counter()
    for (payload,) in db.execute('SELECT body FROM fills'):
        fill=json.loads(payload)
        if fill['action']!='SOL_ADD':continue
        total+=1
        for key in ('episode.h_at_SOL_ADD_admission','episode.sol_add_filled_notional_at_SOL_ADD_admission','last_accepted_session','current_BTC_SOL_signal_sessions'):
            missing.add('profile.'+key)
        parent=fill['parent'];raw=db.execute('SELECT body FROM sol_before WHERE id=?',(fill['native_event_id'],)).fetchone()
        if raw is None:missing.add('profile.BEFORE_STRATEGY_SOL_ADD.current_parent_and_fraction');continue
        before=json.loads(raw[0]);ep=before.get('episode')
        if ep is None or ep['id']!=parent:failures['old_SOL_current_parent_mismatch']+=1;continue
        entry=entries.get(parent);plan=parents.get(parent);level=int(fill['level'])
        if entry is None or plan is None:missing.add('report.entry_sizing_audit/split_cover_audit.actual_parent');continue
        fraction=ep['old_SOL_fractions'].get(str(level))
        if fraction is None or not D(str(fraction)).is_finite() or not 0<D(str(fraction))<=1 or level not in ep['old_SOL_rights']:
            failures['old_SOL_fraction_or_membership_invalid']+=1;continue
        if 'net_submitted_btc_qty' not in entry:missing.add('entry_sizing_audit.net_submitted_btc_qty');continue
        if 'reference_target_lots' not in entry:missing.add('entry_sizing_audit.reference_target_lots')
        net=D(entry['net_submitted_btc_qty'])
        if net<=0:failures['old_SOL_planned_entry_denominator_invalid']+=1;continue
        omitted=level in entry['omitted_zero_levels']
        activations=[row for row in entry.get('sol_right_activations',()) if level in row['levels'] and int(row['timestamp_ns'])<=int(fill['ns'])]
        if omitted and not activations:missing.add('entry_sizing_audit.sol_right_activations.actual_omitted_level')
        if len(facts)<16:
            facts.append(dict(parent=parent,level=level,fill_event_id=fill['native_event_id'],current_parent_matched=True,
                observed_fraction=fraction,actual_entry_quantity=ep['entry_qty_exact'],planned_entry_quantity=str(net),
                raw_legacy_reference_target_lots=entry.get('reference_target_lots'),omitted_level=omitted,guarded_activation_rows=len(activations),
                final_parent_H=plan.get('planref_v1_h_actual'),final_parent_H_scope='FINAL_ENTRY_SNAPSHOT_NOT_PER_ADMISSION_REMAINING_BUDGET'))
        # These are original oldSOL policy fields, not modern hedge caps.
        # Frozen334 does not emit current H or its irreversible filled-notional
        # accumulator at the actual admission boundary. A final parent H and
        # a current rights set do not prove the current unused authorization.
        if omitted:
            for key in ('episode.btc_deferred_right_touched','episode.sol_right_decision_index'):
                missing.add('profile.'+key)
    complete=not failures and not missing
    return dict(status='PASS' if complete else 'UNKNOWN',actual_SOL_ADD_fills=total,
        mechanism_status='NOT_TESTED_NO_ACTUAL_SOL_ADD_FILLS' if total==0 else ('PARTIALLY_OBSERVED_MISSING_REQUIRED_FACTS' if not complete else 'ACTUAL_LEGACY_RIGHTS_COMPLETE'),
        available_actual_field_map=dict(parent='profile.owned_pending + native event/OID',fraction='profile.episode.old_SOL_fractions',
            raw_denominators='report.entry_sizing_audit.reference_target_lots/omitted_zero_levels/net_submitted_btc_qty',
            activation='report.entry_sizing_audit.sol_right_activations',H='report.split_cover_audit.parents.planref_v1_h_actual(final only)'),
        examples=facts,examples_capped_at=16,missing_required_fields=sorted(missing),failures=dict(failures),
        no_modern_P3_A0_rules_applied=True,no_unemitted_fact_promoted_to_PASS=True)


class RightsFactMissing(Exception):pass
class RightsPolicyViolation(Exception):pass

def rights_need(condition,name):
    if not condition:raise RightsPolicyViolation(name)

def rights_float(value,hex_value=None):
    result=float(value)
    if not D(str(result)).is_finite():raise RightsFactMissing('nonfinite_source_float')
    if hex_value is not None and result.hex()!=hex_value:raise RightsFactMissing('source_float_hex_conflict')
    return result

def rights_auth(ep):
    values=ep['source_float_values'];hexes=ep['source_float_hex'];maps=ep['source_float_maps'];maphex=ep['source_float_maps_hex']
    for key,value in values.items():
        if value is not None:rights_float(value,hexes[key])
    for name,entries in maps.items():
        for level,value in entries.items():rights_float(value,maphex[name][level])
    rights_need(ep['h']==values['h'],'source_H_alias_conflict')
    for name in ('sol_add_filled_notional','sol_ownership_transfer_credit','sol_risk_retired_notional'):
        rights_need(ep[name]==maps[name],'source_map_alias_conflict')
    rights_need(ep['old_SOL_fractions']==maps['sol_right_fraction'],'source_fraction_alias_conflict')
    return values,maps

def rights_budget(ep,policy,level):
    values,maps=rights_auth(ep);key=str(level)
    h=rights_float(values['h']);fraction=rights_float(maps['sol_right_fraction'].get(key,1.0))
    rights_need(h>0 and 0<fraction<=1,'invalid_original_H_or_fraction')
    allowed=h*float(policy['sol_size_multipliers_h'][level])*fraction
    return allowed-maps['sol_add_filled_notional'].get(key,0.0)-maps['sol_ownership_transfer_credit'].get(key,0.0)-maps['sol_risk_retired_notional'].get(key,0.0)

def rights_intent(value):
    return dict(id=value.get('id',value.get('intent_id')),parent=value['parent'],action=value['action'],level=value['level'],
        side=value['side'],quantity=value['quantity'],requested_notional=value['requested_notional'],
        decision_index=value['decision_index'],reason=value['reason'])

def rights_context(state):
    return dict(episode=state['episode'],sessions=state.get('legacy_sessions'))

def rights_v2_tables(db):
    for name in ('rights_origin','rights_admission','rights_after','rights_control','rights_quote_actions','rights_native_order'):
        db.execute('CREATE TABLE '+name+' (id TEXT PRIMARY KEY,body TEXT NOT NULL)')

def rights_v2_frame(db,row,state,issues):
    phase=row['phase'];seq=row['sequence'];context=rights_context(state)
    def put(table,key,body):return insert_unique(db,table,key,body,issues)
    def get(table,key):
        value=db.execute('SELECT body FROM '+table+' WHERE id=?',(key,)).fetchone()
        return None if value is None else json.loads(value[0])
    def control(key,body):db.execute('INSERT OR REPLACE INTO rights_control VALUES (?,?)',(key,json.dumps(body,sort_keys=True)))
    if phase=='BEFORE_STRATEGY_on_quote_tick_NATIVE_CACHE_ALREADY_MUTATED':
        control('quote_callback',dict(seq=seq,context=context,input=get('rights_control','source_input'),writer_count=get('rights_control','writers') or 0))
    if phase=='BEFORE_STRATEGY_on_order_filled_NATIVE_CACHE_ALREADY_MUTATED':
        control('writers',(get('rights_control','writers') or 0)+1)
    for value in state['queued']:
        if value['action']!='SOL_ADD':continue
        try:intent=rights_intent(value)
        except KeyError:continue  # V1 schema remains explicitly unqualified.
        old=get('rights_origin',intent['id'])
        if old is None:put('rights_origin',intent['id'],dict(seq=seq,method='EARLIEST_ACTUAL_QUEUED_INTENT',intent=intent,context=context))
        elif old['intent']!=intent:issues['rights_immutable_queued_intent_conflict']+=1
    if phase=='BEFORE_NATIVE_MATCHING_INPUT':
        control('source_input',dict(seq=seq,input=row['input']))
    if phase.startswith('AFTER_STRATEGY_') and row.get('native_order') is not None:
        order=row['native_order']
        db.execute('INSERT OR REPLACE INTO rights_native_order VALUES (?,?)',(order['order_id'],json.dumps(
            dict(seq=seq,order=order,event_id=row['native_event_id'],event_type=row['native_event_type']),sort_keys=True)))
    if phase=='SOL_ADD_PRE_NATIVE_TRANSPORT_AFTER_CHECKPOINT':
        admission=row['admission'];intent=rights_intent(admission['pending_intent'])
        origin=get('rights_origin',intent['id'])
        if origin is None:
            opened=get('rights_control','quote_callback')
            # This is a source-serial interval proof from actual frames, never a fabricated creation snapshot.
            if opened is not None and opened['writer_count']==(get('rights_control','writers') or 0):
                before=opened['context']['episode'];after=context['episode']
                keys=('source_float_values','source_float_maps')
                if before is not None and after is not None and before['id']==after['id'] and all(before.get(k)==after.get(k) for k in keys):
                    put('rights_origin',intent['id'],dict(seq=opened['seq'],method='SAME_SERIAL_QUOTE_CALLBACK_NO_AUTHORIZATION_WRITER',
                        intent=intent,context=context,actual_pre_callback_context=opened['context']))
        put('rights_admission',admission['client_order_id'],dict(seq=seq,admission=admission,context=context))
    if phase=='AFTER_STRATEGY_on_order_filled' and row['native_event_type']=='OrderFilled':
        put('rights_after',row['native_event_id'],dict(seq=seq,episode=state['episode']))
    if phase=='AFTER_STRATEGY_on_quote_tick':
        opened=get('rights_control','quote_callback')
        if opened is not None and opened['input'] is not None:
            tick=opened['input']['input'];pre=opened['context']['episode'];post=context['episode']
            if tick['instrument']=='BTCUSDT-PERP.P1SIM' and tick['event_ns']==row['event_ns'] and pre is not None and post is not None and pre['id']==post['id']:
                if pre.get('btc_deferred_right_touched')!=post.get('btc_deferred_right_touched') or pre['old_SOL_rights']!=post['old_SOL_rights']:
                    put('rights_quote_actions',str(opened['seq']),dict(before_seq=opened['seq'],after_seq=seq,input=tick,before=opened['context'],after=context))
        db.execute('DELETE FROM rights_control WHERE id=?',('quote_callback',))


def rights_sessions(context,intent,creation=False):
    ep=context['episode'];sessions=context['sessions'];s=sessions['current_BTC_SOL_signal_sessions'];latest=int(s['bar_index'])
    expected=s['source_bar_session_ns']
    rights_need(s['BTC']['instrument']=='BTCUSDT-PERP.P1SIM' and s['SOL']['instrument']=='SOLUSDT-PERP.P1SIM','wrong_native_daily_instrument')
    feature=sessions['current_features'];rights_need(feature['index']==latest,'source_feature_index_conflict')
    decision=ep['sol_right_decision_index'][str(intent.get('level',0))]
    if type(decision) is not int or not 0<=decision<=latest:raise RightsFactMissing('actual_right_decision_index_causal_origin')
    if not (s['BTC']['ts_event']==s['SOL']['ts_event']==sessions['last_accepted_session']==expected and sessions['latest_seen_session'] in (None,expected)):raise RightsFactMissing('stale_or_conflicting_native_session')
    if creation and latest!=intent['decision_index']:raise RightsFactMissing('creation_feature_origin_not_observed')
    return latest,feature

def rights_source_z(ep,feature):
    values,_=rights_auth(ep)
    fixed=values['fixed_sigma']
    if fixed is None:return feature['z']
    if feature['relative'] is None or feature['mu'] is None:return None
    return (feature['relative']-feature['mu'])/fixed


def rights_entry_native(db,ep,seq,entry):
    values,_=rights_auth(ep);native_entry=D(0);native_float=0.0
    for (body,) in db.execute("SELECT body FROM fills ORDER BY CAST(json_extract(body,'$.sequence') AS INTEGER)"):
        fill=json.loads(body)
        if fill['parent']==ep['id'] and fill['action']=='BTC_ENTRY' and fill['sequence']<=seq:
            native_entry+=D(fill['qty']);native_float+=float(fill['qty'])
    rights_need(native_entry==D(ep['raw_entry']['btc_entry_qty_exact']) and native_float.hex()==float(values['btc_initial_qty']).hex(),'actual_entry_fraction_native_fill_source_conflict')
    net=values['btc_net_planned_qty'];rights_need(net>0 and float(entry['net_submitted_btc_qty']).hex()==float(net).hex(),'raw_entry_denominator_conflict')

def rights_raw_fraction(db,ep,level,seq,entry,label):
    rights_entry_native(db,ep,seq,entry);key=str(level);omitted=level in ep['omitted_raw_levels'];writer=None
    for (body,) in db.execute("SELECT body FROM fills ORDER BY CAST(json_extract(body,'$.sequence') AS INTEGER)"):
        fill=json.loads(body)
        if fill['parent']!=ep['id'] or fill['sequence']>seq:continue
        if (fill['action']=='BTC_ENTRY' and omitted) or (fill['action']=='BTC_REDUCE' and str(fill['level'])==key):writer=fill
    if writer is None:raise RightsFactMissing('actual_native_fraction_writer:'+ep['id']+':'+key)
    row=db.execute('SELECT body FROM rights_after WHERE id=?',(writer['native_event_id'],)).fetchone()
    if row is None:raise RightsFactMissing('actual_fraction_writer_after_snapshot')
    written=json.loads(row[0]);source=written['episode'];rights_need(source['id']==ep['id'],'fraction_writer_parent_conflict')
    rights_entry_native(db,source,written['seq'],entry)
    values,maps=rights_auth(source);raw=source['raw_entry'];fraction=min(1.0,values['btc_initial_qty']/values['btc_net_planned_qty'])
    if not omitted:
        denominator=(raw['method_a_raw_target_lots'] if label=='P1' else raw['btc_tp_target_lots'])[key]
        filled=raw['btc_tp_filled_lots'].get(key,0);tp=D(0)
        for (body,) in db.execute("SELECT body FROM fills ORDER BY CAST(json_extract(body,'$.sequence') AS INTEGER)"):
            fill=json.loads(body)
            if fill['parent']==ep['id'] and fill['action']=='BTC_REDUCE' and str(fill['level'])==key and fill['sequence']<=written['seq']:tp+=D(fill['qty'])
        lots=tp/D('.001');rights_need(lots==lots.to_integral_value() and denominator>0,'raw_native_TP_lot_denominator_conflict')
        rights_need(filled==min(int(lots),raw['btc_tp_target_lots'][key]) if label=='P0' else filled==int(lots),'raw_TP_consumption_native_conflict')
        fraction=min(1.0,filled/denominator)*fraction if label=='P1' else filled/denominator*fraction
    rights_need(float(maps['sol_right_fraction'][key]).hex()==float(fraction).hex(),'original_fraction_writer_formula_conflict')
    rights_need(float(ep['old_SOL_fractions'][key]).hex()==float(fraction).hex(),'current_fraction_changed_without_original_writer')
    if not omitted:rights_need(ep['sol_right_decision_index'][key]==source['sol_right_decision_index'][key],'actual_TP_right_decision_writer_conflict')
    return omitted


def rights_guarded_touch(db,ep,entry,level,admission_seq):
    rights_need(ep['btc_deferred_right_touched'] is True,'deferred_reference_not_touched')
    reference=D(ep['btc_deferred_right_reference_price']);rights_need(reference>0,'invalid_deferred_reference')
    key=str(level)
    actions=[json.loads(x[0]) for x in db.execute("SELECT body FROM rights_quote_actions ORDER BY CAST(json_extract(body,'$.before_seq') AS INTEGER)")]
    activations=entry.get('sol_right_activations',())
    for active in actions:
        if active['after_seq']>admission_seq:continue
        before=active['before']['episode'];after=active['after']['episode'];quote=active['input']
        if before is None or after is None or before['id']!=ep['id'] or after['id']!=ep['id']:continue
        if level in before['old_SOL_rights'] or level not in after['old_SOL_rights']:continue
        rows=[x for x in activations if level in x['levels'] and int(x['timestamp_ns'])==int(quote['event_ns'])]
        if not rows:continue
        if before['btc_deferred_right_reference_price']!=str(reference) or after['btc_deferred_right_touched'] is not True:continue
        index,_=rights_sessions(dict(episode=after,sessions=active['before']['sessions']),dict(decision_index=0,level=level))
        rights_need(after['sol_right_decision_index'][key]==index and ep['sol_right_decision_index'][key]==index,'guarded_right_decision_session_conflict')
        # Source _activate_selective runs at the start of this strategy quote callback.
        # Matching/native fills are already applied; future same-ns callbacks are excluded.
        rights_entry_native(db,before,active['before_seq'],entry)
        confirmed=before['source_float_values']['btc_initial_qty']
        rights_need(confirmed>0 and any(float(x['confirmed_native_entry_qty']).hex()==float(confirmed).hex() for x in rows),'guarded_activation_confirmed_entry_sequence_conflict')
        for touched in actions:
            if touched['before_seq']>active['before_seq']:break
            pre=touched['before']['episode'];post=touched['after']['episode'];tick=touched['input']
            if pre is None or post is None or pre['id']!=ep['id'] or post['id']!=ep['id']:continue
            if pre['btc_deferred_right_touched'] is not False or post['btc_deferred_right_touched'] is not True:continue
            if int(tick['event_ns'])<int(entry['q1_ns']) or pre['btc_deferred_right_reference_price']!=str(reference):continue
            crossed=(ep['side']==1 and D(tick['bid'])>=reference) or (ep['side']==-1 and D(tick['ask'])<=reference)
            if not crossed:continue
            rights_entry_native(db,pre,touched['before_seq'],entry)
            earned=pre['source_float_values']['btc_initial_qty']>0 and any(pre['old_SOL_fractions'].get(str(x),0)>0 for x in pre['omitted_raw_levels'])
            if not earned:continue
            # Readiness is intentionally not required at the earlier earned latch.
            if touched['before_seq']!=active['before_seq'] and before['btc_deferred_right_touched'] is not True:continue
            if any(x['after']['episode'] is not None and x['after']['episode']['id']==ep['id'] and
                   touched['after_seq']<=x['after_seq']<=active['after_seq'] and x['after']['episode']['btc_deferred_right_touched'] is not True for x in actions):
                raise RightsFactMissing('earned_touch_latch_not_continuously_retained')
            return
    raise RightsFactMissing('actual_earned_touch_then_guarded_activation_sequence')


def rights_auth_signature(ep):
    rights_auth(ep)
    return dict(h=ep['source_float_hex']['h'],maps=ep['source_float_maps_hex'])

def rights_origin_interval(db,origin,current,admission_seq):
    expected=rights_auth_signature(origin['context']['episode']);parent=origin['context']['episode']['id'];writers=0
    for (body,) in db.execute("SELECT body FROM fills ORDER BY CAST(json_extract(body,'$.sequence') AS INTEGER)"):
        fill=json.loads(body)
        if fill['parent']!=parent or not origin['seq']<fill['sequence']<=admission_seq:continue
        before=db.execute('SELECT body FROM sol_before WHERE id=?',(fill['native_event_id'],)).fetchone()
        after=db.execute('SELECT body FROM rights_after WHERE id=?',(fill['native_event_id'],)).fetchone()
        if before is None or after is None:raise RightsFactMissing('actual_origin_interval_writer_frames')
        pre=json.loads(before[0])['episode'];post=json.loads(after[0])['episode']
        if pre is None or post is None or pre['id']!=parent or post['id']!=parent:raise RightsFactMissing('origin_interval_writer_parent')
        if rights_auth_signature(pre)!=expected:raise RightsFactMissing('unobserved_authorization_writer_before_native_fill')
        expected=rights_auth_signature(post);writers+=1
    if expected!=rights_auth_signature(current):raise RightsFactMissing('unobserved_authorization_writer_before_admission')
    return writers


def rights_market_execution(db,oid,initialized):
    row=db.execute('SELECT body FROM rights_native_order WHERE id=?',(oid,)).fetchone()
    if row is None:raise RightsFactMissing('actual_market_native_history_or_terminal:'+oid)
    fact=json.loads(row[0]);order=fact['order'];history=order['native_history']
    for key in ('order_id','instrument','strategy','side','quantity','reduce_only'):
        rights_need(order[key]==initialized[key],'actual_market_order_identity_conflict')
    terminal={'FILLED':'OrderFilled','CANCELED':'OrderCanceled','REJECTED':'OrderRejected','EXPIRED':'OrderExpired','DENIED':'OrderDenied'}
    if order['status'] not in terminal:raise RightsFactMissing('actual_market_terminal_disposition:'+oid)
    terminal_events=[x for x in history if x['id'] and x['type']==terminal[order['status']]]
    if not terminal_events or not fact['event_id'] or not any(x['id']==fact['event_id'] and x['type']==fact['event_type'] for x in history):
        raise RightsFactMissing('actual_market_terminal_event_not_in_history:'+oid)
    terminal_id=terminal_events[-1]['id']
    quantity=D(order['quantity']);filled=D(order['filled'])
    rights_need(quantity>0 and 0<=filled<=quantity,'actual_market_terminal_quantity_conflict')
    actual=D(0);count=0
    for trade,body in db.execute("SELECT id,body FROM fills ORDER BY CAST(json_extract(body,'$.sequence') AS INTEGER)"):
        fill=json.loads(body)
        if fill['oid']!=oid:continue
        rights_need(fill['action']=='SOL_ADD' and fill['instrument']==order['instrument'],'actual_market_fill_owner_conflict')
        if not trade or not fill['native_event_id'] or not any(x['id']==fill['native_event_id'] and x['type']=='OrderFilled' for x in history):
            raise RightsFactMissing('actual_market_fill_event_history_join:'+oid)
        native=db.execute('SELECT body FROM position_trades WHERE id=?',(trade,)).fetchone()
        if native is None:raise RightsFactMissing('actual_market_trade_closed_native_history_join:'+trade)
        native=json.loads(native[0])
        rights_need(native['native_event_id']==fill['native_event_id'] and native['oid']==oid and D(native['qty'])==D(fill['qty']) and D(native['px'])==D(fill['px']),'actual_market_trade_native_position_conflict')
        rights_need(D(fill['qty'])>0 and D(fill['px'])>0,'nonpositive_actual_market_fill')
        actual+=D(fill['qty']);count+=1
    rights_need(actual==filled,'actual_market_fill_total_vs_native_order_conflict')
    rights_need((order['status']=='FILLED' and filled==quantity and count>0) or (order['status']!='FILLED' and filled<quantity),'actual_market_terminal_filled_state_conflict')
    return dict(kind='GENUINE_NATIVE_FILLED_HISTORY' if count else 'GENUINE_UNFILLED_NATIVE_TERMINAL',
        terminal_status=order['status'],terminal_event_id=terminal_id,actual_trade_events=count,
        optional_Accepted_present=any(x['type']=='OrderAccepted' for x in history),initialized_never_execution_credit=True)

def rights_v2_evidence(db,report,label,metadata,observer_sha):
    expected_observer='6e21b00d7df3a7819a67bf0c571ff31f33822888d5095ebf43075c7fa7f72aa7'
    missing=set();failures=Counter();examples=[];admissions=0;actual_fills=0
    def get(table,key):
        row=db.execute('SELECT body FROM '+table+' WHERE id=?',(key,)).fetchone()
        return None if row is None else json.loads(row[0])
    if observer_sha!=expected_observer:missing.add('exact_frozen_observer360_script_pin')
    capture=metadata.get('legacy_SOL_admission_capture')
    if capture is None:missing.add('observer_profile.legacy_SOL_admission_capture')
    else:
        if capture.get('schema')!='METHOD_A_LEGACY_SOL_PRE_TRANSPORT_V2':missing.add('observer_profile.V2_schema')
        if capture.get('error_count')!=0:missing.add('observer_profile.zero_capture_errors')
    entries={x['episode_id']:x for x in report['entry_sizing_audit']}
    qualified={}
    for oid,body in db.execute('SELECT id,body FROM rights_admission'):
        admissions+=1
        try:
            row=json.loads(body);a=row['admission'];ep=row['context']['episode'];i=rights_intent(a['pending_intent']);level=int(i['level']);key=str(level)
            origin=get('rights_origin',i['id'])
            if origin is None:raise RightsFactMissing('intent_origin_interval:'+i['id'])
            if origin['intent']!=i:raise RightsFactMissing('conflicting_immutable_intent_before_admission')
            if db.execute("SELECT COUNT(*) FROM rights_admission WHERE json_extract(body,'$.admission.intent_id')=?",(i['id'],)).fetchone()[0]>1:raise RightsFactMissing('active_ce7_requeue_origin_not_proven')
            writer_count=rights_origin_interval(db,origin,ep,row['seq'])
            rights_need(origin['context']['episode']['id']==ep['id']==a['parent']==i['parent']==a['current_parent'],'actual_parent_mapping_conflict')
            rights_need(a['schema']=='METHOD_A_LEGACY_SOL_PRE_TRANSPORT_V2' and a['boundary']=='ORIGINAL_RECORD_SUBMISSION_RETURNED_TRUE_BEFORE_NATIVE_TRANSPORT','wrong_admission_schema_or_boundary')
            if a['sessions']!=row['context']['sessions']:raise RightsFactMissing('conflicting_admission_session_copy')
            for name in set(a['episode'])&set(ep):
                if a['episode'][name]!=ep[name]:raise RightsFactMissing('conflicting_admission_episode_copy')
            rights_need(a['episode']['h_at_SOL_ADD_admission']==ep['h'] and a['episode']['sol_add_filled_notional_at_SOL_ADD_admission']==ep['sol_add_filled_notional'],'admission_missing_six_fact_alias_conflict')
            rights_need(a['checkpoint_result'] is True and a['initialized_order_is_ACK_or_fill'] is False and a['domain_pending_contains_intent'] is True,'invalid_pre_transport_boundary')
            rights_need(a['order_decision_index']==i['decision_index'] and a['action']==i['action']=='SOL_ADD' and a['level']==level,'intent_order_decision_mapping_conflict')
            policy=a['original_policy']
            rights_need(policy['sol_overlay_enabled'] is True and policy['sol_late_entry_after_tp'] is True and policy['episode_fixed_beta'] is False,'not_original_ce7_SOL_policy')
            rights_need(policy['sol_size_multipliers_h']==[1.75,2.625,3.5] and policy['sol_entry_z']==[1.25,2.5,3.75] and policy['max_parent_notional']==30000000.0,'original_ce7_policy_value_drift')
            created=origin['context'];remaining=rights_budget(created['episode'],policy,level)
            rights_need(remaining>1e-12 and float(i['requested_notional']).hex()==float(remaining).hex(),'immutable_requested_notional_not_original_creation_remaining')
            original_latest,feature=rights_sessions(created,i,True)
            rights_need(level in created['episode']['old_SOL_rights'] and feature['beta'] is not None and .2<feature['beta']<4,'creation_right_or_beta_invalid')
            z=rights_source_z(created['episode'],feature)
            rights_need(z is not None and created['episode']['side']*z>=policy['sol_entry_z'][level],'creation_original_z_guard_invalid')
            current_latest,current_feature=rights_sessions(row['context'],i)
            rights_need(level in ep['old_SOL_rights'],'admission_original_right_missing')
            if current_latest>i['decision_index']:
                z=rights_source_z(ep,current_feature)
                rights_need(current_feature['side']==ep['side'] and current_feature['beta'] is not None and .2<current_feature['beta']<4 and z is not None and ep['side']*z>=policy['sol_entry_z'][level],'original_stale_add_guard_invalid')
                values,maps=rights_auth(ep)
                rights_need(values['h']*policy['sol_size_multipliers_h'][level]*maps['sol_right_fraction'].get(key,1.0)>maps['sol_add_filled_notional'].get(key,0.0),'original_stale_right_already_consumed')
                lifecycle=ep['sol_lifecycle'];bar=datetime.fromisoformat(row['context']['sessions']['current_BTC_SOL_signal_sessions']['bar_close_time'])
                if lifecycle['sol_qty'] and lifecycle['first_fill_at'] is not None:
                    rights_need(bar<datetime.fromisoformat(lifecycle['first_fill_at'])+timedelta(days=policy['sol_max_holding_days']),'original_stale_holding_timeout')
                    signed=ep['side']*z
                    rights_need(not ((not lifecycle['half_done'] and signed<=policy['sol_exit_half_z']) or (lifecycle['half_done'] and lifecycle['half_decision_index'] is not None and current_latest>lifecycle['half_decision_index'] and signed<=policy['sol_exit_all_z'])),'original_stale_SOL_exit_preempts_add')
            entry=entries[ep['id']]
            omitted=rights_raw_fraction(db,created['episode'],level,origin['seq'],entry,label)
            rights_raw_fraction(db,ep,level,row['seq'],entry,label)
            for context,boundary_seq in ((created,origin['seq']),(row['context'],row['seq'])):
                consumed=0.0
                for (payload,) in db.execute("SELECT body FROM fills ORDER BY CAST(json_extract(body,'$.sequence') AS INTEGER)"):
                    fill=json.loads(payload)
                    if fill['action']=='SOL_ADD' and fill['parent']==ep['id'] and str(fill['level'])==key and fill['sequence']<=boundary_seq:consumed+=float(fill['qty'])*float(fill['px'])
                rights_need(float(context['episode']['sol_add_filled_notional'].get(key,0.0)).hex()==consumed.hex(),'irreversible_consumption_actual_native_fill_conflict')
            order=a['native_initialized_order'];quote=a['native_quote'];inst=a['instrument']
            rights_need(order['order_id']==oid and order['instrument']==quote['instrument']==inst['id']=='SOLUSDT-PERP.P1SIM','native_SOL_order_quote_instrument_conflict')
            rights_need(order['side']==('SELL' if ep['side']==1 else 'BUY') and i['side']==-ep['side'] and not order['reduce_only'] and order['status']=='INITIALIZED','native_SOL_side_or_initialized_state_conflict')
            execution=rights_market_execution(db,oid,order)
            ack=get('native_acks',oid)
            if ack is not None:
                rights_need(ack['instrument']==order['instrument'] and ack['strategy']==order['strategy'] and ack['side']==order['side'] and D(ack['quantity'])==D(order['quantity']),'optional_actual_market_ACK_order_conflict')
            with localcontext() as ctx:
                ctx.prec=28
                executable=D(str(float(quote['ask'] if order['side']=='BUY' else quote['bid'])))
                quantity=float(D(str(min(i['requested_notional'],policy['max_parent_notional'])))/executable)
                step=D(inst['size_increment']);rounded=(D(str(quantity))//step)*step
                rights_need(rounded>0 and D(order['quantity'])==rounded,'original_native_lot_rounding_conflict')
                if inst['min_quantity'] is not None:rights_need(rounded>=D(inst['min_quantity']),'native_min_quantity_conflict')
                if inst['min_notional'] is not None:rights_need(rounded*executable>=D(inst['min_notional'].split()[0].replace('_','')),'native_min_notional_conflict')
            if omitted:rights_guarded_touch(db,ep,entry,level,row['seq'])
            qualified[oid]=a
            if len(examples)<16:examples.append(dict(oid=oid,intent_id=i['id'],parent=ep['id'],level=level,origin_method=origin['method'],actual_interval_native_writers=writer_count,actual_native_market_execution=execution,
                original_creation_remaining_hex=float(remaining).hex(),actual_admission_remaining_hex=float(rights_budget(ep,policy,level)).hex(),no_new_admission_clamp=True))
        except (KeyError,TypeError,RightsFactMissing) as error:missing.add(type(error).__name__+':'+str(error))
        except (ValueError,ArithmeticError,RightsPolicyViolation) as error:failures[str(error)]+=1
    totals=Counter()
    for (body,) in db.execute("SELECT body FROM fills ORDER BY CAST(json_extract(body,'$.sequence') AS INTEGER)"):
        fill=json.loads(body)
        if fill['action']!='SOL_ADD':continue
        actual_fills+=1;oid=fill['oid']
        try:
            if oid not in qualified:raise RightsFactMissing('qualified_admission_for_actual_SOL_ADD:'+oid)
            a=qualified[oid];level=str(fill['level']);before=get('sol_before',fill['native_event_id']);after=get('rights_after',fill['native_event_id'])
            if before is None or after is None:raise RightsFactMissing('actual_SOL_ADD_before_after_source_frames:'+fill['native_event_id'])
            b=before['episode'];z=after['episode']
            rights_need(b['id']==z['id']==fill['parent']==a['parent'] and int(a['level'])==int(fill['level']),'native_fill_parent_level_conflict')
            rights_need(D(fill['qty'])>0 and D(fill['px'])>0,'nonpositive_actual_native_fill')
            rights_need(fill['instrument']==a['native_initialized_order']['instrument'],'native_fill_instrument_conflict')
            expected=b['sol_add_filled_notional'].get(level,0.0)+float(fill['qty'])*float(fill['px'])
            rights_need(float(z['sol_add_filled_notional'][level]).hex()==expected.hex(),'native_partial_fill_consumption_update_conflict')
            totals[oid]+=D(fill['qty']);rights_need(totals[oid]<=D(a['native_initialized_order']['quantity']),'actual_native_fills_exceed_initialized_order')
        except (KeyError,TypeError,RightsFactMissing) as error:missing.add(type(error).__name__+':'+str(error))
        except (ValueError,ArithmeticError,RightsPolicyViolation) as error:failures[str(error)]+=1
    if capture is not None and (capture.get('attempts')!=capture.get('recorded') or capture.get('recorded')!=admissions):missing.add('admission_attempts_recorded_stream_count_mismatch')
    return dict(status='FAIL' if failures else ('UNKNOWN' if missing else 'PASS'),actual_SOL_ADD_fills=actual_fills,actual_admitted_orders=admissions,
        actual_qualified_orders=len(qualified),missing_required_fields=sorted(missing),failures=dict(failures),examples=examples,examples_capped_at=16,
        mechanism_status='NOT_TESTED_NO_ACTUAL_SOL_ADD' if admissions==actual_fills==0 else 'ACTUAL_V2_SOURCE_RIGHTS_EVIDENCE',
        initialized_order_never_ACK_credit=True,no_current_budget_clamp=True,no_new_P3_A0_rules=True,no_shadow_PnL=True)


def profile_read(path,db,owners,label,audit=None):
    bad=Counter();counts=Counter();last=None;state_hash=None;seq=0;quote_frames=0;checked_tp=0;first_cash=None
    authority=tp_authority(audit)
    rights_v2_tables(db)
    for table in ('fills','closed','position_trades','order_context','native_acks','sol_before'):
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
        rights_v2_frame(db,row,state,bad)
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
                    if any(x['instrument']!='BTCUSDT-PERP.P1SIM' or x['side']!=('LONG' if ep['side']==1 else 'SHORT') for x in positions):bad['P1_native_held_parent_side_or_instrument']+=1
                    entry=D(ep['entry_qty_exact'])/D('.001')
                    if entry!=entry.to_integral_value():bad['P1_noninteger_entry']+=1;continue
                    n=int(entry);first=n*17//80;two=n*17//40;grants={0:first,1:two-first,2:n-two}
                    actual_grants={int(k):v for k,v in ep['target_lots'].items()}
                    filled={int(k):v for k,v in ep['actual_tp_filled_lots'].items()};retired={int(k):v for k,v in ep['risk_retired_lots'].items()}
                    desired={i:grants[i]-filled.get(i,0)-retired.get(i,0) for i in range(3)}
                    if actual_grants!=grants or any(v<0 for v in desired.values()) or D(sum(desired.values()))*D('.001')!=held:bad['P1_grant_inventory_conservation']+=1
                    authorized=authority['references'].get((ep['id'],n))
                    prices=None
                    if authorized is None or authorized[0]>int(row['event_ns']):bad['P1_authorized_reference_missing']+=1
                    else:
                        try:prices=authorized_tp_prices(authorized[1],ma['raw_levels'][2],ep['side'])
                        except Exception:bad['P1_authorized_geometry_missing_or_invalid']+=1
                    actual={}
                    for oid,owner in state['method_a_active_owners'].items():
                        if owner['parent']!=ep['id']:continue
                        order=state['active_orders'].get(oid)
                        if order is None:bad['P1_owner_order_missing']+=1;continue
                        level=int(owner['level'])
                        ack=db.execute('SELECT body FROM native_acks WHERE id=?',(oid,)).fetchone()
                        ack=None if ack is None else json.loads(ack[0])
                        if level not in (0,1,2):bad['P1_invalid_target_level']+=1;continue
                        if prices is not None:
                            for issue in tp_order_errors(order,owner,ack,prices[level],ep['side']):bad[issue]+=1
                        if level in actual:bad['P1_duplicate_target_owner']+=1
                        if order['status'] not in ('ACCEPTED','PARTIALLY_FILLED') or not order['reduce_only'] or not owner['ack'] or oid in state['method_a_commands']:bad['P1_actual_latest_ACK_missing']+=1
                        actual[level]=D(order['leaves'])/D('.001')
                    if actual!={i:D(v) for i,v in desired.items() if v>0} or ma['coverage_ready'] is not True or ma['expected_cancels']:bad['P1_actual_TP_coverage']+=1
                    observed=db.execute('SELECT entry,tp0,tp1,tp2 FROM parent_actual WHERE id=?',(ep['id'],)).fetchone()
                    if observed is None or D(observed[0])!=D(ep['entry_qty_exact']):bad['P1_actual_entry_grant_source']+=1
                    if observed is not None and any(D(observed[i+1])!=D(filled.get(i,0))*D('.001') for i in range(3)):bad['P1_actual_TP_consumption_source']+=1
        if phase in ('AFTER_STRATEGY_on_order_accepted','AFTER_STRATEGY_on_order_updated'):
            order=row.get('native_order')
            if order is not None:
                history=order.get('native_history',[])
                if not any(item['id']==row['native_event_id'] and item['type'] in ('OrderAccepted','OrderUpdated') for item in history):bad['native_ACK_not_in_actual_history']+=1
                ack=dict(native_event_id=row['native_event_id'],price=order['price'],quantity=order['quantity'],strategy=order['strategy'],instrument=order['instrument'],side=order['side'])
                db.execute('INSERT OR REPLACE INTO native_acks VALUES (?,?)',(order['order_id'],json.dumps(ack,sort_keys=True)))
                if label=='P1' and row['native_event_type']=='OrderUpdated' and owners.get(order['order_id'],{}).get('action')=='BTC_REDUCE':
                    logged=authority['acks'].get(row['native_event_id'])
                    command=None if logged is None else authority['submits'].get((order['order_id'],str(logged['sequence'])))
                    if logged is None or command is None or D(logged['price'])!=D(order['price']) or D(logged['total'])!=D(order['quantity']) or D(command['price'])!=D(order['price']) or D(command['total'])!=D(order['quantity']):bad['P1_modify_ACK_not_authorized_current_price']+=1
        if phase=='BEFORE_STRATEGY_on_order_filled_NATIVE_CACHE_ALREADY_MUTATED' and row['native_event_type']=='OrderFilled':
            insert_unique(db,'sol_before',row['native_event_id'],dict(episode=state['episode'],sequence=seq),bad)
        if phase=='AFTER_STRATEGY_on_order_filled' and row['native_event_type']=='OrderFilled':
            oid=row['client_order_id'];context=db.execute('SELECT body FROM order_context WHERE id=?',(oid,)).fetchone()
            context=json.loads(context[0]) if context else {};raw=owners.get(oid,{})
            action=context.get('action',raw.get('action'));parent=context.get('parent');level=context.get('level',raw.get('level'))
            commission,currency=money(row['commission'])
            value=dict(native_event_id=row['native_event_id'],oid=oid,parent=parent,action=action,level=level,qty=row['last_qty'],
                commission=str(commission),currency=currency,ns=row['event_ns'],px=row['last_px'],sequence=seq,instrument=row['native_order']['instrument'])
            fresh=insert_unique(db,'fills',row['trade_id'],value,bad)
            if fresh and parent is not None and action in ('BTC_ENTRY','BTC_REDUCE'):
                db.execute('INSERT OR IGNORE INTO parent_actual VALUES (?,?,?,?,?)',(parent,'0','0','0','0'))
                column='entry' if action=='BTC_ENTRY' else 'tp'+str(level)
                if column not in ('entry','tp0','tp1','tp2'):bad['native_TP_level_unknown']+=1
                else:
                    old=db.execute('SELECT '+column+' FROM parent_actual WHERE id=?',(parent,)).fetchone()[0]
                    db.execute('UPDATE parent_actual SET '+column+'=? WHERE id=?',(str(D(old)+D(row['last_qty'])),parent))
            if action in ('BTC_ENTRY','BTC_REDUCE','SOL_ADD') and parent is None:bad['fill_parent_owner_missing']+=1
        if phase=='AFTER_STRATEGY_on_position_event' and row['native_event_type']=='PositionClosed':
            event=row.get('native_position_closed_event');position=row.get('native_position')
            if event is None or position is None or not position['is_closed'] or event['realized_pnl'] is None:
                bad['closed_native_position_evidence_missing']+=1;continue
            if event['realized_pnl']!=position['realized_pnl']:bad['closed_native_event_cache_money_conflict']+=1
            value=dict(position_id=event['position_id'],realized=event['realized_pnl'],commissions=position['commissions'])
            if insert_unique(db,'closed',row['native_event_id'],value,bad):
                for fill in position['native_fill_history']:
                    insert_unique(db,'position_trades',fill['trade_id'],dict(closed_event=row['native_event_id'],native_event_id=fill['event_id'],oid=fill['client_order_id'],qty=fill['qty'],commission=fill['commission'],px=fill['px']),bad)
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
        profile=profile_read(extras['protection_profile'],db,owners,label,a.get('method_a_tp_audit'))
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
        observer_pin=next(x for x in bound['freeze']['script_pins'] if Path(x['path']).name=='prefix_observer.py')
        rights=rights_v2_evidence(db,a,label,bound['profile'],observer_pin['sha256'])
        gates=dict(actual_os_exit0='PASS',complete_cash_reconciliation='PASS' if cashproof else 'UNKNOWN',signed_asset_funding_reconciliation='PASS' if fproof and signed==D(a['funding']['signed_amount']) else 'UNKNOWN',
            native_fee_reconciliation='PASS' if fees==fill_fees==D(a['native_fees']) and currencies_ok else 'UNKNOWN',
            native_3TP='NOT_APPLICABLE_LEGACY_CONTROL' if label=='P0' else ('PASS' if profile_good and profile['checked_P1_held_frames']>0 and a.get('method_a_tp_audit') else 'UNKNOWN'),
            ownership='PASS' if profile_good and fill_count==a['fills'] else 'UNKNOWN',continuous_settled_coverage='PASS' if complete_range and not bad else 'UNKNOWN',
            coherent_prefill_preopen_event_coverage='PASS' if o['status']=='PASS' and not o['unknown'] and native_epochs and native_pairs and not bad else 'UNKNOWN',
            source_config_data_comparable='PASS' if venue else 'UNKNOWN',rights_audit_complete=rights['status'] if profile_good and native_pairs else 'UNKNOWN',
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
            old_SOL_rights_evidence=rights,
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
