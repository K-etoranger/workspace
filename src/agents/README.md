# agents

エージェントが読む共通ルール・skill・定時処理の本文・設定の原本を持ち、配置先へ写す。

## 使い方

```sh
python3 deploy.py            # 確かめるだけ。差分があれば終了コード 1
python3 deploy.py --apply    # 配置する。その後に引数なしで流し、差分0を確かめる
./test.sh                    # 試験
```

- `bin/chrome_beta.py`: エージェント専用の Chrome Beta（CDP 9290）を確かめ、止まっていれば起こす。`python3 bin/chrome_beta.py`（本人がログインするときも同じ）。
- プロファイルは `data/agents/browser_profiles/chrome_beta`、状態は `data/agents/state/chrome_beta.json`。
- 原本と配置先:

| 原本 | 配置先 |
|---|---|
| `rules/AGENTS.md`（共通ルール） | `~/.codex/AGENTS.md` |
| `rules/claude-home.md` | `~/.claude/CLAUDE.md`（`rules/AGENTS.md` を読み込む） |
| `settings/claude.json` | `~/.claude/settings.json` |
| `skills/<skill>/` | `~/.claude/skills/<skill>/`・`~/.codex/skills/<skill>/` |
| `scheduled/<名前>/SKILL.md` と、ほかの repo の `scheduled/<名前>/SKILL.md` | `~/.claude/scheduled-tasks/<名前>/SKILL.md`（同じ名前が2つあれば止まる） |

- `settings/claude.json` の編集禁止の行: Workspace の外の物だけを原本に書く。Workspace の中は、`deploy.py` が配置のたびに uchg の印が付いたファイル（`config/`・`sb/`・`src/` の中）を探して足す。ファイルを固める・外すのは本人の許可で `chflags uchg`・`chflags nouchg` をするだけで、一覧を手で直さない。
- `settings/claude.json` は Claude Code 自身も書き換える（モデル・テーマなど）。差分が出たら、先に配置先の変更を原本へ取り込んでから `--apply` する。
- `deploy.py` は、原本の skill から消えたファイルと、やめた skill・定時処理（`RETIRED_SKILLS`・`RETIRED_SCHEDULED`）が配置先に残っていれば差分として出し、`--apply` で消す。原本に無い skill・定時処理には触れない。
- `hooks/memory_recall.py`: 本人が発言するたびに動く hook（`settings/claude.json` の `UserPromptSubmit` に登録）。発言と会話の ID を手元の記憶の窓口（`127.0.0.1:8767`）へ送り、返ってきた記憶の候補を会話に添える。標準の Python だけで動き、窓口が止まっている・遅いときは何も添えずに終わる。
- `hooks/guard.py`: エージェントがシェル・ファイルの書き込みを使う直前に動く hook（`settings/claude.json` の `PreToolUse` に登録）。一時置き場（`/tmp`・`/private/tmp`・`/var/folders`・`mktemp`・`$TMPDIR`・`tempfile`）を使う操作を止める。標準の Python だけで動き、壊れたときは何もせずに通す。
- `bin/scheduled_runs_status.py`: エージェントの定時処理の状態を1画面に出す（読むだけ）。定時処理の本文が始めに流す。
- 定時処理の本文の登録は `scheduled/README.md` を読む。
- 共通ルールは `rules/AGENTS.md` の1本。`rules/claude-home.md` はそれを Claude に読み込ませるだけ。
- skill（中身は各 `skills/<skill>/SKILL.md`）:
  - write-workspace-readme: Workspace の README を作る・直す
  - manage-taro-tasks: タスク・予定の扱い方

## data に書く場所

- data/agents/browser_profiles
- data/agents/state

## data から読む場所

- なし

## SecondBrain に書く層

- 60_distilled（sb distill write --by agents/distill-messages）
- 20_identity（sb identity set --by agents/distill-preferences）
- 10_daily（sb daily write --by agents/distill-daily）
- 30_projects/active（sb project status・log・new・close・meta --by agents/distill-projects）
- 40_tasks/active（案件蒸留の質問タスクだけ。sb task new・note・done・update --project --by agents/distill-projects）
- 90_logs/schedule（sb log schedule --by agents/<定時処理の名前>）
- 90_logs/check（sb check --by agents/distill-daily）

## SecondBrain から読む層

- 00_inbox（sb inbox show）
- 10_daily（sb daily show）
- 20_identity（sb identity show）
- 30_projects/active（sb project list・sb project show。案件メモを直接読んでもよい）
- 40_tasks（sb task list・sb task show）
- 50_media（sb media show）
- 60_distilled（sb distill show）
- 90_logs/schedule・90_logs/handoff.md（前の実行の記録を直接読む）

## 使うモデル

- なし

## 定時処理

- distill-messages: 連絡と会話の本人の発言から候補を蒸留して 60_distilled へ書く。
- distill-preferences: 日々の材料から関心・長い好みを蒸留して 20_identity を直す。
- distill-daily: その日の材料から本人の関心・行動・気分・出来事を 10_daily へまとめる。
- distill-projects: 前回からの材料で active の案件メモを今の姿に書き直し、分からないことを本人への質問タスクにまとめる。

## 試験

- `./test.sh`（`tests/` の pytest）。配置先は `AGENTS_DEPLOY_HOME` で一時フォルダへ向ける。

## してはいけないこと

- 配置先（`~/.claude`・`~/.codex`）を直接直さない。原本を直して `deploy.py --apply`、引数なしで差分0を確かめる。
- `scheduled/` の本文から SecondBrain のファイルを直接書かない。書くのは `sb` だけ。
