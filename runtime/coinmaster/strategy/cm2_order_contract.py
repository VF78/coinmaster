"""CM2 audited request rules only: no margin, account, money or execution model.
Official caps come from the frozen instrument profile. IOC classification and
reduce-only dust exception remain UNKNOWN; conservative choices are model rules.
"""
from dataclasses import dataclass
from decimal import Decimal as D, ROUND_DOWN, ROUND_FLOOR, ROUND_CEILING
from coinmaster.venues.production_preflight import _decimal_places, _significant_figures

MODEL_ID="CM2_BTC_MARKET_NATIVE_REQUEST_V1"
FRESH_NS=120_000_000_000  # OWN operational research choice, not a venue rule.
DRAIN_NS=120_000_000_000 # OWN operational research choice, not a venue rule.
REDUCE_FLOOR_POLICY="CONSERVATIVE_RESEARCH_MIN10_REDUCE_EXCEPTION_UNKNOWN"

def finite_positive(value):
    return isinstance(value,D) and value.is_finite() and value>0

def valid_price(spec,price):
    return (finite_positive(price) and _decimal_places(price)<=spec.max_price_decimals
        and (price==price.to_integral_value() or _significant_figures(price)<=spec.max_price_significant_figures))

def aggressive_price(spec,price,side):
    """Own intent rule: sell floor/buy ceil. Never an HL rounding mandate."""
    if not finite_positive(price) or side not in ("BUY","SELL"):
        raise ValueError("INVALID_PRICE_OR_SIDE")
    if price==price.to_integral_value():return price
    quantum=max(D(1).scaleb(-spec.max_price_decimals),
                min(D(1),D(1).scaleb(price.adjusted()-spec.max_price_significant_figures+1)))
    result=(price/quantum).to_integral_value(rounding=ROUND_CEILING if side=="BUY" else ROUND_FLOOR)*quantum
    if not valid_price(spec,result) or abs(result-price)>quantum:
        raise ValueError("PROTECTIVE_PRICE_FORMAT_OR_OWN_ONE_TICK_BAND")
    return result

def outward_price(spec, price, up):
    """Favourable limit / conservative BE threshold; always official price format."""
    if not finite_positive(price) or type(up) is not bool:
        raise ValueError("INVALID_OUTWARD_PRICE")
    quantum=max(D(1).scaleb(-spec.max_price_decimals),
        min(D(1),D(1).scaleb(price.adjusted()-spec.max_price_significant_figures+1)))
    value=(price/quantum).to_integral_value(rounding=ROUND_CEILING if up else ROUND_FLOOR)*quantum
    if not valid_price(spec,value):raise ValueError("OUTWARD_PRICE_FORMAT")
    return value


def request_cap(spec,intent,tif):
    if intent in ("MARKET","STOP_MARKET"):
        return spec.max_market_notional,"OFFICIAL_MARKET_INTENT_CAP_WIRE_CLASSIFICATION_UNKNOWN"
    if intent=="LIMIT" and tif=="IOC":
        return min(spec.max_market_notional,spec.max_limit_notional),"OWN_CONSERVATIVE_AMBIGUOUS_IOC_CAP_BACKEND_UNKNOWN"
    if intent=="LIMIT" and tif=="GTC":
        return spec.max_limit_notional,"OFFICIAL_LIMIT_GTC_REQUEST_CAP"
    raise ValueError("UNCLASSIFIED_REQUEST_INTENT")

@dataclass(frozen=True)
class RequestTerms:
    limit_price: D | None
    cap_reference_price: D
    minimum_reference_price: D
    cap: D
    classification: str

def request_terms(spec,reference_price,side,intent="MARKET",tif="IOC"):
    if not finite_positive(reference_price):raise ValueError("EXECUTABLE_REFERENCE_UNKNOWN")
    price=aggressive_price(spec,reference_price,side) if intent=="LIMIT" else None
    cap,classification=request_cap(spec,intent,tif)
    return RequestTerms(price,max(reference_price,price or reference_price),
        min(reference_price,price or reference_price),cap,classification)

def validate_request(spec,quantity,terms,intent,tif):
    """Validate actual normalized objects; no collateral/IM check here."""
    if not finite_positive(quantity):return False,"REQUEST_QUANTITY_UNKNOWN"
    if (not all(finite_positive(v) for v in (terms.cap_reference_price,terms.minimum_reference_price,terms.cap))
            or terms.minimum_reference_price>terms.cap_reference_price):
        return False,"REQUEST_REFERENCE_UNKNOWN"
    if intent in ("MARKET","STOP_MARKET") and terms.limit_price is not None:return False,"MARKET_HAS_UNEXPECTED_LIMIT_PRICE"
    if quantity<spec.min_quantity or quantity%spec.quantity_increment:return False,"REQUEST_QUANTITY_FORMAT"
    if intent=="LIMIT" and not valid_price(spec,terms.limit_price):return False,"REQUEST_PRICE_FORMAT"
    if quantity*terms.minimum_reference_price<spec.min_notional:return False,"CONSERVATIVE_RESEARCH_MIN_NOTIONAL"
    cap,classification=request_cap(spec,intent,tif)
    if terms.cap!=cap or terms.classification!=classification:return False,"REQUEST_CAP_IDENTITY"
    if quantity*terms.cap_reference_price>cap:return False,"REQUEST_MAX_NOTIONAL"
    return True,"REQUEST_CONTRACT_PASS_NOT_BACKEND_ACCEPTANCE_PROOF"

def bbo_status(quote,now):
    if quote is None or now<quote.ts_event or now-quote.ts_event>FRESH_NS:return False,"BBO_NATIVE_CLOCK_AGE"
    bid,ask=quote.bid_price.as_decimal(),quote.ask_price.as_decimal()
    if not finite_positive(bid) or not finite_positive(ask) or bid>ask:return False,"BBO_INVALID_OR_CROSSED"
    return True,"FRESH_NATIVE_CLOCK_BBO"

def risk_only_target(actual,target):
    if not actual or actual*target<=0:return D(0)
    return (D(1) if actual>0 else D(-1))*min(abs(actual),abs(target))

def drain_update(previous,now,required_zero_ids):
    """Start once/union scope; never reset a deadline per child/callback."""
    scope=sorted(set(required_zero_ids))
    if previous is None:
        return None if not scope else {"first_ns":now,"deadline_ns":now+DRAIN_NS,
            "scoped_zero_ids":scope,"reconcile_required":False}
    result={**previous,"scoped_zero_ids":sorted(set(previous["scoped_zero_ids"])|set(scope))}
    if now>=result["deadline_ns"]:result["reconcile_required"]=True
    return result

def validate_drain(value,allowed_ids):
    if value is None:return None
    if (set(value)!={"first_ns","deadline_ns","scoped_zero_ids","reconcile_required"}
        or type(value["first_ns"]) is not int or type(value["deadline_ns"]) is not int
        or value["first_ns"]<0 or value["deadline_ns"]!=value["first_ns"]+DRAIN_NS
        or type(value["reconcile_required"]) is not bool
        or not isinstance(value["scoped_zero_ids"],list) or not value["scoped_zero_ids"]
        or value["scoped_zero_ids"]!=sorted(set(value["scoped_zero_ids"]))
        or not set(value["scoped_zero_ids"]).issubset(set(allowed_ids))):
        raise ValueError("DRAIN_CHECKPOINT_INVALID")
    return value
