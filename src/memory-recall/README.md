# memory-recall

data にある記憶の索引から、本人の発言や問いに関係する記憶（md の行）を引き、問題集で引き方の点を測る。

## 使い方

```sh
bin/memory-recall search "<発言・問い>" [--limit 8] [--no-rerank] [--json]
bin/memory-recall eval <問題集.json> [--no-rerank] [--exclude-after YYYY-MM-DD] [--out <結果.json>]
bin/memory-recall serve [--port 8767]    # 検索の窓口（ふだんは定時処理が常駐させる）
```

- 索引は `data/memory-search/index`（環境変数 `MEMORY_RECALL_INDEX` で別の置き場を読める）。`manifest.json` の `schema` と全文検索の語の区切り方（`bigram-v1`）が合わなければ、引かずに止まる。
- 引き方（`memory_recall/search.py`）:
  - 問いを manifest の前置き（`query: `）を付けてローカルの Ollama で埋め込み、意味の近い塊を50件。問いの埋め込みは、索引と同じモデルの軽い版（`QUERY_MODEL`、Q4_K_M）を使う。索引のモデルが同じモデルでなければ、引かずに止まる。
  - 問いを manifest の決まりで2文字ずつ区切り、全文検索で50件。
  - 2つの順位を RRF で混ぜ、上位30件を reranker（`memory_recall/rerank.py`、models の下の ruri-v3-reranker-310m を transformers で動かす）で読み比べて並べ直す。
  - 並べ直すとき、今を表す置き場（20_identity・進行中の案件とタスク）に少し点を足す（`CURRENT_BONUS`）。同じ話題の古い記録（過去の会話・連絡・終わったタスク）と今の記録が並んだとき、今の記録を上に出すため。
  - Ollama が止まっていれば、全文検索だけで引き、結果の `status` にそう書く。
- 結果は塊ごとに path・行・層・日付・話し手・今か archive か・本文。
- 窓口（`memory_recall/serve.py`）: `127.0.0.1:8767` だけで待ち受け、Host が `127.0.0.1:8767`・`localhost:8767` の問い合わせにだけ答え、reranker と問いの埋め込みのモデルを読み込んだままにする（Ollama にも手放さないよう頼む）。
  - `GET /health`: 動いているかと索引を作った時刻。
  - `POST /search`（`query`・`limit`）: 引いた結果。
  - `POST /hook`（`session_id`・`prompt`）: 会話に添える文。その会話で最初の発言なら上位10件、2回目からは前に添えていない上位3件（`FIRST`・`NEXT`）。1件の本文は300字まで。返事だけの発言（「承認します」「進めてください」「今どう？」など、`REPLY_WORDS` の言い方だけでできた発言）には添えず、その会話の最初の発言としても数えない。
  - 索引が作り直されたら（`manifest.json` が変わったら）、次の問い合わせで開き直す。
  - 問いや結果の本文はログに出さない。
- 採点（`memory_recall/evaluate.py`）: 問題集は1問ごとに問い・正解の場所（path と行）・古い記録の場所を持つ JSON。上位5件に正解の行を含む塊が入った割合（Recall@5）と MRR@10、古い記録が正解より上に来た問いを出す。`--exclude-after` は、その日以降の 00_inbox を採点から除く（問題集を作った会話そのものが当たるのを避ける）。
- 部品（sqlite-vec・torch・transformers。版は `requirements.txt` に固定）は repo の `.venv`（git に入れない）にある。`bin/memory-recall` はどの Python で呼んでも `.venv` の Python で動き直す。作り直すときは repo で `/opt/homebrew/bin/python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`。

## data に書く場所
- なし

## data から読む場所
- data/memory-search/index（書き手: memory-search）

## SecondBrain に書く層
- なし

## SecondBrain から読む層
- なし

## 使うモデル
- models/ruri-v3-reranker-310m
- models/ollama-fallback（問いを埋め込む Nemotron-3-Embed-8B の Q4_K_M。Ollama を通して使う）

## 定時処理
- memory-recall.serve: 検索の窓口を常駐させる。

## 試験
```sh
.venv/bin/pip install pytest   # 初回だけ
.venv/bin/python -m pytest -q tests
```

## してはいけないこと
- 索引を書き換えない。読むだけ。
- 窓口を `127.0.0.1` 以外で待ち受けさせない。
- 埋め込みと reranker は手元で動かす。問いや記録の本文を、クラウドの埋め込み・検索の API へ送らない。
- 確認用の問題集で引き方を調整しない（調整は開発用の問題集だけで行い、確認用は最後に1回だけ解く）。
