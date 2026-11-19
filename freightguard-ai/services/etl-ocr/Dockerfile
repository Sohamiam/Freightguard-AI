FROM python:3.11-slim
WORKDIR /app
COPY services/etl-ocr/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt fastapi uvicorn
COPY services/etl-ocr services/etl-ocr
COPY prompts prompts
COPY data/seed/pdf_invoices data/seed/pdf_invoices
CMD ["uvicorn", "main:app", "--app-dir", "services/etl-ocr", "--host", "0.0.0.0", "--port", "8003"]
