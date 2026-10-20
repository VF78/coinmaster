"""Synthetic native event-retention measurement, no historical market replay."""
from pathlib import Path
from decimal import Decimal as D
import json,sys,tracemalloc,gc
from test_native_sol_corridor import Observed,config,engine,Episode,BTC_PERP,SOL_PERP,tick,run_ticks,marks

class Load(Observed):
    generated=0;target=0
    def _conditional_check(self,q):pass  # isolate storage/real native execution from economic scenarios
    def on_quote_tick(self,q):
        super().on_quote_tick(q)
        if q.instrument_id!=SOL_PERP.id or self.generated>=self.target:return
        add=self.generated%2==0
        i=self._domain._intent(self._domain.episode,'SOL_ADD' if add else 'SOL_EXIT',-1 if add else 1,None,quantity=.1,reason='CONDITIONAL_NET_ADD' if add else 'CONDITIONAL_NET_EXIT')
        if add:self._conditional['original_attempts'][i.id]=()
        self._conditional_physical=True
        try:self._submit_intent(i,100,100,None,0,ts_now=q.ts_event)
        finally:self._conditional_physical=False
        self.generated+=1

def deep_size(value,seen=None):
    seen=set() if seen is None else seen
    if id(value) in seen:return 0
    seen.add(id(value));n=sys.getsizeof(value)
    if isinstance(value,dict):n+=sum(deep_size(k,seen)+deep_size(v,seen) for k,v in value.items())
    elif isinstance(value,(list,tuple,set)):n+=sum(deep_size(v,seen) for v in value)
    return n

def memory():
    values={k:int(v.strip().split()[0])*1024 for k,v in (x.split(':',1) for x in Path('/proc/self/smaps_rollup').read_text().splitlines()[1:]) if k in ('Rss','Pss','Private_Dirty')}
    return values

s=Load(config());e=engine(s,rate="1000000/00:00:01");out=[]
try:
    run_ticks(e,[tick(BTC_PERP,1),tick(SOL_PERP,1)]);marks(s,2)
    s._domain.episode=Episode('storage-load',1,10000,1,h=10000)
    s._conditional_state(2);tracemalloc.start()
    for count in (0,200,1000,3000):
        s.target=count
        while s.generated<count:
            first=s.generated+10
            run_ticks(e,[tick(SOL_PERP,t) for t in range(first,first+min(100,count-s.generated))])
        gc.collect()
        account=e.cache.account_for_venue(BTC_PERP.id.venue)
        lists={'risk_audit':s.risk_first_sol_audit,'order_audit':s._order_audit,'fill_audit':s.fill_audit,'seen_trade_ids':s._seen_trade_ids}
        row={'native_orders':len(e.cache.orders()),'native_positions':len(e.cache.positions()),'account_events':len(account.events),'generated':s.generated,'cash':str(account.balance_total().as_decimal()),'native_fees':str(sum((D(x['commission']) for x in s.fill_audit),D(0))),'python_history_count':{k:len(v) for k,v in lists.items()},'python_history_deep_bytes':{k:deep_size(v) for k,v in lists.items()},'memory':memory(),'tracemalloc_current_peak':tracemalloc.get_traced_memory(),'traced_top_files':[{'file':str(x.traceback[0]),'bytes':x.size,'count':x.count} for x in tracemalloc.take_snapshot().statistics('filename')[:8]]}
        assert account.balance_total().as_decimal()==D(10000)-sum((D(x['commission']) for x in s.fill_audit),D(0))
        out.append(row);print(json.dumps(row),flush=True)
    Path('reports/sol-corridor-113/memory-native-load-before.json').write_text(json.dumps(out,indent=2)+'\n')
finally:e.end();e.dispose()
