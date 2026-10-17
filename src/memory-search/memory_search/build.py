"""`memory-search build`: 塊に切り、埋め込みと全文検索の索引を作って、使う側との約束（manifest.json）と一緒に置く。

索引は md から作る捨ててよい派生物。埋め込みは文の sha256 で使い回すので、2回目からは変わった塊だけを埋め込む。
埋め込みが揃わなければ、前の索引を残して失敗にする（全文検索だけの索引に落とさない）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import sqlite3
import struct
import subprocess
import sys
import time
import unicodedata
import urllib.request
from datetime import datetime
from pathlib import Path

from memory_search import workspace as paths
from memory_search.chunk import Chunk, chunk_file, target_files

SCHEMA = 1
MODEL = "hf.co/Abiray/Nemotron-3-Embed-8B-GGUF:Q8_0"
DIM = 4096
LOCAL_URL = "http://127.0.0.1:11434/api/embed"
PASSAGE_PREFIX = "passage: "  # モデルの説明書きの決まり。問いには "query: " を付ける
QUERY_PREFIX = "query: "
NUM_CTX = 4096  # 1塊は約1,000字なので足りる。大きくするとメモリを取る
BATCH = 16
MIN_FILES = 10

FTS_RULE = (
    "bigram-v1: NFKC で正規化して小文字にし、英数字の並びは1語、それ以外の文字（漢字・かな・記号でない字）の並びは"
    "2文字ずつ重ねて区切る（1文字だけならその1文字）。語は空白で区切って FTS5 の unicode61（remove_diacritics 0）に入れる。"
)
TOKEN_RE = re.compile(r"[0-9a-z]+|[^\W0-9a-z_]+")


def fts_tokens(text: str) -> list[str]:
    """全文検索の語。使う側も同じ決まり（FTS_RULE）で問いを区切る。"""
    out = []
    for run in TOKEN_RE.findall(unicodedata.normalize("NFKC", text).lower()):
        if run.isascii() or len(run) == 1:
            out.append(run)
        else:
            out.extend(run[i : i + 2] for i in range(len(run) - 1))
    return out


def embed_text(chunk: Chunk) -> str:
    return f"{PASSAGE_PREFIX}{chunk.context()}\n{chunk.text}"


# ---------------------------------------------------------------- 埋め込み


def ollama_embed(texts: list[str]) -> list[list[float]]:
    body = json.dumps({"model": MODEL, "input": texts, "truncate": True, "options": {"num_ctx": NUM_CTX}}).encode()
    request = urllib.request.Request(LOCAL_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=600) as response:
        vectors = json.loads(response.read())["embeddings"]
    if len(vectors) != len(texts) or any(len(v) != DIM for v in vectors):
        raise RuntimeError("embedding_response_invalid")
    return vectors


def ensure_local_ollama() -> None:
    """手元の Ollama が止まっていれば start_ollama.mjs で起こす。"""
    try:
        socket.create_connection(("127.0.0.1", 11434), timeout=3).close()
        return
    except OSError:
        pass
    subprocess.run(["/opt/homebrew/bin/node", str(Path(__file__).resolve().parents[1] / "start_ollama.mjs")],
                   check=True, capture_output=True, timeout=30)
    for _ in range(60):
        try:
            socket.create_connection(("127.0.0.1", 11434), timeout=1).close()
            return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError("ollama_start_timeout")


def fill_cache(texts: dict[str, str], cache_path: Path, embed=ollama_embed) -> None:
    """texts（sha256 → 文）の埋め込みを cache_path に揃える。足りない分だけ埋め込み、バッチごとに保存する（止まっても続きから）。"""
    db = sqlite3.connect(cache_path)
    cache_path.chmod(0o600)
    db.execute("CREATE TABLE IF NOT EXISTS vectors (model TEXT, sha TEXT, vector BLOB, PRIMARY KEY (model, sha))")
    have = {sha for (sha,) in db.execute("SELECT sha FROM vectors WHERE model=?", (MODEL,))}
    missing = [sha for sha in texts if sha not in have]
    if missing:
        ensure_local_ollama()
    batches = [missing[i : i + BATCH] for i in range(0, len(missing), BATCH)]
    started, done = time.time(), 0

    def run(batch: list[str]) -> list[tuple[str, bytes]]:
        vectors = embed([texts[sha] for sha in batch])
        return [(sha, struct.pack(f"{DIM}f", *v)) for sha, v in zip(batch, vectors)]

    try:
        for batch in batches:
            rows = run(batch)
            db.executemany("INSERT OR REPLACE INTO vectors VALUES (?, ?, ?)", [(MODEL, sha, blob) for sha, blob in rows])
            db.commit()
            done += len(rows)
            if done % (BATCH * 20) < BATCH or done == len(missing):
                rate = done / max(time.time() - started, 1e-9)
                print(f"埋め込み {done}/{len(missing)}（{rate:.1f} 塊/秒、残り約 {(len(missing) - done) / max(rate, 1e-9) / 60:.0f} 分）",
                      file=sys.stderr, flush=True)
    finally:
        db.close()


def prune_cache(texts: dict[str, str], cache_path: Path) -> None:
    """今の塊に使われていない埋め込みを消す（索引ができた後だけ呼ぶ）。"""
    db = sqlite3.connect(cache_path)
    try:
        db.execute("CREATE TEMP TABLE keep (sha TEXT PRIMARY KEY)")
        db.executemany("INSERT INTO keep VALUES (?)", ((sha,) for sha in texts))
        db.execute("DELETE FROM vectors WHERE model != ? OR sha NOT IN (SELECT sha FROM keep)", (MODEL,))
        db.commit()
        db.execute("VACUUM")
    finally:
        db.close()


# ---------------------------------------------------------------- 書き出し


def write_index(chunks: list[Chunk], shas: list[str | None], cache_path: Path, out: Path) -> None:
    import sqlite_vec

    temp = out.with_name(f".{out.name}.{os.getpid()}.tmp")
    temp.unlink(missing_ok=True)
    try:
        db = sqlite3.connect(temp)
        try:
            db.enable_load_extension(True)
            sqlite_vec.load(db)
            db.execute("ATTACH DATABASE ? AS cache", (f"file:{cache_path}?mode=ro",))
            db.executescript(f"""
                CREATE TABLE chunks (id INTEGER PRIMARY KEY, path TEXT, line_start INTEGER, line_end INTEGER, layer TEXT,
                  date TEXT, speaker TEXT, status TEXT, title TEXT, heading TEXT, text TEXT, embedded INTEGER);
                CREATE VIRTUAL TABLE chunks_fts USING fts5(tokens, content='', tokenize='unicode61 remove_diacritics 0');
                CREATE VIRTUAL TABLE chunk_vectors USING vec0(embedding float[{DIM}] distance_metric=cosine);
            """)
            for rowid, (c, sha) in enumerate(zip(chunks, shas), 1):
                db.execute("INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                           (rowid, c.path, c.line_start, c.line_end, c.layer, c.date, c.speaker, c.status, c.title,
                            c.heading, c.text, int(sha is not None)))
                db.execute("INSERT INTO chunks_fts(rowid, tokens) VALUES (?, ?)", (rowid, " ".join(fts_tokens(f"{c.context()}\n{c.text}"))))
                if sha is not None:
                    row = db.execute("SELECT vector FROM cache.vectors WHERE model=? AND sha=?", (MODEL, sha)).fetchone()
                    if row is None:
                        raise RuntimeError("embedding_missing")
                    db.execute("INSERT INTO chunk_vectors(rowid, embedding) VALUES (?, ?)", (rowid, row[0]))
            db.commit()
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("index_integrity_failed")
        finally:
            db.close()
        temp.chmod(0o600)
        temp.replace(out)
    finally:
        temp.unlink(missing_ok=True)  # 途中で止まったときに作りかけを残さない


def write_json(path: Path, data: dict) -> None:
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.chmod(0o600)
    temp.replace(path)


def build(out_dir: Path, embed=ollama_embed) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_path = out_dir / "state.json"
    files = target_files()
    if len(files) < MIN_FILES:
        raise RuntimeError(f"too_few_source_files:{len(files)}")
    chunks: list[Chunk] = []
    dropped = 0
    scheduled: dict[str, bool] = {}  # 日をまたいで続く定時処理の会話も外すため、全ファイルで1つ（target_files は日の順）
    for path in files:
        got, lost = chunk_file(path, scheduled)
        chunks += got
        dropped += lost
    shas = [hashlib.sha256(embed_text(c).encode()).hexdigest() if c.embed else None for c in chunks]
    texts = {sha: embed_text(c) for c, sha in zip(chunks, shas) if sha}
    print(f"{len(files)} ファイル・{len(chunks)} 塊（埋め込む文 {len(texts)}）", file=sys.stderr, flush=True)
    cache_path = out_dir / "embeddings.sqlite"
    fill_cache(texts, cache_path, embed)
    write_index(chunks, shas, cache_path, out_dir / "index.sqlite")
    prune_cache(texts, cache_path)
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    manifest = {
        "schema": SCHEMA,
        "built_at": now,
        "index": "index.sqlite",
        "tables": {
            "chunks": "id・path（Workspace からの相対）・line_start・line_end（1始まり・両端を含む）・layer・date・speaker・status（current か archive）・title・heading・text・embedded",
            "chunks_fts": "rowid が chunks.id。tokens 列に fts.rule で区切った語",
            "chunk_vectors": "rowid が chunks.id。sqlite-vec の vec0、cosine",
        },
        "embedding": {"model": MODEL, "dim": DIM, "query_prefix": QUERY_PREFIX, "passage_prefix": PASSAGE_PREFIX,
                      "endpoint": "Ollama /api/embed", "num_ctx": NUM_CTX},
        "fts": {"rule": FTS_RULE},
        # embedded_chunks はベクトルを持つ塊の数、embedded_texts はそのうち中身の違う文の数（同じ文の塊は1回だけ埋め込む）
        "counts": {"files": len(files), "chunks": len(chunks), "embedded_chunks": sum(sha is not None for sha in shas),
                   "embedded_texts": len(texts), "secret_dropped": dropped},
    }
    write_json(out_dir / "manifest.json", manifest)
    state = {"status": "ok", "built_at": now, **manifest["counts"]}
    write_json(state_path, state)
    return state


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="memory-search build")
    p.add_argument("--out", type=Path, default=None, help="索引を置く所（既定 data/memory-search/index）")
    a = p.parse_args(argv)
    out = a.out or paths.index_dir()
    try:
        state = build(out)
    except Exception as error:
        # 例外の文には元の本文が入り得るので、種類だけを残す。前の索引はそのまま。
        write_json(out / "state.json", {"status": "failed", "at": datetime.now().astimezone().isoformat(timespec="seconds"),
                                        "error": type(error).__name__})
        raise
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0
