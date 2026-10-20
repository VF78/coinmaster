"""Synthetic native event-retention measurement, no historical market replay."""
from pathlib import Path
from decimal import Decimal as D
import json,sys,gc,os
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


from coinmaster.research.native_audit import NativeAuditArchive

def memory():
    return {k:int(v.strip().split()[0])*1024 for k,v in (x.split(':',1) for x in Path('/proc/self/smaps_rollup').read_text().splitlines()[1:]) if k in ('Rss','Pss','Private_Dirty')}

path=Path('reports/sol-corridor-113/memory-native-load-bounded.sqlite')
s=Load(config());e=engine(s,rate="1000000/00:00:01");out=[]
a=NativeAuditArchive(path,s)
try:
    run_ticks(e,[tick(BTC_PERP,1),tick(SOL_PERP,1)]);marks(s,2)
    s._domain.episode=Episode('storage-load',1,10000,1,h=10000)
    s._conditional_state(2)
    for count in (0,1000,3000,10000,30000):
        s.target=count
        while s.generated<count:
            first=s.generated+10
            run_ticks(e,[tick(SOL_PERP,t) for t in range(first,first+min(100,count-s.generated))])
            receipt=a.capture(e,s.generated+10)
            assert not e.cache.orders() and not e.cache.positions()
        gc.collect()
        account=e.cache.account_for_venue(BTC_PERP.id.venue)
        cash=account.balance_total().as_decimal()
        assert cash==D(10000)-D(s.generated)*D(".01")
        assert a.count("position")+a.count("position_snapshot")==s.generated//2
        row=dict(generated=s.generated,memory=memory(),cash=str(cash),account_events=len(account.events),
            native_orders=len(e.cache.orders()),native_positions=len(e.cache.positions()),
            native_snapshots=len(e.cache.position_snapshots()),disk_orders=a.count("order"),disk_account_events=a.count("account"),
            closed_lifecycles=a.count("position")+a.count("position_snapshot"),
            risk_rows=len(s.risk_first_sol_audit),fill_rows=len(s.fill_audit),
            mutable_contexts=len(a.contexts.current),db_bytes=path.stat().st_size)
        out.append(row);print(json.dumps(row),flush=True)
    a.freeze()
    exports={kind:a.export_orders(Path("reports/sol-corridor-113")/("memory-load-"+kind+".csv"),kind=="fills") for kind in ("orders","fills")}
    row=dict(stage="finite_export",memory=memory(),exports=exports,archive_sha=a.digest)
    out.append(row);print(json.dumps(row),flush=True)
    Path('reports/sol-corridor-113/memory-native-load-bounded.json').write_text(json.dumps(out,indent=2)+'\n')
finally:
    a.close();e.end();e.dispose()
