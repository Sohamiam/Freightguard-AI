"""Hybrid RAG: pgvector dense + tsvector full-text, fused with RRF, then reranked.
Pure functions (chunking, RRF, rerank, embedding) are testable without a database."""
from __future__ import annotations
import hashlib, math, os, re
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Chunk:
    carrier: str
    clause: str      # e.g. "5.1"
    text: str
    @property
    def id(self) -> str: return f"{self.carrier}:{self.clause}"

CLAUSE_RE = re.compile(r"^(\d+\.\d+)\s+(.*)$")

def chunk_msa(carrier: str, markdown: str) -> list[Chunk]:
    """One chunk per numbered clause, prefixed with its section heading so clause numbers stay searchable."""
    out, heading = [], ""
    for line in markdown.splitlines():
        if line.startswith("## "): heading = line[3:].strip()
        m = CLAUSE_RE.match(line.strip())
        if m: out.append(Chunk(carrier, m.group(1), f"MSA {m.group(1)} [{heading}] {m.group(2)}"))
    return out

DIM = 256
def embed(text: str) -> list[float]:
    """Gemini embedding when GEMINI_API_KEY is set; otherwise a deterministic hashed bag-of-words vector (offline/tests)."""
    if os.getenv("GEMINI_API_KEY"):
        from google import genai
        r = genai.Client(api_key=os.environ["GEMINI_API_KEY"]).models.embed_content(
            model="text-embedding-004", contents=text, config={"output_dimensionality": DIM})
        return list(r.embeddings[0].values)
    v = [0.0] * DIM
    for tok in re.findall(r"[a-z0-9\.\-]+", text.lower()):
        v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % DIM] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]

def rrf(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion: score(d) = sum 1/(k + rank)."""
    s: dict[str, float] = {}
    for ranked in rankings:
        for r, doc in enumerate(ranked, 1): s[doc] = s.get(doc, 0.0) + 1.0 / (k + r)
    return sorted(s.items(), key=lambda t: -t[1])

_RANKER: list = []   # [] = untried, [None] = unavailable (e.g. model download blocked), [Ranker] = ready
RERANKER_BACKEND = "lexical-fallback"

def _ranker():
    global RERANKER_BACKEND
    if not _RANKER:
        try:
            from flashrank import Ranker
            _RANKER.append(Ranker()); RERANKER_BACKEND = "flashrank"
        except Exception:
            _RANKER.append(None)
    return _RANKER[0]

def rerank(query: str, chunks: list[Chunk], top_k: int = 3) -> list[Chunk]:
    """FlashRank cross-encoder when its model is available; lexical-overlap fallback keeps the pipeline runnable offline."""
    try:
        from flashrank import RerankRequest
        ranker = _ranker()
        if ranker is None: raise RuntimeError("flashrank unavailable")
        res = ranker.rerank(RerankRequest(query=query, passages=[{"id": c.id, "text": c.text} for c in chunks]))
        order = {r["id"]: i for i, r in enumerate(res)}
        return sorted(chunks, key=lambda c: order[c.id])[:top_k]
    except Exception:
        q = set(re.findall(r"[a-z0-9\.\-]+", query.lower()))
        return sorted(chunks, key=lambda c: -len(q & set(re.findall(r"[a-z0-9\.\-]+", c.text.lower()))))[:top_k]

SCHEMA = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS msa_chunks (
  id TEXT PRIMARY KEY, carrier TEXT NOT NULL, clause TEXT NOT NULL, text TEXT NOT NULL,
  embedding vector({DIM}), tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED);
CREATE INDEX IF NOT EXISTS msa_tsv_idx ON msa_chunks USING GIN (tsv);
"""

class PgHybridStore:
    def __init__(self, dsn: str):
        import psycopg
        from pgvector.psycopg import register_vector
        self.conn = psycopg.connect(dsn, autocommit=True); self.conn.execute(SCHEMA); register_vector(self.conn)

    def upsert(self, chunks: list[Chunk]):
        for c in chunks:
            self.conn.execute("INSERT INTO msa_chunks (id,carrier,clause,text,embedding) VALUES (%s,%s,%s,%s,%s) "
                              "ON CONFLICT (id) DO UPDATE SET text=EXCLUDED.text, embedding=EXCLUDED.embedding",
                              (c.id, c.carrier, c.clause, c.text, embed(c.text)))

    def search(self, query: str, carrier: str, n: int = 8) -> list[Chunk]:
        dense = self.conn.execute("SELECT id,carrier,clause,text FROM msa_chunks WHERE carrier=%s "
                                  "ORDER BY embedding <=> %s::vector LIMIT %s", (carrier, embed(query), n)).fetchall()
        sparse = self.conn.execute("SELECT id,carrier,clause,text FROM msa_chunks WHERE carrier=%s "
                                   "AND tsv @@ plainto_tsquery('english',%s) "
                                   "ORDER BY ts_rank_cd(tsv, plainto_tsquery('english',%s)) DESC LIMIT %s",
                                   (carrier, query, query, n)).fetchall()
        by_id = {r[0]: Chunk(r[1], r[2], r[3]) for r in dense + sparse}
        fused = rrf([[r[0] for r in dense], [r[0] for r in sparse]])
        return [by_id[i] for i, _ in fused]

class MemoryHybridStore:
    """Same interface, in-memory: cosine for dense, term overlap for sparse. Used by tests and offline evals."""
    def __init__(self, chunks: list[Chunk] | None = None): self.chunks: list[Chunk] = chunks or []
    def upsert(self, chunks: list[Chunk]): self.chunks = [c for c in self.chunks if c.id not in {x.id for x in chunks}] + chunks
    def search(self, query: str, carrier: str, n: int = 8) -> list[Chunk]:
        pool = [c for c in self.chunks if c.carrier == carrier]; qv = embed(query)
        dense = sorted(pool, key=lambda c: -sum(a * b for a, b in zip(qv, embed(c.text))))[:n]
        q = set(re.findall(r"[a-z0-9\.\-]+", query.lower()))
        sparse = [c for c in sorted(pool, key=lambda c: -len(q & set(re.findall(r"[a-z0-9\.\-]+", c.text.lower())))) if q & set(re.findall(r"[a-z0-9\.\-]+", c.text.lower()))][:n]
        by_id = {c.id: c for c in pool}
        return [by_id[i] for i, _ in rrf([[c.id for c in dense], [c.id for c in sparse]])]
