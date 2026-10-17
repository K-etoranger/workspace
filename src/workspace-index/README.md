# workspace-index

Workspace の地図になる README を自動で作り、置き場の決まりに合わない所を知らせる。

## 使い方

```sh
python3 workspace_index.py refresh              # 一覧になる README を作る。中身が変わらなければ書かない
python3 workspace_index.py refresh --out <DIR>  # 同じ物を <DIR> の下に書く（試し）
python3 workspace_index.py check                # 作らずに、警告だけを出す。警告があれば終了コード 1
python3 bin/check_workspace_paths.py [--list]   # Workspace の外を指すパスが、許した場所の外に無いかを数える
python3 bin/check_repo_independence.py          # repo が他の repo（src/<別の repo>）を名指ししていないかを調べる
```

- 作る README: `Workspace/README.md`・`src/README.md`・`data/README.md`・`models/README.md`・`logs/README.md`。
- 材料: 各 repo（`src/*` と `sb`）の README の冒頭1行と欄、各 repo の `launchd/*.plist` とコード。
  - `src/README.md`: repo の名前・冒頭1行・定時処理の名前と時刻（plist から出す）
  - `data/README.md`: フォルダごとの書き手・読み手（README の「data に書く場所」「data から読む場所」から出す）
  - `models/README.md`: モデルごとの使う repo（README の「使うモデル」から出す）
  - `logs/README.md`: ログのファイルと書く定時処理（plist から出す）
- 警告: README が無い、冒頭1行が無い、repo の README に決まった欄が無い・空、data のフォルダの書き手が0か2つ以上、README に書いた data の場所やモデルが無い、読めない plist、コードが他の repo を名指ししている（`bin/check_repo_independence.py` と同じ検査）、コードが README で申告していない data のフォルダ（`data/<フォルダ>`）に触れている。
- 警告の中身が前の回と変わったときだけ、SecondBrain の定時処理の記録に書く。警告が1件以上なら、その一覧を本文にしたタスクを1件作る（担当は本人+エージェント、期限はその日）。警告が0件に戻ってもタスクは閉じない。
- repo・data のフォルダ・README の申告は、走るたびに探し直す。
- repo や置き場を増やした作業の最後にも、`refresh` を手で1回流す。
- `bin/check_workspace_paths.py`: 走る先は `src`・`sb`・`SecondBrain/README.md`・`config`・`~/.claude` と `~/.codex` の skill・指示・定時処理・設定。許す場所は `config/external_paths.json`。違反が0件なら終了コード 0。
- `bin/check_repo_independence.py`: repo（`src/*` と `sb`）が関わってよいのは sb のコマンド・data・models・config・外の場所だけ。他の repo の名指しを1行ずつ出し、終了コード 1。試験と md は見ない。

## data に書く場所
- data/workspace-index

## data から読む場所
- なし

## SecondBrain に書く層
- 90_logs/schedule（sb log schedule --task workspace-index --by workspace-index/refresh）
- 40_tasks（sb task new --by workspace-index/refresh）

## SecondBrain から読む層
- なし

## 使うモデル
- なし

## 定時処理
- workspace-index.refresh: 一覧になる README を作り直し、警告が変わったら記録に書き、警告があればタスクにする。

## 試験
```sh
python3 -m pytest -q tests
```
一時フォルダの Workspace だけを使う。

## してはいけないこと
- 作った README（Workspace・src・data・models・logs）を手で直さない。次に作るときに上書きされる。直すのは材料（各 repo の README と plist）か、このコード。
- repo の中の README（`src/<repo>/README.md` とその下）を作ったり書き換えたりしない。
- `company/` の README の文を一覧へ写さない。
