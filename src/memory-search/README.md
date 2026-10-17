# memory-search

SecondBrain と company/ の md を元の文のまま小さな塊に切り、意味の埋め込みと全文検索の索引を作って data に置く。

## 使い方

```sh
bin/memory-search build                      # 索引を作り直す（ふだんは定時処理が動かす）
bin/memory-search build --out <置き場>        # 別の置き場に作る（試すとき）
```

- 対象は SecondBrain の 00_inbox・10_daily・20_identity・30_projects・40_tasks・50_media・60_distilled と company/（`memory_search/workspace.py` の `INDEX_ROOTS`）。SecondBrain の 90_logs と直下の README・NOW、「.」で始まる置き場、node_modules などは入れない。
- 切り方（`memory_search/chunk.py`）:
  - 20_identity は箇条1行ずつ。
  - 会話（00_inbox/conversations）は発言1つずつ。最初の発言に定時処理の目印（`<scheduled-task`・`<automation_id>` など、`SCHEDULED_MARKS`）がある見出し、定時処理の会話の続き（見出しや日が分かれても、会話の id で見る）と検索の試験のために話題を並べた作業の会話（`WORK_SESSIONS`）のエージェントの返事、機械が入れた発言（作業の通知・引き継ぎの添付・コマンドの注記・hook の返事。`MACHINE_TURN_RE`）は外す。
  - 連絡（00_inbox/messages）は1通ずつ。続いた同じ相手の通は約1,000字までまとめる。
  - ほか（company/ を含む）は見出しの中の段落・箇条ごと。短い物は約600字までまとめる。
  - 30_projects と 40_tasks は、頭書きのうち中身のある欄（件名・状態・期限・出典・待ち など。仕組みの記録の欄 `MECHANICAL_KEYS` は除く）も1つの塊にする。
  - 1塊は約1,000字まで。長い段落は行の境目で切る。1行だけで長い行は100字重ねて字で切る。
  - 行は改行だけで数える。塊の行番号は、その塊の文が実際にある行を指す。
- 塊には、場所（path・行）・日付・話し手・今か archive か を持たせる。20_identity は今の本人だけを置く層なので、日付を付けない。埋め込む文と全文検索の語には、頭に「[日付] 層 > 文書名 > 見出し > 話し手」を付ける。
- 埋め込みはローカルの Ollama（`Nemotron-3-Embed-8B`、Q8_0・4,096次元）。50_media は全文検索だけで、埋め込まない。止まっていれば `start_ollama.mjs` が `models/ollama-fallback` のモデルで起こす。
- 埋め込みは文の sha256 で `embeddings.sqlite` に溜め、変わった塊だけを埋め込む。途中で止まっても続きから作れる。索引ができたら、使わなくなった埋め込みを消す。
- 埋め込みが揃わなければ、前の索引を残して失敗にする。結果は `state.json` に出る。
- 置く物:
  - `index.sqlite`: 塊・全文検索・ベクトル。
  - `manifest.json`: 使う側との約束。表の形・埋め込みのモデルと前置き（問いは `query: `）・全文検索の語の区切り方。
- 索引は md から作る捨ててよい派生物。正本は md。
- 部品の sqlite-vec（版は `requirements.txt` に固定）は repo の `.venv`（git に入れない）にある。`bin/memory-search` はどの Python で呼んでも `.venv` の Python で動き直す。作り直すときは repo で `/opt/homebrew/bin/python3 -m venv .venv && .venv/bin/pip install --no-deps -r requirements.txt`。

## data に書く場所
- data/memory-search/index

## data から読む場所
- なし

## SecondBrain に書く層
- なし

## SecondBrain から読む層
- 00_inbox・10_daily・20_identity・30_projects・40_tasks・50_media・60_distilled（ファイルを直接読む）

## 使うモデル
- models/ollama-fallback

## 定時処理
- memory-search.index: 索引を作り直す。

## 試験
```sh
.venv/bin/pip install pytest iniconfig pluggy packaging pygments   # 初回だけ
.venv/bin/python -m pytest -q tests
/opt/homebrew/bin/node --test tests/start_ollama.test.mjs
```

## してはいけないこと
- SecondBrain と company/ に書かない。読むだけ。
- 索引には company/ の中身も入る。
- 索引と `embeddings.sqlite` を Workspace の外や クラウド へ写さない。
- private・raw の本文をクラウドの埋め込み API へ送らない。
- 索引作りは同時に1つだけ動かす（2つ走ると SQLite が壊れる）。
- `manifest.json` の約束（表の形・モデル・前置き・語の区切り方）を変えたら `schema` を上げる。
- 普通の質問で索引を作り直したり、Ollama を再起動したりしない。
