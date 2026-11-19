import { useState } from "react";
import { api, money, shapBars, totalOvercharge } from "./lib.js";

// Demo case so the cockpit renders without a backend. Real cases arrive from POST /api/disputes.
const DEMO = {
  thread_id: "demo-1",
  state: {
    invoice: { invoice_id: "INV-000081", carrier: "Apex Freight", lane: "CHI-DAL" },
    findings: [
      { code: "UNAPPROVED_FSC", billed: "190.00", expected: "125.00", overcharge: "65.00" },
      { code: "DETENTION_MISCALC", billed: "300.00", expected: "180.00", overcharge: "120.00" },
    ],
    citations: ["Apex Freight:5.1", "Apex Freight:6.2"],
    clauses: ["MSA 5.1 [Fuel Surcharge] Fuel surcharge is fixed at 10% of linehaul.", "MSA 6.2 [Detention] Detention beyond free time is billed at $60.00 per hour."],
    draft: "Re: Invoice INV-000081 - billing dispute\n\nWe identified discrepancies. Please issue a credit within 30 days (MSA 8.1).",
  },
  ml: { risk_probability: 0.93, anomaly_score: 0.61, top_drivers: [
    { feature: "fsc_delta_pct", shap: 1.8, value: 0.52 }, { feature: "detention_delta_usd", shap: 1.1, value: 120 }, { feature: "total_delta_pct", shap: -0.4, value: 0.09 } ] },
};

const LIVE = {
  invoice: { invoice_id: "INV-LIVE", carrier: "Apex Freight", lane: "CHI-DAL", miles: "500", linehaul: "1250", fuel_surcharge: "190", detention_hours: "5", detention_charge: "300" },
  card: { carrier: "Apex Freight", lane: "CHI-DAL", rate_per_mile: "2.5", fuel_surcharge_pct: "0.10", detention_rate_per_hr: "60" },
  actual_detention_hrs: "5", ml: {},
};
const NO_ML = { risk_probability: 0, anomaly_score: 0, top_drivers: [] };

function Shap({ drivers }) {
  return (
    <div className="space-y-2" aria-label="SHAP drivers">
      {shapBars(drivers).map((d) => (
        <div key={d.feature}>
          <div className="flex justify-between text-xs text-slate-600"><span>{d.feature}</span><span>{d.shap > 0 ? "+" : ""}{d.shap.toFixed(2)}</span></div>
          <div className="h-2 rounded bg-slate-200"><div className={`h-2 rounded ${d.up ? "bg-red-500" : "bg-emerald-500"}`} style={{ width: `${d.width}%` }} /></div>
        </div>
      ))}
    </div>
  );
}

export default function App() {
  const [cases, setCases] = useState([DEMO]);
  const [sel, setSel] = useState(0);
  const [draft, setDraft] = useState(DEMO.state.draft);
  const [msg, setMsg] = useState("");
  const c = cases[sel];
  const pick = (i) => { setSel(i); setDraft(cases[i].state.draft); setMsg(""); };

  async function loadLive() {
    try {
      const id = `live-${Date.now()}`;
      const r = await api("/api/disputes", { method: "POST", body: JSON.stringify({ thread_id: id, ...LIVE }) });
      if (!r.interrupted) return setMsg("Agent found nothing to dispute on this invoice.");
      setCases((cs) => [...cs, { thread_id: id, state: r.state, ml: r.state.ml?.top_drivers ? r.state.ml : NO_ML }]);
      setSel(cases.length); setDraft(r.state.draft); setMsg("Live dispute loaded from the agent.");
    } catch (e) { setMsg(`Could not start a live dispute (${e.message}). Are the agent (8002) and node-api (4000) running?`); }
  }

  async function decide(action) {
    if (c.thread_id === "demo-1") return setMsg("This sample case is not connected to the agent. Click 'Start live dispute' to try a real one.");
    try {
      const body = { action, reviewer: "ops", ...(action === "edit" ? { edited_draft: draft } : {}) };
      const r = await api(`/api/disputes/${c.thread_id}/review`, { method: "POST", body: JSON.stringify(body) });
      setMsg(`Decision recorded: ${action} -> ${r.status}`);
      setCases((cs) => cs.filter((_, i) => i !== sel)); setSel(0);
    } catch (e) { setMsg(`Could not reach the API (${e.message}). Start node-api to submit decisions.`); }
  }

  if (!c) return <main className="p-8 text-slate-600">Review queue is empty.</main>;
  const f = c.state.findings;
  return (
    <main className="mx-auto grid max-w-6xl grid-cols-12 gap-4 p-6">
      <aside className="col-span-3 space-y-2">
        <h1 className="text-lg font-semibold">Review queue</h1>
        <button onClick={loadLive} className="w-full rounded bg-slate-800 px-3 py-2 text-sm text-white">Start live dispute</button>
        {cases.map((x, i) => (
          <button key={x.thread_id} onClick={() => pick(i)} className={`w-full rounded border p-3 text-left text-sm ${i === sel ? "border-blue-500 bg-white" : "bg-slate-100"}`}>
            <div className="font-medium">{x.state.invoice.invoice_id}</div><div className="text-slate-500">{x.state.invoice.carrier}</div>
          </button>))}
      </aside>
      <section className="col-span-5 space-y-4">
        <div className="rounded border bg-white p-4">
          <h2 className="font-semibold">Findings - {money(totalOvercharge(f))} overbilled</h2>
          <table className="mt-2 w-full text-sm"><thead className="text-left text-slate-500"><tr><th>Code</th><th>Billed</th><th>Contract</th><th>Over</th></tr></thead>
            <tbody>{f.map((x) => <tr key={x.code}><td>{x.code}</td><td>{money(x.billed)}</td><td>{money(x.expected)}</td><td className="text-red-600">{money(x.overcharge)}</td></tr>)}</tbody></table>
        </div>
        <div className="rounded border bg-white p-4"><h2 className="mb-2 font-semibold">Risk drivers (SHAP) - p={c.ml.risk_probability.toFixed(2)}, anomaly={c.ml.anomaly_score.toFixed(2)}</h2><Shap drivers={c.ml.top_drivers} /></div>
        <div className="rounded border bg-white p-4"><h2 className="mb-2 font-semibold">MSA citations</h2>
          <ul className="space-y-1 text-sm">{c.state.clauses.map((t, i) => <li key={i} className="rounded bg-slate-50 p-2">{t}</li>)}</ul></div>
      </section>
      <section className="col-span-4 space-y-3">
        <h2 className="font-semibold">Dispute email draft</h2>
        <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={12} className="w-full rounded border p-2 text-sm" />
        <div className="flex gap-2">
          <button onClick={() => decide("approve")} className="rounded bg-emerald-600 px-3 py-2 text-sm text-white">Approve</button>
          <button onClick={() => decide("edit")} className="rounded bg-blue-600 px-3 py-2 text-sm text-white">Send edited</button>
          <button onClick={() => decide("reject")} className="rounded bg-slate-600 px-3 py-2 text-sm text-white">Reject</button>
        </div>
        {msg && <p role="status" className="text-sm text-slate-700">{msg}</p>}
      </section>
    </main>
  );
}
