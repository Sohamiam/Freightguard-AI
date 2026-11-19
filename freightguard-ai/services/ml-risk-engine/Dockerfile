FROM python:3.11-slim
WORKDIR /app
COPY services/ml-risk-engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/ml-risk-engine/ services/ml-risk-engine/
COPY data/seed/historical_invoices.csv data/seed/historical_invoices.csv
RUN python services/ml-risk-engine/train.py
CMD ["uvicorn", "app:app", "--app-dir", "services/ml-risk-engine", "--host", "0.0.0.0", "--port", "8001"]
