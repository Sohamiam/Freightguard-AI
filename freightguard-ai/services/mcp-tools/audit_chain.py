"""Append-only, hash-chained audit log. Storage-agnostic core + Postgres DDL."""
from __future__ import annotations
import hashlib, json, time
from dataclasses import dataclass, field

GENESIS = "0" * 64

POSTGRES_DDL = """
CREATE TABLE IF NOT EXISTS audit_log (
  seq BIGSERIAL PRIMARY KEY,
  ts DOUBLE PRECISION NOT NULL,
  actor TEXT NOT NULL,
  event TEXT NOT NULL,
  payload JSONB NOT NULL,
  prev_hash CHAR(64) NOT NULL,
  entry_hash CHAR(64) NOT NULL UNIQUE
);
CREATE OR REPLACE FUNCTION audit_log_immutable() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'audit_log is append-only'; END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS audit_no_update ON audit_log;
CREATE TRIGGER audit_no_update BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();
"""

def _h(prev: str, ts: float, actor: str, event: str, payload: dict) -> str:
    body = json.dumps([prev, ts, actor, event, payload], sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()

@dataclass
class AuditChain:
    entries: list[dict] = field(default_factory=list)

    def append(self, actor: str, event: str, payload: dict, ts: float | None = None) -> dict:
        ts = time.time() if ts is None else ts
        prev = self.entries[-1]["entry_hash"] if self.entries else GENESIS
        e = {"ts": ts, "actor": actor, "event": event, "payload": payload,
             "prev_hash": prev, "entry_hash": _h(prev, ts, actor, event, payload)}
        self.entries.append(e)
        return e

    def verify(self) -> tuple[bool, int | None]:
        prev = GENESIS
        for i, e in enumerate(self.entries):
            if e["prev_hash"] != prev or e["entry_hash"] != _h(prev, e["ts"], e["actor"], e["event"], e["payload"]):
                return False, i
            prev = e["entry_hash"]
        return True, None
