import json
import sqlite3
import struct
import sys
from pathlib import Path

import pytest
import sqlite_vec

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from memory_recall import search as s
from memory_recall.evaluate import evaluate

DIM = 4


def make_index(directory: Path, rows: list[dict], schema: int = 1) -> Path:
    """memory-search の manifest の約束どおりの小さな索引。"""
    directory.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(directory / "index.sqlite")
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.executescript(f"""
        CREATE TABLE chunks (id INTEGER PRIMARY KEY, path TEXT, line_start INTEGER, line_end INTEGER, layer TEXT,
          date TEXT, speaker TEXT, status TEXT, title TEXT, heading TEXT, text TEXT, embedded INTEGER);
        CREATE VIRTUAL TABLE chunks_fts USING fts5(tokens, content='', tokenize='unicode61 remove_diacritics 0');
        CREATE VIRTUAL TABLE chunk_vectors USING vec0(embedding float[{DIM}] distance_metric=cosine);
    """)
    for i, r in enumerate(rows, 1):
        db.execute("INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?,?,1)", (i, r["path"], r["line"], r["line"], r["layer"], r.get("date", ""),
                                                                     "", r.get("status", "current"), "t", "", r["text"]))
        db.execute("INSERT INTO chunks_fts(rowid, tokens) VALUES (?, ?)", (i, " ".join(s.fts_tokens(r["text"]))))
        db.execute("INSERT INTO chunk_vectors(rowid, embedding) VALUES (?, ?)", (i, struct.pack(f"{DIM}f", *r["vec"])))
    db.commit()
    db.close()
    (directory / "manifest.json").write_text(json.dumps({
        "schema": schema, "built_at": "2026-10-04T00:00:00+09:00", "index": "index.sqlite",
        "embedding": {"model": "hf.co/Abiray/Nemotron-3-Embed-8B-GGUF:Q8_0", "dim": DIM, "query_prefix": "query: ", "passage_prefix": "passage: ", "num_ctx": 4096},
        "fts": {"rule": "bigram-v1: …"}}), encoding="utf-8")
    return directory


ROWS = [
    {"path": "SecondBrain/20_identity/profile.md", "line": 29, "layer": "20_identity", "text": "- 庭のトマトは今年も育てている。", "vec": [1, 0, 0, 0]},
    {"path": "SecondBrain/10_daily/2026/2026-07-21.md", "line": 14, "layer": "10_daily", "date": "2026-07-21", "text": "- トマトの苗を買った。", "vec": [0.9, 0.1, 0, 0]},
    {"path": "SecondBrain/30_projects/active/町内会の会報/メモ.md", "line": 21, "layer": "30_projects", "text": "- 第1号（ABCD-127）", "vec": [0, 0, 1, 0]},
    {"path": "SecondBrain/00_inbox/conversations/claude/2026-10-04.md", "line": 5, "layer": "00_inbox/conversations", "date": "2026-10-04 10:00", "text": "トマトってどうなった？", "vec": [1, 0, 0, 0]},
]


@pytest.fixture
def index(tmp_path, monkeypatch):
    make_index(tmp_path / "idx", ROWS)
    monkeypatch.setattr(s.Index, "embed_query", lambda self, q, url=s.OLLAMA_URL: [1.0, 0.0, 0.0, 0.0] if "トマト" in q else [0.0, 0.0, 1.0, 0.0])
    return s.Index(tmp_path / "idx")


def test_tokens_follow_manifest_rule():
    assert s.fts_tokens("ABCD-127 ってどの号") == ["abcd", "127", "って", "てど", "どの", "の号"]


def test_contract_mismatch_is_refused(tmp_path):
    make_index(tmp_path / "old", ROWS, schema=2)
    with pytest.raises(RuntimeError, match="index_contract_mismatch"):
        s.Index(tmp_path / "old")
    make_index(tmp_path / "other", ROWS)  # 問いを埋め込むモデルと別のモデルで作った索引は読まない
    manifest = json.loads((tmp_path / "other/manifest.json").read_text())
    manifest["embedding"]["model"] = "other-embed:latest"
    (tmp_path / "other/manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match="index_contract_mismatch"):
        s.Index(tmp_path / "other")


def test_search_mixes_dense_and_lexical(index):
    got = s.search(index, "ABCD-127 ってどの号だっけ", limit=2)
    assert got["results"][0]["path"].endswith("町内会の会報/メモ.md") and got["status"]["dense"] == "ok"


def test_ollama_down_falls_back_to_lexical(index, monkeypatch):
    def down(self, q, url=s.OLLAMA_URL):
        raise OSError("refused")
    monkeypatch.setattr(s.Index, "embed_query", down)
    got = s.search(index, "ABCD-127", limit=1)
    assert got["status"]["dense"].startswith("unavailable") and got["results"][0]["line_start"] == 21


def test_browsing_records_are_not_candidates(tmp_path, monkeypatch):
    rows = ROWS + [{"path": "SecondBrain/50_media/browsing/web/2026-08-27.md", "line": 84, "layer": "50_media",
                    "text": "| 19:00 | ABCD-127 - 動画サイト |", "vec": [0, 0, 1, 0]}]
    make_index(tmp_path / "idx", rows)
    monkeypatch.setattr(s.Index, "embed_query", lambda self, q, url=s.OLLAMA_URL: [0.0, 0.0, 1.0, 0.0])
    got = s.search(s.Index(tmp_path / "idx"), "ABCD-127", limit=5)
    assert got["results"] and not any("50_media/browsing" in r["path"] for r in got["results"])


def test_reranker_and_current_bonus_order(index):
    class Flat:  # どれも同じ点を付ける reranker。今を表す置き場の補正だけで順が決まる
        name = "flat"

        def score(self, query, passages):
            return [0.5] * len(passages)

    got = s.search(index, "トマトってどうなった", limit=4, reranker=Flat())
    assert got["results"][0]["layer"] == "20_identity"  # 点が並んだとき、今を表す置き場が上に来る


def test_evaluate_counts_lines_and_excludes_leaks(index):
    questions = [{"id": "A01", "category": "A", "query": "トマトってどうなった",
                  "gold": [{"path": "SecondBrain/20_identity/profile.md", "lines": [29, 29]}],
                  "historical": [{"path": "SecondBrain/10_daily/2026/2026-07-21.md", "lines": [14, 14]}]}]
    result = evaluate(questions, index, exclude_after="2026-10-04")
    assert result["recall@5"] == 1.0
    assert not any("2026-10-04" in t for t in result["rows"][0]["top"])  # 問題集を作った日の会話は採点に入れない


def test_hook_adds_first_ten_then_three_unseen(tmp_path, monkeypatch):
    from memory_recall import serve
    rows = [{"path": f"SecondBrain/10_daily/2026/2026-09-{i + 1:02d}.md", "line": 3, "layer": "10_daily",
             "date": f"2026-09-{i + 1:02d}", "text": f"- トマトの記録 {i}", "vec": [1, 0, 0, 0]} for i in range(20)]
    make_index(tmp_path / "idx", rows)
    monkeypatch.setattr(s.Index, "embed_query", lambda self, q, url=s.OLLAMA_URL: [1.0, 0.0, 0.0, 0.0])
    recall = serve.Recall(index_factory=lambda: s.Index(tmp_path / "idx"))
    first = recall.hook("abc", "トマトどうなった")
    second = recall.hook("abc", "トマトどうなった")
    other = recall.hook("xyz", "トマトどうなった")
    assert (first["count"], second["count"], other["count"]) == (10, 3, 10)
    paths = lambda r: {l.split("（")[0] for l in r["context"].split("\n") if l.startswith("- [")}
    assert not paths(first) & paths(second)  # 同じ会話で前に添えた物は添えない
    assert recall.hook("abc", " ")["count"] == 0
    assert recall.hook("new", "承認します。")["count"] == 0
    assert recall.hook("new", "トマトどうなった")["count"] == 10  # 返事だけの発言は、最初の発言として数えない


def test_reply_only_prompts_are_recognized():
    from memory_recall.serve import is_reply
    for p in ("承認します。", "OK", "ｏｋ！", "了解です。承認します。", "じゃあGoしてください", "今どう？", "では、次は？", "進めてください",
              "今どうなってる？", "OKです", "了解しました", "よろしくお願いします"):
        assert is_reply(p), p
    for p in ("5月の読書会について教えて", "先週の土曜は何をしたっけ？", "承認します。続きもお願いします",
              "Aは承認、Bは見送ります", "トークの1件はどうなった？", "それどうなった？"):
        assert not is_reply(p), p


def test_server_reloads_rebuilt_index_and_answers_over_http(tmp_path, monkeypatch):
    import threading
    import urllib.error
    import urllib.request
    from http.server import HTTPServer
    from memory_recall import serve
    make_index(tmp_path / "idx", ROWS)
    monkeypatch.setattr(s.Index, "embed_query", lambda self, q, url=s.OLLAMA_URL: [0.0, 0.0, 1.0, 0.0])
    recall = serve.Recall(index_factory=lambda: s.Index(tmp_path / "idx"))
    server = HTTPServer(("127.0.0.1", 0), serve.handler_for(recall))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    post = lambda path, data: json.loads(urllib.request.urlopen(urllib.request.Request(
        url + path, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})).read())
    assert post("/hook", {"session_id": "s1", "prompt": "ABCD-127 ってどの号"})["context"].count("町内会の会報") == 1
    before = recall.index
    import os, time
    time.sleep(0.01)
    os.utime(tmp_path / "idx/manifest.json")  # 索引が作り直された
    assert json.loads(urllib.request.urlopen(url + "/health").read())["ok"] and recall.index is not before
    forged = urllib.request.Request(url + "/health", headers={"Host": "evil.example:8767"})  # 手元以外の名前では答えない
    try:
        urllib.request.urlopen(forged)
        assert False
    except urllib.error.HTTPError as error:
        assert error.code == 403
    server.shutdown()
