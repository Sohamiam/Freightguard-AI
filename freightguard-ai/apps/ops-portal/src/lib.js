/** Scale SHAP values to bar widths (0-100) and sign them for colouring. */
export function shapBars(drivers) {
  const max = Math.max(...drivers.map((d) => Math.abs(d.shap)), 1e-9);
  return drivers.map((d) => ({ ...d, width: Math.round((Math.abs(d.shap) / max) * 100), up: d.shap > 0 }));
}
export const money = (n) => Number(n).toLocaleString("en-US", { style: "currency", currency: "USD" });
export const totalOvercharge = (findings) => findings.reduce((s, f) => s + Number(f.overcharge), 0);

export async function api(path, opts) {
  const r = await fetch(path, { headers: { "content-type": "application/json" }, ...opts });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}
