"""data にある記憶の索引を引く。約束（manifest.json）を確かめ、意味検索と全文検索を混ぜ、reranker で並べ直す。"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import struct
import unicodedata
import urllib.request
from pathlib import Path

SCHEMA = 1  # 読める manifest の schema
OLLAMA_URL = "http://127.0.0.1:11434/api/embed"
# 問いは、索引と同じモデルの軽い版で埋め込む（会話の間ずっと読み込んでおくため。問題集で点が変わらないことを確かめた）
QUERY_MODEL = "hf.co/Abiray/Nemotron-3-Embed-8B-GGUF:Q4_K_M"
MODEL_FAMILY = "hf.co/Abiray/Nemotron-3-Embed-8B-GGUF:"
EMBED_TIMEOUT = 20  # 秒。Ollama が固まっていても、hook を長く待たせない（読み込んだままなら1秒かからない）
CANDIDATES = 50  # 意味検索・全文検索それぞれの候補の数
RERANK_DEPTH = 30  # reranker で読み比べる数
CURRENT_BONUS = 1.0  # 今を表す置き場（20_identity・進行中の案件とタスク）に足す点（reranker の点を標準化した単位）
RRF_K = 60
# 閲覧の記録（ブラウザ・動画サイトの訪問の表）は題名の語の一致だけで上位に来て、一般の問いの雑音になる。
# 閲覧を聞く問いでも上位にほとんど出ず、要点は 10_daily にあるので、候補に入れない
BROWSING = "SecondBrain/50_media/browsing/"
TOKEN_RE = re.compile(r"[0-9a-z]+|[^\W0-9a-z_]+")


def index_dir() -> Path:
    ws = Path(os.environ.get("WORKSPACE") or "/Users/taro/Workspace")
    return Path(os.environ.get("MEMORY_RECALL_INDEX") or ws / "data" / "memory-search" / "index")


def fts_tokens(text: str) -> list[str]:
    """manifest の fts.rule（bigram-v1）どおりに区切る。"""
    out = []
    for run in TOKEN_RE.findall(unicodedata.normalize("NFKC", text).lower()):
        if run.isascii() or len(run) == 1:
            out.append(run)
        else:
            out.extend(run[i : i + 2] for i in range(len(run) - 1))
    return out


class Index:
    def __init__(self, directory: Path | None = None):
        directory = directory or index_dir()
        self.manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if (self.manifest.get("schema") != SCHEMA or not self.manifest["fts"]["rule"].startswith("bigram-v1")
                or not self.manifest["embedding"]["model"].startswith(MODEL_FAMILY)):
            raise RuntimeError(f"index_contract_mismatch:schema={self.manifest.get('schema')}")
        self.manifest_path = directory / "manifest.json"
        self.manifest_mtime = self.manifest_path.stat().st_mtime
        import sqlite_vec

        self.db = sqlite3.connect(f"file:{directory / self.manifest['index']}?mode=ro", uri=True, check_same_thread=False)
        self.db.enable_load_extension(True)
        sqlite_vec.load(self.db)
        self.db.row_factory = sqlite3.Row

    def embed_query(self, query: str, url: str = OLLAMA_URL) -> list[float]:
        e = self.manifest["embedding"]
        body = json.dumps({"model": QUERY_MODEL, "input": [e["query_prefix"] + query], "truncate": True,
                           "keep_alive": -1, "options": {"num_ctx": e["num_ctx"]}}).encode()  # 手放さずに読み込んだままにする
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=EMBED_TIMEOUT) as response:
            return json.loads(response.read())["embeddings"][0]

    def stale(self) -> bool:
        """索引が作り直されたか（memory-search は manifest を最後に書き直す）。"""
        try:
            return self.manifest_path.stat().st_mtime != self.manifest_mtime
        except OSError:
            return False

    def query_vector(self, query: str) -> bytes:
        return struct.pack(f"{self.manifest['embedding']['dim']}f", *self.embed_query(query))

    def dense(self, vector: bytes, k: int = CANDIDATES) -> list[int]:
        sql = "SELECT rowid FROM chunk_vectors WHERE embedding MATCH ? AND k=? ORDER BY distance"
        return [r[0] for r in self.db.execute(sql, (vector, k))]

    def lexical(self, query: str, k: int = CANDIDATES) -> list[int]:
        tokens = list(dict.fromkeys(fts_tokens(query)))
        if not tokens:
            return []
        match = " OR ".join('"' + t.replace('"', '""') + '"' for t in tokens)
        sql = "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts) LIMIT ?"
        return [r[0] for r in self.db.execute(sql, (match, k))]

    def rows(self, ids: list[int]) -> list[dict]:
        found = {r["id"]: dict(r) for r in self.db.execute(
            f"SELECT * FROM chunks WHERE id IN ({','.join('?' * len(ids))})", ids)} if ids else {}
        return [found[i] for i in ids if i in found]


def rrf(*lists: list[int]) -> list[int]:
    """順位の逆数で混ぜる。どちらでも上位の物が上に来る。"""
    score: dict[int, float] = {}
    for ranked in lists:
        for rank, item in enumerate(ranked, 1):
            score[item] = score.get(item, 0.0) + 1.0 / (RRF_K + rank)
    return sorted(score, key=lambda item: -score[item])


def passage(row: dict) -> str:
    where = " > ".join(x for x in (row["layer"], row["title"], row["heading"], row["speaker"]) if x)
    head = f"[{row['date']}] {where}" if row["date"] else where
    return f"{head}\n{row['text']}"


def is_current(row: dict) -> bool:
    return row["layer"] == "20_identity" or (row["layer"] in ("30_projects", "40_tasks") and row["status"] == "current")


def search(index: Index, query: str, *, limit: int = 8, reranker=None) -> dict:
    status = {}
    try:
        dense = index.dense(index.query_vector(query))
        status["dense"] = "ok"
    except OSError as error:  # Ollama が止まっている等。全文検索だけで返し、そう書く
        dense, status["dense"] = [], f"unavailable:{type(error).__name__}"
    fused = [r for r in index.rows(rrf(dense, index.lexical(query))) if not r["path"].startswith(BROWSING)][: max(limit, RERANK_DEPTH)]
    if reranker is not None and fused:
        scores = reranker.score(query, [passage(r) for r in fused])
        mean = sum(scores) / len(scores)
        spread = (sum((v - mean) ** 2 for v in scores) / len(scores)) ** 0.5 or 1.0
        for row, value in zip(fused, scores):
            row["rerank_score"] = round(float(value), 4)
            # 同じ話題の古い記録と今の記録が並んだとき、今を表す置き場を上に出す
            row["_order"] = (value - mean) / spread + CURRENT_BONUS * is_current(row)
        fused = sorted(fused, key=lambda r: -r["_order"])
        status["rerank"] = reranker.name
    results = [{k: r[k] for k in ("path", "line_start", "line_end", "layer", "date", "speaker", "status", "title", "heading", "text")}
               | ({"rerank_score": r["rerank_score"]} if "rerank_score" in r else {}) for r in fused[:limit]]
    return {"query": query, "index_built_at": index.manifest["built_at"], "status": status, "results": results}
