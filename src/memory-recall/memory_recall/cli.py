"""memory-recall search <問い> [--limit N] [--no-rerank] [--json]
memory-recall eval <問題集.json> [--no-rerank] [--exclude-after YYYY-MM-DD] [--out <結果.json>]
memory-recall serve [--port 8767]"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from memory_recall.evaluate import evaluate, load
from memory_recall.search import Index, search


def reranker_of(no_rerank: bool):
    if no_rerank:
        return None
    from memory_recall.rerank import Reranker

    return Reranker()


def main(argv: list[str]) -> int:
    if argv[:1] == ["serve"]:
        from memory_recall.serve import main as serve

        return serve(argv[1:])
    p = argparse.ArgumentParser(prog="memory-recall")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=8)
    s.add_argument("--no-rerank", action="store_true", help="reranker を使わない（RRF の順のまま返す）")
    s.add_argument("--json", action="store_true")
    e = sub.add_parser("eval")
    e.add_argument("questions", type=Path)
    e.add_argument("--no-rerank", action="store_true")
    e.add_argument("--exclude-after", default="", help="この日以降の 00_inbox を採点で除く（問題集を作った日）")
    e.add_argument("--out", type=Path)
    a = p.parse_args(argv)
    index = Index()
    if a.command == "search":
        result = search(index, a.query, limit=a.limit, reranker=reranker_of(a.no_rerank))
        if a.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            for r in result["results"]:
                print(f"{r['path']}:{r['line_start']}-{r['line_end']}  [{r['date']}] {r['text'][:100]!r}")
            print(json.dumps(result["status"], ensure_ascii=False), file=sys.stderr)
        return 0
    result = evaluate(load(a.questions), index, reranker_of(a.no_rerank), exclude_after=a.exclude_after)
    if a.out:
        a.out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, ensure_ascii=False))
    return 0
