# FreightGuard AI

Freight invoice audit and dispute engine: detects duplicate invoices, unapproved fuel surcharges, detention miscalculation, rate-card drift and accessorial stacking; drafts a cited dispute; pauses for human approval before any email is sent.

## Quick start (no Docker)
    pip install pandas openpyxl numpy scikit-learn xgboost imbalanced-learn shap fastapi uvicorn httpx pydantic reportlab pytest pyyaml pypdf joblib \
                langgraph langgraph-checkpoint-postgres "psycopg[binary]" pgvector flashrank google-genai "mcp<2"
    python data/generator/generate.py        # seed data -> data/seed/
    python evals/run_all_evals.py            # OCR + ML + agent scorecard -> evals/reports/
    pytest -q tests                          # Python tests
    (cd services/node-api && npm i && npm test)
    (cd apps/ops-portal && npm i && npm test && npm run dev)

## Full stack
    python data/generator/generate.py && docker compose up --build
Portal http://localhost:5173, n8n http://localhost:5678 (import `workflows/n8n/*.json`), Postgres 5432. Set `GEMINI_API_KEY` for live OCR and embeddings.

## Verification status (be precise about this in interviews)
Verified in the build sandbox: pytest (10), Vitest node-api (5), Vitest portal (3) plus production build, eval scorecard, agent HTTP flow with MemorySaver, MCP tool call, n8n JSON and compose/CI YAML syntax.
NOT verified (no Docker or Postgres in the sandbox): `docker compose up`, PostgresSaver and pgvector/tsvector SQL against a live database, `bi/powerbi/views.sql`, Gemini OCR and embeddings, FlashRank model download (the eval ran the lexical fallback; the report records `reranker_backend`).

## Known gaps
- The agent calls `services/mcp-tools/billing.py` in-process; the MCP server exposes the same functions but the graph does not consume it through an MCP client yet.
- Drafting uses a deterministic template unless an `llm` callable is passed to `build_graph`; the Gemini drafter is not wired in.
- No OpenTelemetry/Langfuse exporter: OCR returns latency and token fields per call, and prompts are versioned in `prompts/v1/`.
- All data is synthetic; metrics are not evidence of real-world performance. Power BI `.pbix` is a spec, not a binary.
