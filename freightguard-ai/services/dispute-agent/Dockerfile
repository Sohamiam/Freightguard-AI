FROM python:3.11-slim
WORKDIR /app
COPY services/dispute-agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/dispute-agent services/dispute-agent
COPY services/mcp-tools services/mcp-tools
COPY prompts prompts
COPY data/seed/msa data/seed/msa
CMD ["uvicorn", "main:app", "--app-dir", "services/dispute-agent", "--host", "0.0.0.0", "--port", "8002"]
