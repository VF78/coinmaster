"""Immutable inputs to the existing C1 policy; no execution or PnL model."""
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class C1PositionInput:
    instrument_id: str
    position_id: str
    opened_ns: int
    is_long: bool
    quantity: Decimal
    step: Decimal
    mark: Decimal
    mark_ns: int
    native_pnl: Decimal

    def __post_init__(self):
        if (not self.instrument_id or not self.position_id or type(self.opened_ns) is not int
            or type(self.mark_ns) is not int or self.mark_ns<0 or type(self.is_long) is not bool
            or any(not isinstance(x,Decimal) or not x.is_finite() for x in (self.quantity,self.step,self.mark,self.native_pnl))
            or min(self.quantity,self.step,self.mark)<=0 or self.quantity%self.step):
            raise ValueError('C1_NATIVE_POSITION_INPUT_INVALID')

@dataclass(frozen=True)
class C1DecisionInput:
    equity: Decimal
    source_available_ns: int
    decision_ns: int
    fill_epoch: int
    native_revision: int
    ws_epoch: int
    account_event_id: str
    positions: tuple[C1PositionInput,...]

    def __post_init__(self):
        if (not isinstance(self.equity,Decimal) or not self.equity.is_finite() or self.equity<=0
            or not 0<self.source_available_ns<self.decision_ns or not self.account_event_id
            or any(type(v) is not int or v<0 for v in (self.fill_epoch,self.native_revision,self.ws_epoch))
            or not isinstance(self.positions,tuple) or any(not isinstance(p,C1PositionInput) for p in self.positions)
            or len({p.instrument_id for p in self.positions})!=len(self.positions)):
            raise ValueError('C1_DECISION_INPUT_INVALID')
