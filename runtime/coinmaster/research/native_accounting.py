"""Read-only native lifecycle export: native cache history, never PnL reconstruction."""
import hashlib
import json


def native_position_lifecycles(cache):
    """NETTING reuses IDs; archived native snapshots retain older closed lives."""
    rows={};duplicate_copies=0;unknown=[]
    snapshots=cache.position_snapshots()
    current=cache.positions()
    for source,positions in (("NATIVE_CACHE_SNAPSHOT",snapshots),("NATIVE_CACHE_CURRENT",current)):
        for position in positions:
            events=position.events
            original_id=str(events[0].position_id) if events and events[0].position_id is not None else str(position.id)
            fills=[(str(e.trade_id),int(e.ts_event),str(e.last_qty),str(e.last_px),str(e.commission)) for e in events]
            digest=hashlib.sha256(json.dumps(fills,separators=(",",":")).encode()).hexdigest()
            key=(original_id,int(position.ts_opened),int(position.ts_closed),str(position.opening_order_id),digest)
            row=dict(position_id=original_id,native_copy_id=str(position.id),instrument_id=str(position.instrument_id),
                opened_ns=str(position.ts_opened),closed_ns=str(position.ts_closed),opening_order_id=str(position.opening_order_id),
                native_event_count=len(events),native_fill_lifecycle_sha256=digest,closed=position.is_closed,
                realized_pnl=str(position.realized_pnl.as_decimal()) if position.realized_pnl is not None else None,
                native_commissions=[str(c) for c in position.commissions()],sources=[source])
            if key in rows:
                old=rows[key]
                if (old['realized_pnl'],old['native_commissions'],old['closed'])!=(row['realized_pnl'],row['native_commissions'],row['closed']):
                    unknown.append('DUPLICATE_LIFECYCLE_NATIVE_VALUES_DISAGREE')
                old['sources'].append(source);duplicate_copies+=1
            else:rows[key]=row
    return dict(positions=list(rows.values()),native_snapshot_count=len(snapshots),native_current_count=len(current),
        unique_lifecycles=len(rows),duplicate_native_copies=duplicate_copies,unknown=unknown,
        identity='ORIGINAL_FILL_POSITION_ID+OPENED_NS+CLOSED_NS+OPENING_ORDER_ID+NATIVE_FILL_LIFECYCLE_SHA256')
