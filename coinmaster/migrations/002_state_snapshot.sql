-- Migration 002: State snapshot table for Phase 1 bridge
-- Stores the full DBShape as a single JSONB document, allowing
-- PostgresStore to load/flush the same in-memory snapshot that
-- lowdb uses — zero changes to core logic.
--
-- This is a transitional approach: Phase 2+ will migrate to the
-- normalised tables created in 001_initial_schema.sql.
--
-- Run: psql $DATABASE_URL -f migrations/002_state_snapshot.sql

BEGIN;

CREATE TABLE IF NOT EXISTS state_snapshot (
  key        TEXT        PRIMARY KEY,
  data       JSONB       NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
