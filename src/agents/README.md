# agents

全部の repo が持つエージェント向けの原本（共通ルール・設定・hook・skill・定時処理の本文）を集め、エージェントが読む配置先へ写す。

## 使い方

```sh
python3 deploy.py            # 確かめるだけ。差分があれば終了コード 1
python3 deploy.py --apply    # 写す。その後に引数なしで流し、差分0を確かめる
python3 deploy.py --archive  # 原本の無くなった skill・定時処理を ~/Documents/_archive_<日付>/agents/ へ移す
./test.sh                    # 試験
```

- 集める原本と配置先:

| 原本（`src/<repo>/`） | 配置先 |
|---|---|
| `rules/AGENTS.md`（全 repo で1つ） | `~/.codex/AGENTS.md` |
| `rules/claude-home.md`（全 repo で1つ） | `~/.claude/CLAUDE.md` |
| `settings/claude.json`（全 repo で1つ） | `~/.claude/settings.json` |
| `hooks/hooks.json` | `~/.claude/settings.json` の hooks（全 repo の分を合わせる） |
| `skills/<skill>/` | `~/.claude/skills/<skill>/`・`~/.codex/skills/<skill>/` |
| `scheduled/<名前>/SKILL.md` | `~/.claude/scheduled-tasks/<名前>/SKILL.md` |

- 同じ名前の skill・定時処理が2つの repo にあれば、何もしないで止まる。
- `hooks/hooks.json` の形: 場面（`PreToolUse` など）ごとに `matcher`（あれば）・`command`（引数の並び。`/` で始まらない要素はその repo からのパス）・`timeout`（あれば）。
- settings の編集禁止の行: 原本の行に、Workspace の中で uchg の印が付いたファイル（`config/`・`sb/`・`src/` の中）を配置のたびに探して足す。ファイルを固める・外すのは本人の許可で `chflags uchg`・`chflags nouchg` をするだけで、一覧を手で直さない。
- settings は Claude Code 自身も書き換える（モデル・テーマなど）。差分が出たら、先に配置先の変更を原本へ取り込んでから `--apply` する。
- 原本の skill から消えたファイルは `stale` として出し、`--apply` で消す。
- 配った skill・定時処理の名前を `data/agents/state/deployed.json` に残す。前に配ったのに原本の無い物は `orphan` として出す（`--apply` では移さない）。
- 定時処理の時刻は本文の頭の `schedule:`（cron の形）が正本。Claude アプリの定時処理の登録を読んで比べ、違う・無い・登録だけある物を `schedule` として出す。登録はアプリの画面で手で直す。
- Codex の定時処理は Codex アプリの中に登録するので、自動では写らない。同じ本文をそのまま登録する。

## data に書く場所
- data/agents/state

## data から読む場所
- なし

## SecondBrain に書く層
- なし

## SecondBrain から読む層
- なし

## 使うモデル
- なし

## 定時処理
- なし

## 試験
- `./test.sh`（`tests/` の pytest）。配置先は `AGENTS_DEPLOY_HOME` で一時フォルダへ向ける。

## してはいけないこと
- 配置先（`~/.claude`・`~/.codex`）を直接直さない。原本を直して `--apply`、引数なしで差分0を確かめる。
- この repo に中身（ルール・設定・hook・skill・定時処理の本文）を置かない。
- `--archive` は、確認だけの `orphan` の行を本人に見せてから流す。
