import { describe, it, expect } from "vitest";
import { shapBars, totalOvercharge, money } from "./lib.js";
describe("lib", () => {
  it("scales shap bars relative to the largest driver", () => {
    const b = shapBars([{ feature: "a", shap: 2 }, { feature: "b", shap: -1 }]);
    expect(b[0].width).toBe(100); expect(b[1].width).toBe(50); expect(b[1].up).toBe(false);
  });
  it("sums overcharges", () => expect(totalOvercharge([{ overcharge: "65.00" }, { overcharge: "120.00" }])).toBe(185));
  it("formats money", () => expect(money(1234.5)).toBe("$1,234.50"));
});
