# scheduled

エージェントの定時処理の本文を、1つの処理に `<名前>/SKILL.md` を1つずつ置く。

## 使い方

- 本文はエージェントに依らない形で書く。
- Claude: `src/agents/deploy.py --apply` が `~/.claude/scheduled-tasks/<名前>/SKILL.md` へ写す。時刻は Claude アプリの定時処理の設定が持つ。
- Codex: 定時処理は Codex アプリの中に登録するので、自動では写らない。同じ本文をそのまま Codex の定時処理に登録する。
- 蒸留の3本は distill-messages → distill-preferences → distill-daily の順に動かす。
- SecondBrain へは `sb` だけで書く。`--by` は `agents/<名前>`。
- 始めに `../bin/scheduled_runs_status.py --json` を1回流し、同じ処理が二重に動いていないかを確かめる。

## してはいけないこと

- 本文にエージェント固有の書き方をしない。
- SecondBrain のファイルを直接書かない。
- 蒸留の3本を順番を変えて動かさない。同じ処理を二重に動かさない。
