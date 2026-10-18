# sb

SecondBrain を読み書きする唯一の入口（CLI）。

## 使い方
- 入口は絶対パス `/Users/taro/Workspace/sb/bin/sb`。形は `sb <対象> <動作> [オプション]`。
- SecondBrain に書くのは sb だけ。エージェントと定時処理はファイルを直接書かない。本人は Obsidian で直接書いてよい（崩れは `sb check` が 90_logs/check に出す）。
- 他の repo は sb のコマンドだけを使い、sb の中のファイル・関数を直接使わない。
- 書き込みは必ず `--by <書いた物>` を付ける。値の形は下の「`--by` の値」。頭書きの `書いた物` は、そのファイルを最後に書いた者を表す（書くたびに置き換わる）。
- コマンドの一覧・書式・終了コードは、この README の後ろの節にある。
- Python 3.9 以上の標準ライブラリだけで動く。
- sb 自身の作業の状態（書き込みのロック・取り込んだ順番・読み手ごとの読み進め位置）を `data/sb` に置く。

## data に書く場所
- data/sb

## data から読む場所
- なし

## SecondBrain に書く層
- 00_inbox（sb inbox add）
- 10_daily（sb daily write・sb identity set）
- 20_identity（sb identity set）
- 30_projects（sb project …）
- 40_tasks（sb task …・sb views refresh --by sb/views-refresh）
- 50_media（sb media add・sb media current）
- 60_distilled（sb distill write）
- 90_logs（sb log …・sb check --by sb/check）
- README.md・NOW.md（sb views refresh --by sb/views-refresh）

## SecondBrain から読む層
- 全層（sb … show・sb … list）

## 使うモデル
- なし

## 定時処理
- sb.views-refresh: NOW.md・40_tasks/タスク.base・README.md を作り直す。40_tasks/active が変わったときも動く。
- sb.check: 全ファイルの形を調べ、90_logs/check に書く。
- sb.tidy: 日時を過ぎた予定を archive へ移す。

sb が持つ定時処理は、自分の手入れのこの3本だけ。ほかの定時処理は各 repo が持ち、sb を呼ぶ。

## 試験
```sh
python3 -m pytest -q          # repo の直下から
```

## してはいけないこと
- sb/launchd/ に手入れの3本以外の定時処理を足さない。
- sb から repo・モデル・他の data を参照しない。sb は呼ばれて SecondBrain を読み書きするだけ。
- 他の repo から sb の中のファイル・関数を import しない。

---

## `--by` の値

| 書く物 | 値 | 例 |
|---|---|---|
| repo の処理 | `<repo名>/<処理>` | `sb/tidy` |
| 人・エージェントが直接書く | `本人`、またはエージェントの名前（小文字。`/` を含まない） | `claude` |

## 置き場の決め方（環境変数）

| 関数（`sb/paths.py`） | 既定 | 差し替え |
|---|---|---|
| `workspace_root()` | `/Users/taro/Workspace` | `SB_WORKSPACE` |
| `vault_root()` | workspace/`SecondBrain` | `SB_VAULT` |
| `data_root()` | workspace/`data` | `SB_DATA` |
| `config_root()` | workspace/`config` | `SB_CONFIG` |

- sb 自身のデータは `data/sb/`: `locks/`・`checkpoints/<読み手>.json`・`inbox/<ソース>.jsonl`（受け付けた順番）。
- `SB_NOW`（ISO 日時）は試験用に今の時刻を固定する。`SB_LOCK_WAIT`（秒、既定 3）はロック待ちの長さ。

## 共通の決まり

- `--dry-run`: 書かずに、書く予定の内容と検証の結果だけを出す。
- `--json`: 結果を JSON で出す（`{"ok": true, ...}`。誤りは `{"ok": false, "code": n, "error": "..."}`）。
- 本文: `--text "<本文>"`・`--stdin`・`--file <path>`（Workspace の中だけ）。
- 論理日（Asia/Tokyo 05:00 区切り。09-30 03:00 は 09-29）を決めるのは sb だけ。他の repo は計算せず、書くときは時刻を渡し、日が要るときは `sb day` に尋ねる。
- `inbox add`・`media add` は `--date` を省くと、各件の `時刻`（タイムゾーン付きの日時）から日を決めて日ごとのファイルへ振り分ける。`時刻` が `HH:MM` だけの件・時刻の無い行は `--at <取得した日時>` を付ける。`--date` は元のサービスが日付しか返さないデータと手作業にだけ使う（日時の件の日と食い違うと断る）。
- それ以外のコマンドは、`--date` を省くと今日の論理日。

```sh
sb day --json                                  # 今の論理日と、その始まり・終わり
sb day --at 2026-09-30T04:59+09:00 --json      # その日時の論理日（2026-09-29）
sb day --date 2026-09-29 --json                # その論理日の始まりと終わり
printf '2026-09-30T04:59+09:00\n' | sb day --stdin --json   # まとめて日を尋ねる
```
- 書き込みは「ロック → 一時ファイル → 検証 → 置き換え」。途中で止まっても元のファイルは壊れない（書きかけは `.名前.sb-tmp-…` で、読まれない）。
- 書く前に必ず調べる: 秘密の形の文字列（トークン・パスワードの値）が無いこと、会社機密ゲート（`config/company_confidential.json`）が禁じる置き場でないこと、頭書きと見出しがそろうこと（頭書きは YAML として読める形で書く。必要な値だけ "…" で囲む）、その層に書いてよいコマンドであること、archive でないこと。
- 会社の言葉を含む行は SecondBrain に書ける（会社機密ゲートが禁じる置き場には書かない）。

### 終了コード

| コード | 意味 |
|---|---|
| 0 | 成功 |
| 1 | 形の誤り（検証で断った・状態の規則で断った・`sb check` で崩れが残った） |
| 2 | 他の書き込み中（ロック） |
| 3 | 対象が無い（タスク・案件・ファイル） |
| 4 | 書き込みを断った（archive・読み取り専用・秘密・会社機密・Workspace の外・その層に書けない） |
| 5 | 内部の誤り（読み込めない拡張を含む） |

## コマンド

### inbox（00_inbox）

```sh
echo '<JSON の1行（id・時刻・本文 など、ソースの列）>' | sb inbox add --source <ソース> --stdin --by <書いた物>
sb inbox list --source <ソース> --since <読み手>   # 読み手の位置より後（JSON 行）
sb inbox ack --reader <読み手> --until <id>        # 位置を進める（戻さない）
sb inbox show [--source <ソース>] [--date D]       # --source を省くと、その日の全ソース
```
- 件の形は2つ。連絡（`messages`）は `id`・`時刻`・`相手`・`場所`・`向き`（self か other）・`本文`・`元データ`。会話（`conversations`）は `id`・`時刻`・`会話ID`・`本人`・`返答`。形に無い項目は断る。
- 置き場は、そのソースのフォルダがあればそこ（`00_inbox/messages/<ソース>` か `00_inbox/conversations/<ソース>`）。無ければ件の形で決める（`本人`・`返答`・`会話ID` のどれかがあれば会話）。
- 同じ `id` は二度書かない。
- 秘密の形に当たった値の部分だけを「〈伏せた〉」にして全部書く。伏せた件は結果の `masked`（id と型の名前。値は出さない）に出る。
- `show` で `--source` を省いたときの JSON: `{"date": "D", "sources": {"<ソース>": {"dir": "messages|conversations", "path": "…", "items": [件…]}}}`。その日の記録が無いソースは含めない（無ければ `{}`）。

### media（50_media）

```sh
echo '<JSON の1行>' | sb media add --kind <種類> --stdin --by <書いた物>              # その日の記録
echo '<JSON の1行>' | sb media current --kind <種類> --total <総数> --stdin --by <書いた物>   # 今の一覧（current.md を置き換え）
sb media show [--kind <種類>] [--date D]   # --kind を省くと全種類
```
- 列は `layers.toml` の種類ごとの形に従う。形の無い種類は、その日のファイルがあればその表の列、無ければ受け取った JSON のキー（出てきた順）を列にする。列に無い項目は断る。同じ行は二度書かない。
- 形のある種類は、`daily`・`has_current` が true のときだけ日別・current を持つ。形の無い種類は両方を持つ。1件1ファイルの種類は無い（日別の表の1行になる）。
- `時刻` の列は、日別の表では `HH:MM`、current では日付つきの `YYYY-MM-DD HH:MM`（ISO の日時で渡したとき。`HH:MM`・`YYYY-MM-DD` だけの値はそのまま）。
- `show --kind K`: `--date` があればその日。省くと current を持つ種類は current.md、持たない種類は今日の論理日。
- `show` で `--kind` を省いたときの JSON: `{"date": "D", "kinds": {"<種類>": {"path": "…", "text": "…"}}}`。`--date` も省くと `"date": null` で各種類の current.md。ファイルの無い種類は含めない。
- `media add` も秘密の値だけを「〈伏せた〉」にして書き、`masked` に出す。

### task（40_tasks）

```sh
sb task new --title "<件名>" --owner <担当> [--due D] [--type 予定 --start "<日時>" --end "<日時>"] [--repeat <繰り返し>] [--project <案件>] [--estimate "<見積>"] [--text "<本文>"] [--id <ID>] --by <書いた物>
sb task update <ID> [--title] [--due] [--start] [--end] [--priority 高|中|低] [--estimate] [--project] [--owner] [--repeat] --by <書いた物>
sb task note <ID> --text "…" --by <書いた物>       # 「経緯」へ日時つきで1行
sb task start <ID> --by <書いた物>                 # in_progress
sb task wait <ID> --for "<待つ物>" --recheck D --by <書いた物>
sb task review <ID> --text "<確かめてほしいこと>" --by <書いた物>
sb task done <ID> [--text "…"] --by <書いた物>     # archive へ。繰り返しなら次の回を作る
sb task cancel <ID> --reason "…" --by <書いた物>
sb task reopen <ID> --by <書いた物>                # open に戻す（archive の物は active へ戻す）
sb task show <ID>
sb task list [--state] [--owner] [--due-before D] [--project] [--type] [--all]
sb task tidy [--before D] --by sb/tidy             # 日時を過ぎた予定を archive へ。繰り返しなら今日以降の最初の回を作る
```
- ID は `YYYYMMDD-英小文字・数字・ハイフン`。省くと論理日と件名から作る。重なれば `-2`…。
- 期限を日付だけで渡すと `23:59` を付ける（比べるときは論理日の終わり＝翌日 05:00）。
- `--project` は active の案件だけ（無ければ 3）。archive のタスクは変えられない（4。`reopen` で戻す）。
- 繰り返し `毎日`・`毎週<曜日>`・`毎月<N>日`: done・cancel で次の回を active に作る。次の回がもうあれば作らない。
- 頭書きの `作った物` は `task new` の `--by`。後から変えるコマンドは無い（繰り返しの次の回は前の回の値を引き継ぐ）。`書いた物` は書くたびに置き換わるので、誰が作ったタスクかはこちらで見る。

### project（30_projects）

```sh
sb project new "<案件>" --purpose "…" [--repo <repo>] [--data <data の置き場>] --by <書いた物>
echo "…" | sb project status "<案件>" [--section 今の状態|決まっていること|目的|経緯] --stdin --by <書いた物>   # その節を置き換え（既定は「今の状態」）
sb project meta "<案件>" [--start D] [--repo <repo> …] [--data <data の置き場> …] --by <書いた物>   # 頭書きの 開始・関連repo・関連data を置き換え（渡した物だけ）
sb project log "<案件>" --text "…" --by <書いた物>              # 「経緯」へ日付つきで1行
sb project attach "<案件>" --file <Workspace の中の md> [--name <名前>] --by <書いた物>
sb project close "<案件>" --result 完了|中止 --text "…" --by <書いた物>   # 紐づく active タスクがあれば断る
sb project reopen "<案件>" --by <書いた物>
sb project show "<案件>"     # メモと、紐づくタスク
sb project list [--all]      # --all は archive も
```
- archive の案件への書き込みは断る（4）。案件名は日本語可。`/` と先頭の `.` は不可。

### identity（20_identity）・daily（10_daily）・distill（60_distilled）

```sh
echo "…" | sb identity set <ファイル> --section <節> [--why "<理由>"] --stdin --by <書いた物>
sb identity show [<ファイル>]                      # 省くと全ファイル
echo "…" | sb daily write [--date D] --section <節> --stdin --by <書いた物>
sb daily show [--date D]
echo "## <節>\n…" | sb distill write --source <ソース> [--date D] --read-count <読んだ数> --adopted <採った数> --stdin --by <書いた物>
sb distill show [--source <ソース>] [--date D]      # --source を省くと、その日の全ソース
```
- `identity show` でファイルを省いたときの JSON: `{"files": {"<ファイル>": {"path": "…", "text": "…"}}}`（20_identity の下の全 md）。
- `distill show` で `--source` を省いたときの JSON: `{"date": "D", "sources": {"<ソース>": {"path": "…", "text": "…"}}}`。その日の記録が無いソースは含めない。
- 名前を省いた show は、`--json` が無くても JSON で出す。
- `identity set` は節を置き換え、書き換える前と後の節の中身を行で比べて、同じ論理日の 10_daily「本人像の変化」へ差を書く。
  - 行は前後の空白を除き、空行は無視し、行頭の箇条書き `- ` は外して比べる（表示でも外す）。
  - 前に無く後にある行は `- <ファイル>: 足した「<行>」`、前にあり後に無い行は `- <ファイル>: 消した「<行>」`。消した→足したの順で、それぞれ元の順。1行の書き換えは、消した1行と足した1行になる。節が「今の状態」以外なら `<ファイル>（<節>）` と書く。
  - `--why` は省ける。渡されて差があるときだけ、差の行の後に `- <ファイル>: 理由: <why>` を1行足す。
  - 中身が同じときは、20_identity も 10_daily も書かない。並べ替えだけなど、足した・消した行が無い書き直しは、20_identity だけを書き、10_daily には書かない。
- `daily write`・`distill write` は節ごとに置き換える。節の名前は各層の形（`templates/`）に従い、形に無い節は断る。

### log（90_logs）

```sh
sb log audit --name <名前> [--date D] --text "…" --by <書いた物>    # 同じ日付は上書きしない
sb log schedule --task <処理> --text "…" --by <書いた物>  # ## YYYY-MM-DD HH:MM で追記
sb log handoff --text "何を / どこで / どう確かめたか / task:<ID>" --by <エージェント名>
```
- `log handoff` は handoff の記録の末尾に `- YYYY-MM-DD HH:MM [<--by>] <本文>` を1行足す。前の行は変えない。エージェントは `--by` に自分の名前（小文字。例 `claude`）を渡す。
- 本文は1行で、何を決めた・変えたか / どこで（repo・ファイル） / どう確かめたか / `task:<ID>` を ` / ` で区切る。
- 他の書き込み中は終了コード 2 なので、待ってから同じコマンドをやり直す。

### 画面・検査・版

```sh
sb views refresh --by sb/views-refresh   # NOW.md（7節）・40_tasks/タスク.base・README.md。タスクのファイルは読むだけ
sb check [--fix] [--date D] --by sb/check   # 全ファイルの形 → 90_logs/check/<D>.md。--fix は頭書きの補完と、頭書きの書き方の直しだけ（中身は変えない）
sb version
```
## 層の中身と書式

- `layers.toml` が決めるのは、層（00〜90）と、層ごとのファイルの形（`templates/<種類>.md`・50_media の種類ごとの表の列）だけ。層の中のファイル名（20_identity のファイル・50_media の種類・60_distilled と 00_inbox のソース）は決めない。`--source`・`--kind`・ファイル名には、英小文字・数字・`_`・`-`・`/` の名前なら何でも渡せ、無ければ作る。新しく作るファイルの題名はその名前。
- `sb check` が「置き場所が決まりにない」と言うのは、層の外と、層の中でも形に合わない所（例: `60_distilled/<ソース>/` の日付でない md、current を持たない種類の current.md）だけ。
- 新しい md を足すのに sb を直す必要は無い。新しい「形」の文書を足すときだけ、`templates/<種類>.md` を1つ置く。
- 層の一覧は `SecondBrain/README.md`（`sb views refresh` が作る）。

## 互換性の約束（v1）

1. コマンド名・オプション名・意味を変える・消すのは、本人が決めたときだけ。
2. 足すのは自由（新しいコマンド・オプション・頭書きの項目）。
3. ファイルの形を変えるときは頭書きの `形式:` を上げる。sb は古い形式も読める。
4. 出力の JSON の項目は消さない（足すのは可）。
5. 呼ぶ側は sb の中のファイル・関数を直接使わず、コマンドだけを使う。
