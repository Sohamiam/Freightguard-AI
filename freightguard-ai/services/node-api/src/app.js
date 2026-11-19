import express from "express";

/** Backend-for-frontend. All I/O is injected so it can be unit-tested without services. */
export function createApp({ riskUrl, agentUrl, n8nWebhook, fetchImpl = fetch, rawStore, ledger }) {
  const app = express();
  app.use(express.json({ limit: "2mb" }));

  const call = async (url, method, body) => {
    const r = await fetchImpl(url, { method, headers: { "content-type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
    const data = await r.json().catch(() => ({}));
    return { status: r.status, data };
  };

  app.get("/health", (_req, res) => res.json({ ok: true }));

  // Score an invoice with the ML engine; persist the raw payload (Mongo) and the scored row (Postgres).
  app.post("/api/invoices/score", async (req, res) => {
    const { raw, invoice } = req.body ?? {};
    if (!invoice?.invoice_id) return res.status(400).json({ error: "invoice.invoice_id required" });
    const { status, data } = await call(`${riskUrl}/score`, "POST", [invoice]);
    if (status !== 200) return res.status(502).json({ error: "risk engine failed", detail: data });
    if (raw && rawStore) await rawStore.saveRaw(invoice.invoice_id, raw);
    if (ledger) await ledger.saveScore(data[0]);
    res.json(data[0]);
  });

  // Start an agent run; it pauses at the human-review interrupt.
  app.post("/api/disputes", async (req, res) => {
    const { status, data } = await call(`${agentUrl}/disputes`, "POST", req.body);
    res.status(status).json(data);
  });

  // Reviewer decision. Approve/edit resumes the durable graph; the agent dispatches, and n8n is notified.
  app.post("/api/disputes/:id/review", async (req, res) => {
    const { action } = req.body ?? {};
    if (!["approve", "reject", "edit"].includes(action)) return res.status(400).json({ error: "action must be approve|reject|edit" });
    const { status, data } = await call(`${agentUrl}/disputes/${encodeURIComponent(req.params.id)}/review`, "POST", req.body);
    if (status === 200 && data.status === "sent" && n8nWebhook) {
      await call(n8nWebhook, "POST", { thread_id: req.params.id, action, reviewer: req.body.reviewer ?? "ops", to: data.message?.to, body: data.message?.body }).catch(() => {});
    }
    if (ledger && status === 200) await ledger.saveDecision(req.params.id, action, data.status);
    res.status(status).json(data);
  });

  app.get("/api/audit/verify", async (_req, res) => {
    const { status, data } = await call(`${agentUrl}/audit/verify`, "GET");
    res.status(status).json(data);
  });
  return app;
}
