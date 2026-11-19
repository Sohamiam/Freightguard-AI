import { createApp } from "./app.js";

const env = process.env;
let rawStore, ledger;

// NO_DB=1 runs the BFF without MongoDB/Postgres (local demo). Scoring and disputes still work; persistence is skipped.
if (env.NO_DB !== "1") {
  const { default: pg } = await import("pg");
  const { MongoClient } = await import("mongodb");
  const mongo = new MongoClient(env.MONGO_URL ?? "mongodb://localhost:27017");
  await mongo.connect();
  const raw = mongo.db("freightguard").collection("raw_payloads");
  const pool = new pg.Pool({ connectionString: env.DATABASE_URL ?? "postgres://fg:fg@localhost:5432/freightguard" });
  rawStore = { saveRaw: (id, payload) => raw.updateOne({ _id: id }, { $set: { payload, at: new Date() } }, { upsert: true }) };
  ledger = {
    saveScore: (s) => pool.query(
      `INSERT INTO invoice_scores (invoice_id, risk_probability, anomaly_score, flagged, top_drivers)
       VALUES ($1,$2,$3,$4,$5) ON CONFLICT (invoice_id) DO UPDATE SET risk_probability=$2, anomaly_score=$3, flagged=$4, top_drivers=$5`,
      [s.invoice_id, s.risk_probability, s.anomaly_score, s.flagged, JSON.stringify(s.top_drivers)]),
    saveDecision: (id, action, status) => pool.query(
      `INSERT INTO dispute_decisions (thread_id, action, final_status) VALUES ($1,$2,$3)`, [id, action, status]),
  };
}

createApp({ riskUrl: env.RISK_URL ?? "http://localhost:8001", agentUrl: env.AGENT_URL ?? "http://localhost:8002",
  n8nWebhook: env.N8N_WEBHOOK, rawStore, ledger }).listen(4000, () => console.log(`node-api on :4000 (${env.NO_DB === "1" ? "no database" : "with databases"})`));
