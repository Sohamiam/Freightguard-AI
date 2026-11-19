-- Materialized views for Power BI (DirectQuery or Import). Refresh: REFRESH MATERIALIZED VIEW CONCURRENTLY <name>;
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_invoice_facts AS
SELECT i.invoice_id, i.carrier, i.lane, i.invoice_date, i.billed_total, i.is_overbilled, i.typology,
       s.risk_probability, s.anomaly_score, s.flagged,
       COALESCE(f.total_overcharge, 0) AS total_overcharge
FROM invoices i
LEFT JOIN invoice_scores s USING (invoice_id)
LEFT JOIN (SELECT invoice_id, SUM(overcharge) AS total_overcharge FROM dispute_findings GROUP BY invoice_id) f USING (invoice_id);
CREATE UNIQUE INDEX IF NOT EXISTS mv_invoice_facts_pk ON mv_invoice_facts (invoice_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_carrier_recovery AS
SELECT carrier, COUNT(*) AS invoices, COUNT(*) FILTER (WHERE flagged) AS flagged_invoices,
       SUM(total_overcharge) AS identified_overcharge, SUM(billed_total) AS billed_total
FROM mv_invoice_facts GROUP BY carrier;
CREATE UNIQUE INDEX IF NOT EXISTS mv_carrier_recovery_pk ON mv_carrier_recovery (carrier);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_typology_monthly AS
SELECT date_trunc('month', f.invoice_date)::date AS month, f.typology, COUNT(*) AS cases, SUM(f.total_overcharge) AS overcharge
FROM mv_invoice_facts f WHERE f.typology IS NOT NULL AND f.typology <> 'none' GROUP BY 1, 2;
CREATE UNIQUE INDEX IF NOT EXISTS mv_typology_monthly_pk ON mv_typology_monthly (month, typology);

CREATE OR REPLACE VIEW v_dispute_outcomes AS
SELECT d.thread_id, d.action, d.final_status, d.decided_at FROM dispute_decisions d;
