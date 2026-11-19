import { describe, it, expect, vi } from "vitest";
import request from "supertest";
import { createApp } from "../src/app.js";

const json = (status, body) => Promise.resolve({ status, json: () => Promise.resolve(body) });
const mk = (fetchImpl, extra = {}) => createApp({ riskUrl: "http://risk", agentUrl: "http://agent", n8nWebhook: "http://n8n/hook", fetchImpl, ...extra });

describe("node-api BFF", () => {
  it("rejects scoring without invoice_id", async () => {
    const r = await request(mk(vi.fn())).post("/api/invoices/score").send({ invoice: {} });
    expect(r.status).toBe(400);
  });

  it("scores, stores raw payload and ledger row", async () => {
    const f = vi.fn(() => json(200, [{ invoice_id: "I1", risk_probability: 0.9 }]));
    const rawStore = { saveRaw: vi.fn() }, ledger = { saveScore: vi.fn() };
    const r = await request(mk(f, { rawStore, ledger })).post("/api/invoices/score").send({ raw: { text: "x" }, invoice: { invoice_id: "I1" } });
    expect(r.status).toBe(200); expect(rawStore.saveRaw).toHaveBeenCalledWith("I1", { text: "x" }); expect(ledger.saveScore).toHaveBeenCalled();
  });

  it("returns 502 when the risk engine fails", async () => {
    const r = await request(mk(vi.fn(() => json(500, {})))).post("/api/invoices/score").send({ invoice: { invoice_id: "I1" } });
    expect(r.status).toBe(502);
  });

  it("validates review action", async () => {
    const r = await request(mk(vi.fn())).post("/api/disputes/t1/review").send({ action: "maybe" });
    expect(r.status).toBe(400);
  });

  it("notifies n8n only after the agent reports 'sent'", async () => {
    const f = vi.fn((url) => json(200, url.includes("/review") ? { status: "sent" } : {}));
    await request(mk(f)).post("/api/disputes/t1/review").send({ action: "approve" });
    expect(f.mock.calls.some(([u]) => u === "http://n8n/hook")).toBe(true);
    const g = vi.fn(() => json(200, { status: "rejected" }));
    await request(mk(g)).post("/api/disputes/t2/review").send({ action: "reject" });
    expect(g.mock.calls.some(([u]) => u === "http://n8n/hook")).toBe(false);
  });
});
