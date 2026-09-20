"""P2 local-only API; it records control intent but never sends orders."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, model_validator

from coinmaster.research.native_fixture import BTC_PERP, SIM, SOL_PERP, build_engine, quote
from coinmaster.research.catalog import RESEARCH_CATALOG
from coinmaster.venues.bybit_profile import BybitVenueProfile


BASELINE_CONFIG: dict[str, Any] = {
    "strategy_id": "btc_sol_wave_overlay_v1", "mode": "paper", "live_enabled": False,
    "venue": None, "initial_total_usdt": "10000", "initial_active_fraction": 1.0,
    "signal_timeframe": "1D", "regime": "close_vs_ema", "ema_period": 21,
    "beta_days": 270, "relative_days": 65, "z_history_days": 180, "wave_history_days": 730,
    "wave_min_count": 8, "include_zero_waves": True, "wave_quantiles": [0.10, 0.30, 0.60],
    "btc_tp_fractions_initial_qty": [0.15, 0.25, 0.35], "btc_notional_multiplier": 9.0,
    "max_parent_notional": "10000000", "max_gross_to_active": 50.0,
    "sol_size_multipliers_H": [1.0, 1.5, 2.0], "sol_entry_z": [1.25, 2.50, 3.75],
    "sol_direction": "opposite_btc", "sol_entry_eligibility": "persistent_after_btc_level",
    "freeze_sigma_on_first_sol_fill": True, "sol_exit_half_z": 0.375,
    "sol_exit_all_z": 0.125, "sol_max_holding_days": 14, "sol_z_stop": None,
    "btc_close_stop_fraction": None, "btc_close_trail_fraction": 0.03,
    "portfolio_loss_limit_fraction": None, "future_sol_margin_fraction": 0.0,
    "insufficient_margin": "reject", "reserve_transfer_fraction": 0.0,
    "reserve_trigger_multiple": 4.0, "restart_target": "initial_active_seed",
    "post_liquidation": "restart_from_reserve_else_pause",
}


class StrategyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy_id: Literal["btc_sol_wave_overlay_v1"]; mode: Literal["paper"]; live_enabled: Literal[False]
    venue: Literal["bybit", "hyperliquid"] | None; initial_total_usdt: str; initial_active_fraction: float = Field(gt=0, le=1)
    signal_timeframe: Literal["1D"]; regime: Literal["close_vs_ema"]; ema_period: int = Field(gt=0); beta_days: int = Field(gt=0); relative_days: int = Field(gt=0); z_history_days: int = Field(gt=0); wave_history_days: int = Field(gt=0); wave_min_count: int = Field(gt=0)
    include_zero_waves: bool; wave_quantiles: list[float] = Field(min_length=3, max_length=3); btc_tp_fractions_initial_qty: list[float] = Field(min_length=3, max_length=3); btc_notional_multiplier: float = Field(gt=0); max_parent_notional: str; max_gross_to_active: float = Field(gt=0)
    sol_size_multipliers_H: list[float] = Field(min_length=3, max_length=3); sol_entry_z: list[float] = Field(min_length=3, max_length=3); sol_direction: Literal["opposite_btc"]; sol_entry_eligibility: Literal["persistent_after_btc_level"]; freeze_sigma_on_first_sol_fill: bool; sol_exit_half_z: float = Field(ge=0); sol_exit_all_z: float = Field(ge=0); sol_max_holding_days: int = Field(gt=0); sol_z_stop: float | None; btc_close_stop_fraction: float | None; btc_close_trail_fraction: float = Field(ge=0); portfolio_loss_limit_fraction: float | None; future_sol_margin_fraction: float = Field(ge=0, le=1); insufficient_margin: Literal["reject", "clip"]; reserve_transfer_fraction: float = Field(ge=0, le=1); reserve_trigger_multiple: float = Field(gt=0); restart_target: Literal["initial_active_seed"]; post_liquidation: Literal["restart_from_reserve_else_pause"]

    @model_validator(mode="after")
    def validate_candidate(self) -> "StrategyConfig":
        for value in (self.initial_total_usdt, self.max_parent_notional):
            if not Decimal(value).is_finite() or Decimal(value) <= 0: raise ValueError("money values must be finite positive decimal strings")
        if self.wave_quantiles != sorted(self.wave_quantiles) or self.sol_entry_z != sorted(self.sol_entry_z): raise ValueError("quantiles and z levels must be ordered")
        return self

class ConfigurationInput(BaseModel):
    config: StrategyConfig


class ConfigurationRecord(BaseModel):
    id: str
    config_hash: str
    created_at: str
    config: StrategyConfig


class RunInput(BaseModel):
    config_id: str
    kind: Literal["fixture", "backtest", "paper"]


class RunRecord(BaseModel):
    id: str
    config_id: str
    kind: str
    status: str
    evidence: list[str]
    created_at: str
    report: dict[str, Any] | None = None


class ResearchCatalogEntry(BaseModel):
    id: str; kind: str; title: str; classification: str; selected: bool
    artifact: str; sha256: str; artifact_state: str
    interval: str; warmup: str; settled_total: str; interval_cash: str; roi: str; drawdown_percent: str; fees: str
    fills: int; funding: int; liquidations: int; limitations: list[str]; supersession: str


class ResearchCatalogDetail(ResearchCatalogEntry):
    verified_detail: dict[str, Any] | None = None


class PreflightInput(BaseModel):
    venue: Literal["bybit", "hyperliquid"]
    active_usdt: str = "10000"
    beta: str | None = None
    selected_leverage: str | None = None
    btc_notional: str
    sol_multipliers: list[float] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_values(self) -> "PreflightInput":
        if Decimal(self.active_usdt) <= 0 or Decimal(self.btc_notional) <= 0: raise ValueError("notionals must be positive")
        if self.beta is not None and Decimal(self.beta) <= 0: raise ValueError("beta must be positive")
        if self.selected_leverage is not None and Decimal(self.selected_leverage) <= 0: raise ValueError("selected leverage must be positive")
        return self


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


class ControlStore:
    def __init__(self, database: str) -> None:
        Path(database).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(database, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS configurations (
                id TEXT PRIMARY KEY, config_hash TEXT NOT NULL, created_at TEXT NOT NULL, body TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, config_id TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL,
                evidence TEXT NOT NULL, created_at TEXT NOT NULL, report TEXT
            );
            CREATE TABLE IF NOT EXISTS commands (
                idempotency_key TEXT PRIMARY KEY, command TEXT NOT NULL, created_at TEXT NOT NULL, result TEXT NOT NULL
            );
        """)

    def save_config(self, config: StrategyConfig) -> ConfigurationRecord:
        config = config.model_dump()
        body = json.dumps(config, sort_keys=True, separators=(",", ":"))
        record = ConfigurationRecord(id=str(uuid4()), config_hash=hashlib.sha256(body.encode()).hexdigest(), created_at=utcnow(), config=config)
        self.db.execute("INSERT INTO configurations VALUES (?, ?, ?, ?)", (record.id, record.config_hash, record.created_at, body))
        self.db.commit()
        return record

    def configs(self) -> list[ConfigurationRecord]:
        return [ConfigurationRecord(id=row[0], config_hash=row[1], created_at=row[2], config=StrategyConfig.model_validate_json(row[3])) for row in self.db.execute("SELECT id, config_hash, created_at, body FROM configurations ORDER BY created_at DESC")]

    def get_config(self, config_id: str) -> ConfigurationRecord:
        row = self.db.execute("SELECT id, config_hash, created_at, body FROM configurations WHERE id = ?", (config_id,)).fetchone()
        if row is None:
            raise KeyError(config_id)
        return ConfigurationRecord(id=row[0], config_hash=row[1], created_at=row[2], config=StrategyConfig.model_validate_json(row[3]))

    def save_run(self, record: RunRecord) -> RunRecord:
        self.db.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?)", (record.id, record.config_id, record.kind, record.status, json.dumps(record.evidence), record.created_at, json.dumps(record.report) if record.report else None))
        self.db.commit()
        return record

    def get_run(self, run_id: str) -> RunRecord:
        row = self.db.execute("SELECT id, config_id, kind, status, evidence, created_at, report FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return RunRecord(id=row[0], config_id=row[1], kind=row[2], status=row[3], evidence=json.loads(row[4]), created_at=row[5], report=json.loads(row[6]) if row[6] else None)

    def runs(self) -> list[RunRecord]:
        return [self.get_run(row[0]) for row in self.db.execute("SELECT id FROM runs ORDER BY created_at DESC")]

    def cancel(self, run_id: str) -> RunRecord:
        run = self.get_run(run_id)
        if run.status == "QUEUED":
            self.db.execute("UPDATE runs SET status = ? WHERE id = ?", ("CANCELED", run_id))
            self.db.commit()
            return self.get_run(run_id)
        return run


def fixture_report() -> dict[str, Any]:
    """Runs the P1 native engine; this is explicitly not a strategy backtest."""
    engine = build_engine()
    engine.add_data([
        quote(BTC_PERP.id, "80000.0", "80001.0", 1), quote(BTC_PERP.id, "80999.0", "81000.0", 2),
        quote(BTC_PERP.id, "80999.0", "81000.0", 3), quote(BTC_PERP.id, "80999.0", "81000.0", 4),
        quote(SOL_PERP.id, "159.90", "160.00", 5), quote(SOL_PERP.id, "159.90", "160.00", 6),
        quote(BTC_PERP.id, "80999.0", "81000.0", 7), quote(BTC_PERP.id, "80999.0", "81000.0", 8),
        quote(SOL_PERP.id, "149.90", "150.00", 9), quote(SOL_PERP.id, "149.90", "150.00", 10),
    ])
    engine.run()
    try:
        total = engine.trader.generate_account_report(SIM)["total"].iloc[-1].split()[0]
        return {"terminal_total_usdt": total, "fills": len(engine.trader.generate_order_fills_report()), "label": "SYNTHETIC_P1_FIXTURE", "ranking_eligible": False}
    finally:
        engine.dispose()


def _catalog_artifact_state(entry: dict[str, Any]) -> str:
    path = Path(__file__).resolve().parents[2] / "var/data" / entry["artifact"]
    if not path.exists():
        return "ARTIFACT_NOT_LOCAL"
    return "VERIFIED_LOCAL" if hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"] else "ARTIFACT_HASH_MISMATCH"


def _catalog_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {**entry, "artifact_state": _catalog_artifact_state(entry)}


def _verified_catalog_detail(entry: dict[str, Any]) -> dict[str, Any] | None:
    if _catalog_artifact_state(entry) != "VERIFIED_LOCAL":
        return None
    source = json.loads((Path(__file__).resolve().parents[2] / "var/data" / entry["artifact"]).read_text())
    variant_by_id = {
        "bybit-reporting-v2-selected-7.5": "btc_notional_7.5",
        "bybit-reporting-v2-candidate-8.25": "btc_notional_8.25",
        "bybit-reporting-v2-excluded-9.75": "btc_notional_9.75",
        "bybit-reporting-v2-excluded-10.5": "btc_notional_10.5",
    }
    if entry["id"] in variant_by_id:
        source = next(item for item in source["results"] if item["variant_id"] == variant_by_id[entry["id"]])
    if entry["id"] == "bybit-reporting-v2-fixed-stress":
        return {"status": source["status"], "control_reuse": source["control_reuse"], "results": [{key: item.get(key) for key in ("variant_id", "status", "terminal_total", "terminal_active", "terminal_reserve", "fills", "native_fees", "funding", "liquidation_count", "pre_submit_tier_margin_gate_blocks", "post_boundary_settlement", "summary")} for item in source["results"]]}
    if entry["id"] == "hyperliquid-public-rest-blocked":
        return {key: source[key] for key in ("schema", "daily_interval", "funding_interval", "symbols", "faithful_comparable_1m_run_blockers", "historical_profile_applicability", "limitations")}
    return {key: source.get(key) for key in ("status", "terminal_total", "terminal_active", "terminal_reserve", "terminal_open_positions", "fills", "native_fees", "funding", "liquidation_count", "liquidation_audit", "pre_submit_tier_margin_gate_blocks", "post_boundary_settlement", "summary", "config_hash", "data_hash", "policy_hash", "code_hash")}


def immutable_research_reference() -> tuple[list[str], dict[str, Any]]:
    selected = next(item for item in RESEARCH_CATALOG if item["id"] == "bybit-reporting-v2-selected-7.5")
    state = _catalog_artifact_state(selected)
    return ["IMMUTABLE_RESEARCH_REFERENCE", "NO_NEW_BACKTEST_COMPUTE", selected["classification"], state], {"catalog_id": selected["id"], "artifact": selected["artifact"], "sha256": selected["sha256"], "artifact_state": state, "reason": "This request references immutable native research evidence; a separate research worker is required for any new computation."}


def create_app(database: str | None = None, token: str | None = None) -> FastAPI:
    store = ControlStore(database or os.getenv("COINMASTER_CONTROL_DB", "var/coinmaster-control.sqlite"))
    expected_token = token if token is not None else os.getenv("COINMASTER_API_TOKEN")
    app = FastAPI(title="Coinmaster Nautilus Control API", version="0.1.0", docs_url="/api/v1/docs", openapi_url="/api/v1/openapi.json")
    app.add_middleware(CORSMiddleware, allow_origins=[os.getenv("COINMASTER_ALLOWED_ORIGIN", "http://localhost:5173")], allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Authorization", "Idempotency-Key"])

    def auth(authorization: str | None = Header(default=None)) -> None:
        if not expected_token or authorization != f"Bearer {expected_token}":
            raise HTTPException(401, "local API token required")

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "bind": "localhost/private-network only", "execution": "disabled"}

    @app.get("/api/v1/configurations/default", response_model=ConfigurationInput, dependencies=[Depends(auth)])
    def default_config() -> ConfigurationInput:
        return ConfigurationInput(config=BASELINE_CONFIG)

    @app.get("/api/v1/configurations", response_model=list[ConfigurationRecord], dependencies=[Depends(auth)])
    def list_configs() -> list[ConfigurationRecord]:
        return store.configs()

    @app.post("/api/v1/configurations", response_model=ConfigurationRecord, dependencies=[Depends(auth)])
    def create_config(input: ConfigurationInput) -> ConfigurationRecord:
        try:
            return store.save_config(input.config)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/api/v1/venue-profiles", dependencies=[Depends(auth)])
    def venue_profiles() -> dict[str, Any]:
        profile = BybitVenueProfile.from_raw(Path(__file__).resolve().parents[2])
        return {"profiles": [{"venue": "bybit", "hashes": profile.hashes, "evidence": ["UNKNOWN_ACCOUNT_TIER", "MISSING_ACCOUNT_FEES"]}, {"venue": "hyperliquid", "evidence": ["UNKNOWN_TIERS", "MISSING_FUNDING", "PROXY_PRICES"]}]}

    @app.get("/api/v1/research/catalog", response_model=list[ResearchCatalogEntry], dependencies=[Depends(auth)])
    def research_catalog() -> list[ResearchCatalogEntry]:
        return [_catalog_entry(entry) for entry in RESEARCH_CATALOG]

    @app.get("/api/v1/research/catalog/{catalog_id}", response_model=ResearchCatalogDetail, dependencies=[Depends(auth)])
    def research_catalog_detail(catalog_id: str) -> ResearchCatalogDetail:
        entry = next((item for item in RESEARCH_CATALOG if item["id"] == catalog_id), None)
        if entry is None:
            raise HTTPException(404, "research catalog entry not found")
        return {**_catalog_entry(entry), "verified_detail": _verified_catalog_detail(entry)}

    @app.post("/api/v1/preflight", dependencies=[Depends(auth)])
    def preflight(input: PreflightInput) -> dict[str, Any]:
        if input.beta is None:
            return {"requested": {"btc_notional": input.btc_notional}, "allowed": False, "im": None, "mm": None, "sol_additions": ["UNKNOWN_BETA"] * 3, "reasons": ["UNKNOWN_BETA"]}
        if input.venue != "bybit":
            return {"requested": {"btc_notional": input.btc_notional}, "allowed": False, "im": None, "mm": None, "sol_additions": ["UNKNOWN_TIERS"] * 3, "reasons": ["UNKNOWN_TIERS", "MISSING_FUNDING", "PROXY_PRICES"]}
        profile = BybitVenueProfile.from_raw(Path(__file__).resolve().parents[2])
        btc = Decimal(input.btc_notional); beta = Decimal(input.beta); sol_notionals = [btc / beta * Decimal(str(item)) for item in input.sol_multipliers]
        try:
            btc_tier = profile.tier_for("BTCUSDT", btc); sol_tiers = [profile.tier_for("SOLUSDT", item) for item in sol_notionals]
        except ValueError:
            return {"requested": {"btc_notional": input.btc_notional}, "allowed": False, "im": None, "mm": None, "sol_additions": ["UNKNOWN_OR_OUT_OF_RANGE_TIER"] * 3, "reasons": ["UNKNOWN_OR_OUT_OF_RANGE_TIER"]}
        im = btc * btc_tier.im; mm = max(Decimal("0"), btc * btc_tier.mm - btc_tier.deduction); additions = []
        for sol, tier in zip(sol_notionals, sol_tiers):
            im += sol * tier.im; mm += max(Decimal("0"), sol * tier.mm - tier.deduction); additions.append(str(sol))
        return {"requested": {"btc_notional": str(btc)}, "allowed": False, "im": str(im), "mm": str(mm), "sol_additions": additions, "reasons": ["UNKNOWN_ACCOUNT_MARGIN_MODE", "MISSING_ACCOUNT_FEES"], "cap_label": "maximum request with sufficient collateral; not a starting order"}

    @app.post("/api/v1/runs", response_model=RunRecord, dependencies=[Depends(auth)])
    def create_run(input: RunInput) -> RunRecord:
        try: store.get_config(input.config_id)
        except KeyError as error: raise HTTPException(404, "configuration not found") from error
        run = RunRecord(id=str(uuid4()), config_id=input.config_id, kind=input.kind, created_at=utcnow(), status="QUEUED", evidence=[], report=None)
        if input.kind == "fixture":
            run.status, run.evidence, run.report = "COMPLETED", ["SYNTHETIC_P1_FIXTURE", "NOT_REAL_DATA", "NOT_RANKABLE"], fixture_report()
        elif input.kind == "backtest":
            run.status = "COMPLETED_ARTIFACT_REFERENCE"
            run.evidence, run.report = immutable_research_reference()
        return store.save_run(run)

    @app.get("/api/v1/runs", response_model=list[RunRecord], dependencies=[Depends(auth)])
    def list_runs() -> list[RunRecord]: return store.runs()

    @app.get("/api/v1/runs/{run_id}", response_model=RunRecord, dependencies=[Depends(auth)])
    def get_run(run_id: str) -> RunRecord:
        try: return store.get_run(run_id)
        except KeyError as error: raise HTTPException(404, "run not found") from error

    @app.post("/api/v1/runs/{run_id}/cancel", response_model=RunRecord, dependencies=[Depends(auth)])
    def cancel_run(run_id: str) -> RunRecord:
        try: return store.cancel(run_id)
        except KeyError as error: raise HTTPException(404, "run not found") from error

    @app.get("/api/v1/runs/{run_id}/report", dependencies=[Depends(auth)])
    def run_report(run_id: str) -> dict[str, Any]: return get_run(run_id).model_dump()

    @app.get("/api/v1/runtime", dependencies=[Depends(auth)])
    def runtime() -> dict[str, Any]:
        return {"status": "NOT_RUNNING", "active_usdt": "10000", "reserve_usdt": "0", "total_usdt": "10000", "positions": [], "orders": [], "warnings": ["P4 paper worker and reconciliation are not implemented"]}

    @app.post("/api/v1/commands", dependencies=[Depends(auth)])
    def command(command: Literal["pause-new-entries", "flatten"], idempotency_key: str = Header(alias="Idempotency-Key")) -> dict[str, str]:
        if not idempotency_key: raise HTTPException(422, "Idempotency-Key is required")
        result = {"status": "REJECTED_NO_RUNTIME", "command": command}
        store.db.execute("INSERT OR IGNORE INTO commands VALUES (?, ?, ?, ?)", (idempotency_key, command, utcnow(), json.dumps(result))); store.db.commit()
        row = store.db.execute("SELECT result FROM commands WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
        return json.loads(row[0])

    return app


app = create_app()
