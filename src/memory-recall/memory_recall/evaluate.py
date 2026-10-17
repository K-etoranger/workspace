"""問題集を解き、上位5件に正解の行を含む塊が入ったかを数える。

問題集は JSON の並び。1問は {"id", "category", "query", "gold": [{"path", "lines": [始, 終]}], "historical": [...]}。
historical は「古い記録」の場所で、正解より上に出たら knowledge_update の外れとして数える。
exclude_after を渡すと、その日以降の 00_inbox（会話・連絡）を結果から除いて採点する。問題集を作った会話そのものが
索引に入り、問いと答えがそのまま当たってしまうのを避けるため（採点だけの決まりで、引き方には入れない）。
"""

from __future__ import annotations

import json
from pathlib import Path

from memory_recall.search import Index, search


def overlaps(row: dict, place: dict) -> bool:
    return row["path"] == place["path"] and row["line_start"] <= place["lines"][1] and row["line_end"] >= place["lines"][0]


def leaked(row: dict, exclude_after: str) -> bool:
    return bool(exclude_after) and row["layer"].startswith("00_inbox") and row["date"][:10] >= exclude_after


def evaluate(questions: list[dict], index: Index, reranker=None, k: int = 5, exclude_after: str = "") -> dict:
    rows = []
    for q in questions:
        results = [r for r in search(index, q["query"], limit=30, reranker=reranker)["results"] if not leaked(r, exclude_after)][:10]
        rank = next((i for i, r in enumerate(results, 1) if any(overlaps(r, g) for g in q["gold"])), None)
        old = next((i for i, r in enumerate(results, 1) if any(overlaps(r, h) for h in q.get("historical", []))), None)
        rows.append({"id": q["id"], "category": q["category"], "rank": rank, "historical_rank": old,
                     "top": [f"{r['path']}:{r['line_start']}" for r in results[:3]]})
    hit = [r for r in rows if r["rank"] and r["rank"] <= k]
    by_category = {}
    for c in sorted({r["category"] for r in rows}):
        group = [r for r in rows if r["category"] == c]
        by_category[c] = f"{sum(1 for r in group if r['rank'] and r['rank'] <= k)}/{len(group)}"
    return {
        f"recall@{k}": round(len(hit) / len(rows), 3),
        "mrr@10": round(sum(1 / r["rank"] for r in rows if r["rank"]) / len(rows), 3),
        "by_category": by_category,
        "historical_above_gold": [r["id"] for r in rows if r["historical_rank"] and (not r["rank"] or r["historical_rank"] < r["rank"])],
        "rows": rows,
    }


def load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))
