from pathlib import Path
R=Path('/root/.openclaw/workspace/coinmaster/coinmaster/research-worktrees/residual-recovery-20261023')
p=R/'runtime/coinmaster/strategy/residual_recovery.py';s=p.read_text().replace("            t['targets_need_requeue']=False;self._queue_confirmed_btc_targets(None,len(self._bars)-1,ns)","            t['targets_need_requeue']=False\n            if self._hb_position(self.config.btc_id) is not None:self._queue_confirmed_btc_targets(None,len(self._bars)-1,ns)")
needle='    def _c1_discard_increase(self,i,ns):';s=s.replace(needle,"    def _c1_terminal_flat(self,ns):\n        if not self.config.research_residual_recovery or self._c1_state is None:return\n        if self.cache.positions_open() or self.cache.orders_open() or self.cache.orders_inflight() or self._pending_by_order or self._queued_intents:return\n        self._c1_log('TERMINAL_FLAT_CONFIRMED',ns,credit_expired=self._c1_state['credit'],native_positions=0,native_orders=0,native_inflight=0,pending=0,queued=0,H=str(self._c1_peak))\n        self._c1_state=None\n\n    def _c1_export_terminal(self):\n        t=self._c1_state\n        return dict(active_hold=bool(t and t['state']!='RELEASED'),credit=t['credit'] if t else 0,state=t['state'] if t else 'IDLE',group=t['group'] if t else None,H=str(self._c1_peak),native_positions=len(self.cache.positions_open()),native_orders=len(self.cache.orders_open()),native_inflight=len(self.cache.orders_inflight()),pending=len(self._pending_by_order),queued=len(self._queued_intents))\n\n"+needle);p.write_text(s)
p=R/'runtime/coinmaster/strategy/wave_overlay.py';s=p.read_text();needle='        self.terminal_lifecycle["status"] = "FLAT"\n\n    def reporting_state';assert needle in s;s=s.replace(needle,'        self.terminal_lifecycle["status"] = "FLAT"\n        self._c1_terminal_flat(self.clock.timestamp_ns())\n\n    def reporting_state');s=s.replace('        self._reconcile_terminal_flat()\n        return {','        self._reconcile_terminal_flat()\n        if self.terminal_lifecycle["status"]=="FLAT":self._c1_terminal_flat(self.clock.timestamp_ns())\n        return {');p.write_text(s)
p=R/'runtime/coinmaster/research/native_baseline.py';s=p.read_text().replace('result["c1_denial_counts"]=strategy.c1_denials','result["c1_denial_counts"]=strategy.c1_denials\n            result["c1_terminal_state"]=strategy._c1_export_terminal()');p.write_text(s)
p=R/'runtime/tests/test_native_residual_recovery.py';s=p.read_text();s+='''

def test_terminal_native_flat_burns_credit_and_exports_no_active_hold():
 s,e,ep=held()
 try:
  cut(s,e);assert s._c1_state['credit']>0
  s._submit_terminal_closes()
  for n in range(1,10):run_ticks(e,[tick(BTC_PERP,4000+n,'55'),tick(SOL_PERP,4000+n,'100')])
  s.reporting_state();out=s._c1_export_terminal()
  assert not out['active_hold'] and out['credit']==0 and out['native_positions']==0 and out['pending']==0
  assert any(x['event']=='TERMINAL_FLAT_CONFIRMED' for x in s.c1_audit)
 finally:e.end();e.dispose()
''';p.write_text(s)
print('Native-flat TP gate and terminal C1 witness complete')
