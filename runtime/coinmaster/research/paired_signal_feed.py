"""Immutable causal market-only payload reader; no parent/outcome calendar."""
from dataclasses import dataclass, asdict
from decimal import Decimal as D
from pathlib import Path
import csv
import hashlib

MINUTE=60_000_000_000
DAY=1440*MINUTE
H4=240*MINUTE


@dataclass(frozen=True)
class PairedSignal:
    decision_ns: int
    available_ns: int
    not_before_ns: int
    btc_close: D
    sol_close: D
    a: D | None
    atr_sol: D | None
    valid: bool
    b2_long: bool
    b2_short: bool
    f0_long: bool
    f0_short: bool
    k_long: D | None
    k_short: D | None
    open_o: D

    def owner_row(self):
        return {"t":self.decision_ns,"valid":self.valid,"a":self.a,"PB":self.btc_close,
            "PS":self.sol_close,"ATR_SOL":self.atr_sol,"B2_1":self.b2_long,
            "B2_-1":self.b2_short,"F0_1":self.f0_long,"F0_-1":self.f0_short,
            "K_1":self.k_long,"K_-1":self.k_short,"O":self.open_o}


def load_paired_signal_feed(path: Path, expected_sha256: str, start_ns: int, end_ns: int):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected_sha256:
        raise ValueError("PAIRED_FEED_SHA256_MISMATCH")
    result=[]; previous=None
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            t=int(row["decision_ns"])
            if t%H4 or (previous is not None and t!=previous+H4):
                raise ValueError("PAIRED_FEED_INCOMPLETE_OR_UNORDERED_H4")
            previous=t
            if int(row["available_ns"])!=t or int(row["not_before_ns"])!=t+MINUTE:
                raise ValueError("PAIRED_FEED_CLOCK_INVALID")
            if int(row["d1_last_return_end_ns"])>t-DAY:
                raise ValueError("PAIRED_FUTURE_D1_FEATURE")
            for asset in ("btc","sol"):
                if not int(row[asset+"_funding_previous_ns"])<int(row[asset+"_funding_last_ns"])<t:
                    raise ValueError("PAIRED_FUTURE_OR_UNORDERED_FUNDING_FEATURE")
            if not start_ns<=t<end_ns:
                continue
            bit=lambda name: row[name]=="1" if row[name] in ("0","1") else (_ for _ in ()).throw(ValueError("PAIRED_NONBOOLEAN_FLAG"))
            sb=D(row["sigma_btc_d1_30"]);ss=D(row["sigma_sol_d1_30"])
            beta=D(row["beta_d1_30"]);rho=D(row["rho_d1_30"])
            coeff=bit("risk_coefficients_valid") and all(x.is_finite() and x>0 for x in (sb,ss,beta,rho)) and rho<=1+D("1e-12")
            atr=D(row["sol_atr_h4_14"]) if row["sol_atr_h4_14"] else None
            valid=coeff and bit("sol_atr_valid") and atr is not None and atr.is_finite() and atr>0
            if valid and int(row["atr_last_h4_end_ns"])!=t:
                raise ValueError("PAIRED_ATR_CLOCK_INVALID")
            optional=lambda name:D(row[name]) if row[name] else None
            result.append(PairedSignal(t,t,t+MINUTE,D(row["btc_close"]),D(row["sol_close"]),
                D(".5")*sb/ss if coeff else None,atr,valid,
                bit("b2_pattern_valid") and bit("b2_long"),bit("b2_pattern_valid") and bit("b2_short"),
                bit("f0_pattern_valid") and bit("f0_long"),bit("f0_pattern_valid") and bit("f0_short"),
                optional("b2_long_k"),optional("b2_short_k"),D(row["f0_open_o"])))
    if not result:
        raise ValueError("PAIRED_EMPTY_PREFIX_FEED")
    return tuple(result)


def paired_feed_json_rows(rows):
    return [{k:str(v) if isinstance(v,D) else v for k,v in asdict(row).items()} for row in rows]
