"""Fixed V1 SOL market/episode decisions. Native cache remains quantity/money authority."""
from dataclasses import dataclass, asdict
from decimal import Decimal as D, localcontext, ROUND_HALF_EVEN, ROUND_FLOOR
from math import isfinite
from coinmaster.strategy.cm2_sol_volatility import PairedDailyClose, daily_volatility_coefficient, DAY_NS

MODEL = "CM2_SOL_WAVE_EXHAUSTION_RELATIVE_V1"
ZERO = D(0)


@dataclass(frozen=True)
class SolConfig:
    model: str = MODEL
    enabled: bool = False

    def __post_init__(self):
        if type(self.model) is not str or self.model != MODEL or type(self.enabled) is not bool:
            raise ValueError("FIXED_SOL_V1_MODEL_REQUIRED")


def parse_sol_config(policy):
    if "sol" not in policy:
        return None
    value = policy["sol"]
    if type(value) is not dict or set(value) != {"model", "enabled"}:
        raise ValueError("EXACT_SOL_V1_FIELDS_REQUIRED")
    return SolConfig(**value)


def policy_document(btc, sol):
    result = asdict(btc)
    if sol is not None:
        result["sol"] = asdict(sol)
    return result


def positive(x):
    return isinstance(x, D) and x.is_finite() and x > 0


def floor_lot(quantity, lot):
    if not positive(lot) or not isinstance(quantity, D) or not quantity.is_finite() or quantity < 0:
        raise ValueError("SOL_LOT_OR_QUANTITY_UNKNOWN")
    return (quantity / lot).to_integral_value(rounding=ROUND_FLOOR) * lot


@dataclass
class SolEpisode:
    sponsor: str
    btc_side: int
    side: int
    k: D
    sigma: D
    notional: D
    quantity: D
    accepted_ns: int
    permission: dict | None = None
    opening_live: bool = True
    native_filled: bool = False
    exit_reason: str | None = None


class SolPolicy:
    def __init__(self, config):
        if not isinstance(config, SolConfig) or not config.enabled:
            raise ValueError("ENABLED_TYPED_SOL_V1_REQUIRED")
        self.config = config
        self.daily = []
        self.exhaustion = None
        self.gate_parent = None
        self.gate_truth = False
        self.gate_spent = False
        self.episode = None

    def accept_daily(self, close_ns, btc_close, sol_close, receipt_ns):
        if (type(close_ns) is not int or close_ns % DAY_NS or close_ns > receipt_ns
                or type(btc_close) is not str or type(sol_close) is not str
                or not positive(D(btc_close)) or not positive(D(sol_close))
                or self.daily and close_ns != self.daily[-1].close_ns + DAY_NS):
            raise ValueError("SOL_EXACT_CAUSAL_PAIRED_D1_REQUIRED")
        self.daily.append(PairedDailyClose(close_ns, btc_close, sol_close))
        self.daily = self.daily[-61:]

    def sync_parent(self, parent_id):
        if parent_id != self.gate_parent:
            self.gate_parent, self.gate_truth, self.gate_spent, self.exhaustion = parent_id, False, False, None

    def observe_wave(self, parent, *, native_btc, bid, ask, source_ns, receipt_ns):
        self.sync_parent(parent.id if parent else None)
        if (parent is None or parent.close_reason or not positive(parent.planref)
                or not native_btc or (1 if native_btc > 0 else -1) != parent.side
                or not positive(bid) or not positive(ask) or bid > ask
                or type(source_ns) is not int or source_ns > receipt_ns):
            return False
        if self.exhaustion is not None:
            return True
        level = D(str(parent.levels[0]))
        if not level.is_finite() or level < 0:
            return False
        price = bid if parent.side == 1 else ask
        with localcontext() as ctx:
            ctx.prec = 50
            ctx.rounding = ROUND_HALF_EVEN
            reached = D(parent.side) * (price / parent.planref - 1) >= level
        if reached:
            self.exhaustion = dict(parent_id=parent.id, side=parent.side,
                planref=parent.planref, level=level, source_ns=source_ns,
                receipt_ns=receipt_ns, executable_price=price)
        return reached

    def observe_gate(self, parent_id, truth):
        self.sync_parent(parent_id)
        if truth is None:
            return False
        if type(truth) is not bool:
            raise ValueError("SOL_GATE_TRISTATE_REQUIRED")
        self.gate_truth = truth
        if not truth:self.gate_spent = False
        return truth and not self.gate_spent

    def commit_opportunity(self):
        if self.gate_truth is not True:
            raise ValueError("SOL_ACCEPTED_OPPORTUNITY_NOT_TRUE")
        self.gate_spent = True

    def opening_candidate(self, *, sponsor, btc_side, native_btc_notional, sigma,
                          executable_price, lot, now):
        k = daily_volatility_coefficient(self.daily, decision_ns=now)
        if (not sponsor or btc_side not in (-1, 1) or k is None
                or not positive(sigma) or not positive(native_btc_notional)
                or not positive(executable_price)):
            return None
        with localcontext() as ctx:
            ctx.prec = 50
            ctx.rounding = ROUND_HALF_EVEN
            notional = native_btc_notional / k
            quantity = floor_lot(notional / executable_price, lot)
        return SolEpisode(sponsor, btc_side, -btc_side, k, sigma, notional, quantity, now) if quantity else None

    def remaining(self, *, native_btc_notional, executable_price, lot, actual_sol, pending_growth):
        ep = self.episode
        if ep is None or not ep.opening_live or ep.exit_reason:
            return ZERO
        if any(not isinstance(x, D) or not x.is_finite() or x < 0
               for x in (native_btc_notional, actual_sol, pending_growth)) or not positive(executable_price):
            raise ValueError("SOL_CURRENT_OPENING_CAP_UNKNOWN")
        with localcontext() as ctx:
            ctx.prec = 50
            ctx.rounding = ROUND_HALF_EVEN
            cap = min(ep.quantity, floor_lot(ep.notional / executable_price, lot),
                floor_lot(native_btc_notional / ep.k / executable_price, lot))
            return max(ZERO, cap - actual_sol - pending_growth)

    def retire_opening(self):
        if self.episode is not None:
            self.episode.opening_live = False

    def request_exit(self, reason):
        if self.episode is not None:
            self.episode.exit_reason = self.episode.exit_reason or reason
            self.retire_opening()
            return True
        return False

    def market_end(self, sponsor, reason):
        return (reason in ("REGIME", "TRAIL") and self.episode is not None
            and self.episode.sponsor == sponsor and self.request_exit("BTC_MARKET_" + reason))

    def relative_exit(self, *, relative, mu, daily_ns, now):
        ep = self.episode
        if ep is None or daily_ns != (now // DAY_NS) * DAY_NS:
            return False
        if any(x is None or not isfinite(x) for x in (relative, mu)):
            return False
        with localcontext() as ctx:
            ctx.prec = 50
            ctx.rounding = ROUND_HALF_EVEN
            z = (D(str(relative)) - D(str(mu))) / ep.sigma
            return self.request_exit("SOL_RELATIVE_CONVERGENCE") if D(ep.side) * z >= D("-.125") else False

    def native_fill(self):
        if self.episode is not None:
            self.episode.native_filled = True

    def reconcile(self, *, native_flat, owners_terminal):
        if (self.episode is not None and native_flat and owners_terminal
                and (self.episode.native_filled or not self.episode.opening_live)):
            self.episode = None

    def snapshot(self):
        return dict(model=MODEL, daily=[asdict(x) for x in self.daily],
            exhaustion=self.exhaustion, gate_parent=self.gate_parent,
            gate_truth=self.gate_truth, gate_spent=self.gate_spent, episode=asdict(self.episode) if self.episode else None)

    def restore(self, state, receipt_ns):
        if set(state) != {"model", "daily", "exhaustion", "gate_parent", "gate_truth", "gate_spent", "episode"} or state["model"] != MODEL:
            raise ValueError("SOL_CHECKPOINT_FIELDS")
        rebuilt = SolPolicy(self.config)
        for row in state["daily"]:
            rebuilt.accept_daily(row["close_ns"], row["btc_close"], row["sol_close"], receipt_ns)
        if (len(state["daily"]) > 61 or type(state["gate_truth"]) is not bool or type(state["gate_spent"]) is not bool
                or state["gate_spent"] and not state["gate_truth"]):
            raise ValueError("SOL_CHECKPOINT_DAILY_OR_GATE")
        ep = SolEpisode(**state["episode"]) if state["episode"] is not None else None
        if ep is not None and (ep.side != -ep.btc_side or ep.side not in (-1, 1)
                or not all(positive(x) for x in (ep.k, ep.sigma, ep.notional, ep.quantity))
                or ep.accepted_ns > receipt_ns or type(ep.opening_live) is not bool
                or type(ep.native_filled) is not bool):
            raise ValueError("SOL_CHECKPOINT_EPISODE")
        fact = state["exhaustion"]
        if fact is not None and (fact["parent_id"] != state["gate_parent"]
                or fact["side"] not in (-1, 1) or not positive(fact["planref"])
                or not positive(fact["executable_price"]) or fact["level"] < 0
                or not fact["source_ns"] <= fact["receipt_ns"] <= receipt_ns):
            raise ValueError("SOL_CHECKPOINT_MARKET_FACT")
        self.daily, self.exhaustion = rebuilt.daily, fact
        self.gate_parent, self.gate_truth, self.gate_spent, self.episode = state["gate_parent"], state["gate_truth"], state["gate_spent"], ep
