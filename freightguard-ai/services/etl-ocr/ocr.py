"""Gemini multimodal extraction with schema validation, SHA-256 idempotency and a DLQ for failed parses."""
from __future__ import annotations
import json, os, time
from pathlib import Path
import yaml
from pydantic import ValidationError
from schemas import ExtractedInvoice

PROMPT = yaml.safe_load((Path(__file__).parents[2] / "prompts/v1/ocr_invoice_extract.yaml").read_text())

def sha256_file(path: Path) -> str:
    import hashlib; return hashlib.sha256(path.read_bytes()).hexdigest()

def extract(pdf: Path, seen: set[str], dlq: Path, client=None) -> dict | None:
    digest = sha256_file(pdf)
    if digest in seen:
        return None  # idempotent: duplicate ingestion blocked
    t0 = time.time()
    try:
        if client is None:
            from google import genai
            client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        from google.genai import types
        resp = client.models.generate_content(
            model=PROMPT["model"],
            contents=[types.Part.from_bytes(data=pdf.read_bytes(), mime_type="application/pdf"), PROMPT["user"]],
            config=types.GenerateContentConfig(system_instruction=PROMPT["system"], temperature=0,
                                               response_mime_type="application/json", response_schema=ExtractedInvoice))
        inv = ExtractedInvoice.model_validate_json(resp.text)
        usage = getattr(resp, "usage_metadata", None)
        seen.add(digest)
        return {"hash": digest, "invoice": json.loads(inv.model_dump_json()),
                "trace": {"prompt": f'{PROMPT["id"]}@{PROMPT["version"]}', "latency_s": round(time.time() - t0, 3),
                          "in_tokens": getattr(usage, "prompt_token_count", None), "out_tokens": getattr(usage, "candidates_token_count", None)}}
    except (ValidationError, KeyError, Exception) as e:  # noqa: BLE001 - everything goes to DLQ
        dlq.mkdir(parents=True, exist_ok=True)
        (dlq / f"{digest}.json").write_text(json.dumps({"file": pdf.name, "error": repr(e)}))
        return None
