-- Normalized financial ledger (PostgreSQL). Loaded automatically by docker compose.
CREATE TABLE IF NOT EXISTS carriers (carrier_id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS invoices (
  invoice_id TEXT PRIMARY KEY, pro_number TEXT NOT NULL, carrier TEXT NOT NULL, lane TEXT NOT NULL,
  invoice_date DATE NOT NULL DEFAULT CURRENT_DATE, miles NUMERIC, billed_linehaul NUMERIC(12,2), billed_fsc NUMERIC(12,2),
  billed_detention NUMERIC(12,2), billed_total NUMERIC(12,2) NOT NULL, content_hash CHAR(64) UNIQUE,   -- idempotency
  is_overbilled BOOLEAN, typology TEXT);
CREATE TABLE IF NOT EXISTS invoice_scores (
  invoice_id TEXT PRIMARY KEY, risk_probability DOUBLE PRECISION, anomaly_score DOUBLE PRECISION, flagged BOOLEAN,
  top_drivers JSONB, scored_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS dispute_findings (
  id BIGSERIAL PRIMARY KEY, invoice_id TEXT NOT NULL, code TEXT NOT NULL, billed NUMERIC(12,2), expected NUMERIC(12,2), overcharge NUMERIC(12,2));
CREATE TABLE IF NOT EXISTS dispute_decisions (
  id BIGSERIAL PRIMARY KEY, thread_id TEXT NOT NULL, action TEXT NOT NULL CHECK (action IN ('approve','reject','edit')),
  final_status TEXT, decided_at TIMESTAMPTZ DEFAULT now());
