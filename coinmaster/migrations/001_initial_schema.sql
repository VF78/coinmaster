-- Migration 001: Initial PostgreSQL schema for coinmaster
-- Mirrors lowdb DBShape entities for phase-1 cutover
-- Run: psql $DATABASE_URL -f migrations/001_initial_schema.sql

BEGIN;

-- ─── Settings (singleton row) ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS settings (
  id         INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  deposit_usd NUMERIC(18,2) NOT NULL DEFAULT 1000,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO settings (deposit_usd) VALUES (1000) ON CONFLICT DO NOTHING;

-- ─── Positions ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS positions (
  id              TEXT PRIMARY KEY,
  symbol          TEXT NOT NULL,
  side            TEXT NOT NULL CHECK (side IN ('long','short')),
  entry_price     NUMERIC(18,8) NOT NULL,
  stop_loss       NUMERIC(18,8) NOT NULL,
  take_profit     NUMERIC(18,8) NOT NULL,
  size            NUMERIC(18,8) NOT NULL,
  remaining_size  NUMERIC(18,8),
  realized_pnl    NUMERIC(18,8),
  tp1_price       NUMERIC(18,8),
  tp2_price       NUMERIC(18,8),
  tp3_price       NUMERIC(18,8),
  tp1_done        BOOLEAN DEFAULT FALSE,
  tp2_done        BOOLEAN DEFAULT FALSE,
  tp3_done        BOOLEAN DEFAULT FALSE,
  leverage        NUMERIC(10,2),
  opened_at       TIMESTAMPTZ NOT NULL,
  closed_at       TIMESTAMPTZ,
  status          TEXT NOT NULL CHECK (status IN ('open','closed')),
  pnl             NUMERIC(18,8) NOT NULL DEFAULT 0,
  source          TEXT NOT NULL CHECK (source IN ('manual','sim','live')),
  correlation_id  TEXT
);

CREATE INDEX IF NOT EXISTS idx_positions_symbol_status ON positions (symbol, status);
CREATE INDEX IF NOT EXISTS idx_positions_opened_at ON positions (opened_at);

-- ─── Trade Logs ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trade_logs (
  id          TEXT PRIMARY KEY,
  position_id TEXT REFERENCES positions(id),
  symbol      TEXT NOT NULL,
  action      TEXT NOT NULL CHECK (action IN ('open','partial','close','bias')),
  side        TEXT CHECK (side IN ('long','short')),
  price       NUMERIC(18,8),
  quantity    NUMERIC(18,8),
  pnl         NUMERIC(18,8),
  note        TEXT,
  timestamp   TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trade_logs_timestamp ON trade_logs (timestamp);

-- ─── Trade Events (append-only ledger with hash chain) ────────────────
CREATE TABLE IF NOT EXISTS trade_events (
  id              TEXT PRIMARY KEY,
  seq             BIGINT NOT NULL,
  symbol          TEXT NOT NULL,
  type            TEXT NOT NULL,
  source          TEXT NOT NULL CHECK (source IN ('paper','live','replay')),
  timestamp       TIMESTAMPTZ NOT NULL,
  correlation_id  TEXT NOT NULL,
  position_id     TEXT,
  side            TEXT CHECK (side IN ('long','short')),
  price           NUMERIC(18,8),
  quantity        NUMERIC(18,8),
  pnl             NUMERIC(18,8),
  reason          TEXT,
  prev_hash       TEXT,
  hash            TEXT NOT NULL,
  payload         JSONB
);

CREATE INDEX IF NOT EXISTS idx_trade_events_seq ON trade_events (seq);
CREATE INDEX IF NOT EXISTS idx_trade_events_symbol_type ON trade_events (symbol, type);
CREATE INDEX IF NOT EXISTS idx_trade_events_timestamp ON trade_events (timestamp);

-- ─── Bias Commands ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bias_commands (
  id          TEXT PRIMARY KEY,
  symbol      TEXT NOT NULL,
  bias        TEXT NOT NULL CHECK (bias IN ('long','short','off')),
  created_at  TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bias_commands_symbol ON bias_commands (symbol, created_at);

-- ─── Market Ticks ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS market_ticks (
  symbol    TEXT NOT NULL,
  price     NUMERIC(18,8) NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL
);

-- Partition-friendly: timeseries, no PK needed; use BRIN for fast range scans
CREATE INDEX IF NOT EXISTS idx_market_ticks_symbol_ts ON market_ticks (symbol, timestamp);

-- ─── Daily DD Baselines ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS daily_dd_baselines (
  date             DATE PRIMARY KEY,
  start_equity_usd NUMERIC(18,2) NOT NULL,
  updated_at       TIMESTAMPTZ NOT NULL
);

-- ─── Risk Gate Audit ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS risk_gate_audit (
  id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  timestamp TIMESTAMPTZ NOT NULL,
  gate      TEXT NOT NULL CHECK (gate IN ('daily_dd','leverage_cap','auth')),
  passed    BOOLEAN NOT NULL,
  reason    TEXT,
  details   JSONB
);

CREATE INDEX IF NOT EXISTS idx_risk_gate_audit_ts ON risk_gate_audit (timestamp);

COMMIT;
