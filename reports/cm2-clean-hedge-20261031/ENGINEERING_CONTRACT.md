# Frozen engineering contract

Fixture ID cm2-connected-native-v1. Exactly one BacktestEngine constructor, inside run_fixture only. UTC start_ns1725148800000000000, end_ns1725181200000000000 (nine hours). This synthetic execution test is not a benchmark or income result. No constructor has yet run.

Hour0: long BTC breakout, load4. Hour1/2: adverse confirmations; open opposite SOL. One aggressive SOL limitIOC delegates to pinned stock LimitOrderPartialFillModel (max5 contracts), requiring actual partial and CANCELED native terminal before residual target submission. Hour3: positive BTC harvest core.5; held SOL must reduce before a BTC reduction that would flip factor. Hour4: protective close and SOL orphan drain. Hour5: new short parent. Hour6: positive short harvest. Hour7: opposite SOL long. Hour8: stop and drain. Hour9: terminal boundary.

Fixed quote paths (BTC/SOL): 1000/100 through minute179;1070/90 through239;950/105 through359;880/105 through419;880/110 through479;980/100 to540. Both bid/ask equal. Funding at150m: BTC+.0001×1000, SOL+.0001×100; expected first posting total−1 USDC for40BTC long/300SOL short. At450m: BTC+.0001×880 and SOL+.0001×110 on actual held inventory. All postings use existing native funding module/journal.

Independent arithmetic at confirmed terminal flat: gross=−Σ(signed native fill quantity×fixed quote price); per-fill expected commission=Money(quantity×fixed price×.000432,commission currency), preserving native quantum; expected cash=10000+gross−sum(expected per-fill commission)+signed native funding. Native cash, commissions and funding are independently compared. No manually altered cash or invented fill.

Required actual native checks: both BTC order sides, multiple actual parents, real positive harvest, SOL fills, real partial native order and canceled terminal, funding4 postings, first funding−1, terminal flat with no inflight orders, exact fee/cash equations, ordinary SOL-first stage. The identical neutral minute observer and committed observer must receive callbacks; minute watermark rows540×3 and coherent statusPASS are required.

Before execution, constructor-free32+ regressions cover prefix causality, same-availability quote deferral, scaling, signs, buffer/guard, finite unknown/control targets, held/pending, proposed future factor cap, aggregate margin tiers, lease inheritance and durable budget gates. Actual native cancel/fill races, denied/unknown ACK and restart replay remain UNKNOWN when not forced by this fixture. No live recovery claim is authorized.

Reusable foreground command:
PYTHONPATH=<frozen-runtime> <pinned-python> -m coinmaster.research.cm2_runner --request <engineering-request.json> --resource-receipt <root-receipt.json> --run

Without --run, preflight constructs no engine/counts no attempt. Missing R2_RELEASED, own-stage GO, freeze/review/resource gates or busy global lease cause HOLD/count0. Registration under own durable ledger lock precedes the child. The sanitized child inherits the exact global lease FD; parent never explicitly unlocks its shared description. STARTED, failure, elapsed, exit and true child ru_maxrss are retained. No budget reset across v1.1.
