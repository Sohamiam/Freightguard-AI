# FreightGuard Scorecard

**OCR** (regex-baseline): doc exact-match 90.91%, field F1 0.929

**ML** (test split)

| model | PR-AUC | F1 | P@K |
|---|---|---|---|
| logreg | 0.705 | 0.585 | 0.667 |
| xgboost | 0.716 | 0.800 | 0.667 |
| isolation_forest | 0.697 | 0.667 | 0.667 |

**Agent**

- detection precision 0.984, recall 0.849
- math within $15: 1.000; citation accuracy: 1.000
- audit chain valid: True
- est. tokens/1000 disputes: {'input': 254444, 'output': 63111}; est. USD/1000: $0.0507
- Deterministic template drafter (no LLM) in this run; token/USD figures are estimates.