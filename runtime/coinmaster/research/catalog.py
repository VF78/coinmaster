"""Small checked-in projection of immutable native research evidence.

Large reports remain ignored local artifacts.  This catalog never promotes a
diagnostic result to paper/live and records exactly which hash can unlock a
local detail projection.
"""
from __future__ import annotations

RESEARCH_CATALOG = (
    {
        "id": "bybit-reporting-v2-v0", "kind": "baseline", "title": "Original v0 — reporting-v2", "classification": "NOT_FAITHFUL_DIAGNOSTIC", "selected": False,
        "artifact": "runs/native-diagnostic-v0-canonical-reporting-v2.json", "sha256": "5f9408b65ae39a2d2d369d57db188bb25612ca6de5024a91e80963b64cc00322",
        "interval": "[2024-09-01,2026-09-01)", "warmup": "730d feature-only", "settled_total": "63325.93791898", "interval_cash": "61535.30022708", "roi": "5.332593791898", "drawdown_percent": "0.9067596926568427229058997829", "fees": "219559.24998770", "fills": 478, "funding": 2441, "liquidations": 0,
        "limitations": ["NOT_FAITHFUL_DIAGNOSTIC", "terminal settlement is post-boundary", "historical fee/tier and intraminute fidelity unknown"], "supersession": "Original v0 retained separately; reporting-v2 replaces prior reporting schema.",
    },
    {
        "id": "bybit-reporting-v2-selected-7.5", "kind": "candidate", "title": "Selected diagnostic candidate — BTC multiplier 7.5", "classification": "NOT_FAITHFUL_DIAGNOSTIC", "selected": True,
        "artifact": "runs/native-optimizer-canonical-reporting-v2.json", "sha256": "aa546527bbb18df6206ecb4f1bce9c21e28a6837d1d2a7e1572debd8c76faa40",
        "interval": "[2024-09-01,2026-09-01)", "warmup": "730d feature-only", "settled_total": "125198.28909680", "interval_cash": "122240.20258750", "roi": "11.51982890968", "drawdown_percent": "0.7857106650990000759821010922", "fees": "237674.38855060", "fills": 478, "funding": 2441, "liquidations": 0,
        "limitations": ["selected only within diagnostic assumptions", "not paper default", "not live-rankable"], "supersession": "Supersedes reporting-only interpretation of dfd6f4c pass.",
    },
    {
        "id": "bybit-reporting-v2-candidate-8.25", "kind": "candidate", "title": "Diagnostic comparison — BTC multiplier 8.25", "classification": "NOT_FAITHFUL_DIAGNOSTIC", "selected": False,
        "artifact": "runs/native-optimizer-canonical-reporting-v2.json", "sha256": "aa546527bbb18df6206ecb4f1bce9c21e28a6837d1d2a7e1572debd8c76faa40",
        "interval": "[2024-09-01,2026-09-01)", "warmup": "730d feature-only", "settled_total": "90843.78155857", "interval_cash": "88485.90461457", "roi": "8.084378155857", "drawdown_percent": "0.8510973902789763737006247073", "fees": "230687.68171590", "fills": 478, "funding": 2441, "liquidations": 0,
        "limitations": ["diagnostic comparison only", "not live-rankable"], "supersession": "None.",
    },
    {
        "id": "bybit-reporting-v2-excluded-9.75", "kind": "candidate", "title": "Excluded — BTC multiplier 9.75", "classification": "LIQUIDATED_EARLY_CUTOFF", "selected": False,
        "artifact": "runs/native-optimizer-canonical-reporting-v2.json", "sha256": "aa546527bbb18df6206ecb4f1bce9c21e28a6837d1d2a7e1572debd8c76faa40",
        "interval": "[2024-09-01,2026-09-01)", "warmup": "730d feature-only", "settled_total": "13296.92456772", "interval_cash": "13296.92456772", "roi": "0.329692456772", "drawdown_percent": "0.9647557317053806807599004287", "fees": "67497.12162850", "fills": 133, "funding": 614, "liquidations": 1,
        "limitations": ["authoritative liquidation lockout", "excluded from candidate eligibility"], "supersession": "None.",
    },
    {
        "id": "bybit-reporting-v2-excluded-10.5", "kind": "candidate", "title": "Excluded — BTC multiplier 10.5", "classification": "LIQUIDATED_EARLY_CUTOFF", "selected": False,
        "artifact": "runs/native-optimizer-canonical-reporting-v2.json", "sha256": "aa546527bbb18df6206ecb4f1bce9c21e28a6837d1d2a7e1572debd8c76faa40",
        "interval": "[2024-09-01,2026-09-01)", "warmup": "730d feature-only", "settled_total": "14092.01598100", "interval_cash": "14092.01598100", "roi": "0.4092015981", "drawdown_percent": "0.9647632885313554196929485448", "fees": "75916.70281220", "fills": 133, "funding": 614, "liquidations": 1,
        "limitations": ["authoritative liquidation lockout", "excluded from candidate eligibility"], "supersession": "None.",
    },
    {
        "id": "bybit-reporting-v2-fixed-stress", "kind": "stress", "title": "Fixed cost/latency stress validation", "classification": "VALIDATION_SEEN_NOT_OOS + NOT_FAITHFUL_DIAGNOSTIC", "selected": False,
        "artifact": "runs/native-validation-canonical-reporting-v2-stress.json", "sha256": "fd84369d1a72d294bedac178399796928d1d70870261fd7577e4ea7126729aec",
        "interval": "[2024-09-01,2026-09-01)", "warmup": "730d feature-only", "settled_total": "40097.56604124–96302.13189164", "interval_cash": "39654.95484204–94197.69629864", "roi": "3.009756604124–8.630213189164", "drawdown_percent": "0.8020757563766053931282251948–0.8987094062998082819696779217", "fees": "140868.43998060–279934.52061225", "fills": 475, "funding": 2444, "liquidations": 0,
        "limitations": ["fixed seen-data validation", "not optimization", "not live-rankable"], "supersession": "None.",
    },
    {
        "id": "hyperliquid-public-rest-blocked", "kind": "venue-evidence", "title": "Hyperliquid public REST evidence — blocked", "classification": "ARTIFACT_BLOCKED_FOR_COMPARABLE_1M", "selected": False,
        "artifact": "hyperliquid/manifest.json", "sha256": "b7feb312d8bc451e422ac3bf30742813decefb0723e49b90cb8ff787337b5183",
        "interval": "daily [2022-09-02,2026-09-01); funding [2024-09-01,2026-09-01)", "warmup": "daily proxy only", "settled_total": "UNKNOWN", "interval_cash": "UNKNOWN", "roi": "UNKNOWN", "drawdown_percent": "UNKNOWN", "fees": "UNKNOWN", "fills": 0, "funding": 17520, "liquidations": 0,
        "limitations": ["REST_MAX_5000_NO_24M_BBO", "AWS_REQUESTER_PAYS_INVENTORY_REQUIRED", "UNKNOWN_FREE_REST_HAS_NO_SETTLEMENT_ORACLE", "PROXY_PRICES_NONTRADING"], "supersession": "No Hyperliquid backtest exists.",
    },
)
