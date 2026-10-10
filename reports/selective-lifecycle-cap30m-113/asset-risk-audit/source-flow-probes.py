import json
from decimal import Decimal as D
from datetime import UTC,datetime,timedelta
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import OrderSide,TimeInForce
from coinmaster.domain.wave_overlay import Episode,DailyBar,Features
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP
from test_wave_native_integration import lifecycle_config,native_engine

def tick(i,t,size=1000,p="100"):
 return QuoteTick(i.id,i.make_price(D(p)),i.make_price(D(p)),i.make_qty(D(size)),i.make_qty(D(size)),t,t)
class AckProbe(WaveOverlayStrategy):
 def __init__(self,c):
  super().__init__(c);self.once=False;self.events=[]
 def on_quote_tick(self,t):
  if not self.once:
   self.once=True;self._domain.episode=Episode("ack",1,10000,1.0)
   x=self._domain._intent(self._domain.episode,"SOL_ADD",1,0,quantity=1)
   o=self.order_factory.limit(SOL_PERP.id,OrderSide.BUY,SOL_PERP.make_qty(D(1)),SOL_PERP.make_price(D(1)),time_in_force=TimeInForce.GTC)
   self._pending_by_order[str(o.client_order_id)]=x
   self._sigma_by_order[str(o.client_order_id)]=None;self._decision_index_by_order[str(o.client_order_id)]=0
   self.submit_order(o)
 def on_order_event(self,e):
  o=self.cache.order(e.client_order_id)
  self.events.append({"event":type(e).__name__,"status":str(o.status) if o else None,"open":len(self.cache.orders_open()),"pending":len(self._pending_by_order)})
  super().on_order_event(e)
 def _advance_current_day(self):pass
s=AckProbe(lifecycle_config());engine=native_engine(s)
engine.add_data([tick(SOL_PERP,1)]);engine.run(streaming=True);engine.clear_data()
s._domain.episode.close_reason="REGIME";s._begin_forced_close("REGIME")
s._group_close_reconciliation_pending=True;s._reconcile_group_flat()
ack={"events":s.events,"after_ordinary_cancel":{"pending":len(s._pending_by_order),"open":len(s.cache.orders_open()),"episode":s._domain.episode.id if s._domain.episode else None,"forced":s._forced_close_reason}}
engine.end();engine.dispose()
class HalfProbe(WaveOverlayStrategy):
 def __init__(self,c):super().__init__(c);self.n=0;self.result=None
 def _tier_allows_increase(self,*a):return True
 def on_quote_tick(self,t):
  self.n+=1
  if self.n==1:
   self._domain.episode=Episode("half",1,10000,1.0,btc_entry_vwap=100,btc_initial_qty=1)
   x=self._domain._intent(self._domain.episode,"SOL_ADD",1,0,quantity=1000)
   self._submit_intent(x,1,1,None,0,ts_now=t.ts_event)
  elif self.n==2:
   self._domain.episode.sol_half_target_lots=5000
   x=self._domain._intent(self._domain.episode,"SOL_HALF_EXIT",-1,None,quantity=500,reason="SOL_Z_HALF_EXIT")
   self._submit_intent(x,1,1,None,0,ts_now=t.ts_event)
  else:super().on_quote_tick(t)
 def _advance_current_day(self):
  e=self._domain.episode
  if e and e.sol_half_done:
   f=Features(1,1,1,0,0,1,0.1)
   intents=self._domain._sol_exits(e,f,self._bars[1],1,z=0.1)
   self.result={"stored_half_index":e.sol_half_decision_index,"actual_completion_index":len(self._bars)-1,"next_actions_same_completion_callback":[x.action for x in intents],"native_remaining":str(self.cache.positions_open()[0].quantity)}
s=HalfProbe(lifecycle_config());engine=native_engine(s)
engine.add_data([tick(SOL_PERP,1,p="1"),tick(SOL_PERP,2,250,"1")]);engine.run(streaming=True);engine.clear_data()
now=datetime(2024,1,1,tzinfo=UTC)
s._bars=[DailyBar(now+timedelta(days=j),now+timedelta(days=j+1),now+timedelta(days=j+1),100,100,1) for j in range(2)]
engine.add_data([tick(SOL_PERP,61000000002,p="1")]);engine.run(streaming=True);engine.clear_data()
half={"result":s.result,"half_fill_quantities":[x["qty"] for x in s.fill_audit if x["action"]=="SOL_HALF_EXIT"],"half_fill_count":sum(x["action"]=="SOL_HALF_EXIT" for x in s.fill_audit)}
engine.end();engine.dispose()
print("CM113_PROBE_RESULT="+json.dumps({"ack":ack,"half":half},sort_keys=True))
