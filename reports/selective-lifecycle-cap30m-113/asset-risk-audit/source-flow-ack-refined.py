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
  if type(e).__name__ == "OrderSubmitted":
   # Model the already-completed native close awaiting this opening ACK.
   self._domain.episode.close_reason="REGIME"
   self._forced_close_reason="REGIME";self._group_close_reconciliation_pending=True
   self._reconcile_group_flat()
   self.events[-1]["post_reconcile_episode"]=self._domain.episode.id if self._domain.episode else None
  super().on_order_event(e)
 def _advance_current_day(self):pass
s=AckProbe(lifecycle_config());engine=native_engine(s)
engine.add_data([tick(SOL_PERP,1)]);engine.run(streaming=True);engine.clear_data()
engine.add_data([tick(SOL_PERP,2,p="1")]);engine.run(streaming=True);engine.clear_data()
print("CM113_ACK_REFINED="+json.dumps({"events":s.events,"pending":len(s._pending_by_order),"positions":len(s.cache.positions_open()),"episode":s._domain.episode.id if s._domain.episode else None,"native_fills":len(engine.trader.generate_order_fills_report())},sort_keys=True))
engine.end();engine.dispose()
