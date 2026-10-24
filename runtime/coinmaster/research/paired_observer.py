"""Read-only committed-native snapshot journal; never applies/replays a fill.

Private immutable native Position pickles follow the stock cache snapshot idiom.
Cash is native Money; UPNL is stock Position.unrealized_pnl(explicit Price).
Unknown mutation coverage is exported as UNKNOWN and blocks qualification.
"""
import bisect
import gzip
import hashlib
import json
import pickle
from decimal import Decimal as D
from pathlib import Path
from nautilus_trader.backtest.config import SimulationModuleConfig
from nautilus_trader.backtest.modules import SimulationModule
from nautilus_trader.model.data import QuoteTick
from coinmaster.research.minute_risk import DrawdownTracker

MINUTE=60_000_000_000


class CommittedNativeObserver(SimulationModule):
    def __init__(self, path: Path, seed, instruments, funding_journal=None):
        super().__init__(SimulationModuleConfig())
        self.instruments={i.id:i for i in instruments}
        self.journal=funding_journal
        self.file=gzip.open(path,"wt",compresslevel=1)
        self.sequence=0;self.epoch=0;self.last=None;self.last_mutation_ns=None
        self.seen_fills=set();self.funding_ids=set();self.pending_accounts=[]
        self.unknown=[];self.marks={};self.mark_times=[];self.previous_pair=None
        self.minute_source=None;self.settled_count=0;self.fill_count=0;self.funding_count=0
        self.events=DrawdownTracker(seed);self.settled=DrawdownTracker(seed)
        self.events.add(0,D(seed));self.settled.add(0,D(seed))
        self.final=None;self.account_count=0

    def register_venue(self, exchange):
        super().register_venue(exchange)
        self.msgbus.subscribe(topic="events.fills.*",handler=self.on_committed_fill)
        self.msgbus.subscribe(topic="events.account.*",handler=self.on_committed_account)

    def set_week(self, week):
        if self.mark_times:
            self.previous_pair=(self.mark_times[-1],self.marks[self.mark_times[-1]])
        ids=tuple(self.instruments)
        self.marks={(m.open_time_ms+60000)*1000000:
            {ids[0]:D(str(m.btc_mark["close"])),ids[1]:D(str(m.sol_mark["close"]))} for m in week}
        self.mark_times=sorted(self.marks)

    def _problem(self, reason):
        if reason not in self.unknown:self.unknown.append(reason)

    def _snapshot(self):
        account=self.exchange.get_account()
        if account is None or account.base_currency is None:
            return None
        balance=account.balance_total(account.base_currency)
        if balance is None:return None
        positions=[]
        for position in sorted(self.exchange.cache.positions_open(),key=lambda p:str(p.id)):
            if position.instrument_id not in self.instruments:
                raise ValueError("COHERENT_OBSERVER_FOREIGN_NATIVE_POSITION")
            inst=self.instruments[position.instrument_id]
            if inst.quote_currency!=account.base_currency:
                raise ValueError("COHERENT_OBSERVER_UNKNOWN_SETTLEMENT_CURRENCY")
            positions.append(pickle.dumps(position,protocol=pickle.HIGHEST_PROTOCOL))
        positions=tuple(positions)
        position_hash=hashlib.sha256(b"".join(positions)).hexdigest()
        cash=balance.as_decimal()
        signature=(str(cash),position_hash)
        return dict(cash=cash,positions=positions,position_hash=position_hash,signature=signature)

    def _pair(self, ns):
        i=bisect.bisect_right(self.mark_times,ns)-1
        if i>=0:return self.mark_times[i],self.marks[self.mark_times[i]]
        if self.previous_pair and self.previous_pair[0]<=ns:return self.previous_pair
        return None,None

    def _value(self,state,ns):
        source,prices=self._pair(ns)
        equity=state["cash"];details=[]
        if state["positions"] and prices is None:
            self._problem("MISSING_COMPLETED_PAIRED_MARK_SOURCE")
            return None,source,[]
        for raw in state["positions"]:
            position=pickle.loads(raw)
            inst=self.instruments[position.instrument_id]
            price=inst.make_price(prices[position.instrument_id])
            upnl=position.unrealized_pnl(price).as_decimal()
            equity+=upnl
            details.append(dict(position_id=str(position.id),instrument_id=str(position.instrument_id),
                quantity=str(position.quantity),side="LONG" if position.is_long else "SHORT",
                raw_mark=str(prices[position.instrument_id]),native_price=str(price),native_upnl=str(upnl)))
        return equity,source,details

    def _emit(self,kind,ns,state,*,identity=None,track=True,receipt_ns=None):
        equity,source,positions=self._value(state,ns)
        self.sequence+=1
        row=dict(sequence=self.sequence,epoch=self.epoch,kind=kind,event_ns=str(ns),
            receipt_ns=str(receipt_ns if receipt_ns is not None else ns),native_id=identity,
            mark_available_ns=str(source) if source is not None else None,
            cash=str(state["cash"]),native_positions_sha256=state["position_hash"],
            equity=str(equity) if equity is not None else None,positions=positions)
        self.file.write(json.dumps(row,separators=(",",":"))+"\n")
        if track and equity is not None:self.events.add(self.sequence,equity)
        return equity

    def on_committed_account(self,event):
        state=self._snapshot()
        if state is not None:
            self.pending_accounts.append((str(event.id),event.ts_event,state))
            self.account_count+=1

    def on_committed_fill(self,event):
        identity=str(event.trade_id)
        if identity in self.seen_fills:return
        self.seen_fills.add(identity);self.fill_count+=1
        state=self._snapshot()
        if self.last is None or state is None:
            self._problem("FILL_WITHOUT_COMPLETE_PRE_NATIVE_SNAPSHOT")
        else:
            self._emit("PRE_FILL_LAST_COMMITTED_NATIVE_COPY",event.ts_event,self.last,identity=identity)
            self.epoch+=1
            self._emit("POST_FILL_COMMITTED_NATIVE",event.ts_event,state,identity=identity)
        self.last=state;self.last_mutation_ns=event.ts_event
        # Native fill-associated account updates occur before this committed
        # post-position topic; transient cash/new+position/old pairs are not valued.
        self.pending_accounts=[]

    def _resolve_funding(self,ns):
        rows=self.journal.funding_cash_audit() if self.journal and self.pending_accounts else ()
        new=[r for r in rows if (r[0],r[1]) not in self.funding_ids]
        for row in new:
            key=(row[0],row[1]);self.funding_ids.add(key)
            match=next(((k,a) for k,a in enumerate(self.pending_accounts)
                if a[2]["cash"]==D(row[4]) and self.last is not None and
                   a[2]["position_hash"]==self.last["position_hash"]),None)
            if self.last is None or self.last["cash"]!=D(row[3]) or match is None:
                self._problem("FUNDING_MUTATION_EPOCH_NOT_EXACTLY_COVERED")
                continue
            index,(event_id,received,state)=match
            self._emit("PRE_FUNDING_COMMITTED_NATIVE_COPY",int(row[2]),self.last,identity=row[0])
            self.epoch+=1;self.funding_count+=1
            self._emit("POST_FUNDING_ACCOUNT_NATIVE",int(row[2]),state,identity=row[0],receipt_ns=received)
            self.last=state;self.last_mutation_ns=int(row[2])
            self.pending_accounts=self.pending_accounts[index+1:]
        current=self._snapshot()
        if self.last is not None and current is not None and current["signature"]!=self.last["signature"]:
            self._problem("UNOBSERVED_NATIVE_CASH_OR_POSITION_MUTATION")
        # Duplicate account publications with the same committed state are inert.
        if current is not None and all(a[2]["signature"]==current["signature"] for a in self.pending_accounts):
            self.pending_accounts=[]
        elif self.pending_accounts:
            self._problem("UNRESOLVED_NATIVE_ACCOUNT_PUBLICATION")

    def pre_process(self,data):
        if not isinstance(data,QuoteTick):return
        ns=data.ts_event
        self._resolve_funding(ns)
        current=self._snapshot()
        if current is None:
            self._problem("PREQUOTE_NATIVE_STATE_MISSING");return
        if self.last is None:self.last=current
        if current["signature"]!=self.last["signature"]:
            self._problem("PREQUOTE_NATIVE_STATE_EPOCH_MISMATCH")
        if self.minute_source is not None and ns>self.minute_source:
            if self.last_mutation_ns is not None and self.last_mutation_ns>self.minute_source:
                self._problem("NO_EXACT_PRIOR_SOURCE_SETTLED_WATERMARK")
            else:
                equity=self._emit("SETTLED_PRE_NEXT_SOURCE_WATERMARK",self.minute_source,self.last,
                                  track=False,receipt_ns=ns)
                if equity is not None:self.settled.add(self.minute_source,equity);self.settled_count+=1
        if self.minute_source is None or ns>self.minute_source:self.minute_source=ns
        self._emit("PREQUOTE_DIRECT_NATIVE",ns,current)
        self.last=current

    def process(self,ts_now):
        self._resolve_funding(ts_now)

    def finish_after_engine_end(self,ns):
        self._resolve_funding(ns)
        current=self._snapshot()
        if current is None:
            self._problem("TERMINAL_NATIVE_ACCOUNT_MISSING")
        else:
            if current["positions"]:self._problem("TERMINAL_NOT_NATIVE_FLAT")
            if self.exchange.cache.orders_open() or self.exchange.cache.orders_inflight():
                self._problem("TERMINAL_NATIVE_ORDERS_NONTERMINAL")
            self._emit("DIRECT_NATIVE_AFTER_ENGINE_END_RETURNED",ns,current)
            self.final=str(current["cash"]) if not current["positions"] else None
        self.file.flush()
        return self.report()

    def report(self):
        return dict(status="PASS" if not self.unknown else "UNKNOWN",unknown=list(self.unknown),
            sequence_count=self.sequence,mutation_epochs=self.epoch,native_unique_fills=self.fill_count,
            native_funding_transitions=self.funding_count,native_account_publications=self.account_count,
            settled_receipts=self.settled_count,event_drawdown=self.events.summary(),
            settled_drawdown=self.settled.summary(),terminal_actual_cash=self.final,
            basis="ACTUAL_NATIVE_CASH_AND_IMMUTABLE_NATIVE_POSITION_UPNL_AT_COMMON_COMPLETED_MARK",
            actual_intraminute_price_path_proven=False)

    def close(self):self.file.close()
    def log_diagnostics(self,logger):pass
    def reset(self):pass
