# agent-setup

全エージェントに共通の、共通ルール・hook・専用ブラウザの原本を持つ。

## 使い方

- 共通ルールは `rules/AGENTS.md` の1本。
- 配置は agents の README の使い方。配置先を直接直さない。
- `hooks/guard.py`: エージェントがシェル・ファイルの書き込みを使う直前に動く hook。一時置き場（`/tmp`・`/private/tmp`・`/var/folders`・`mktemp`・`$TMPDIR`・`tempfile`）を使う操作を止める。標準の Python だけで動き、壊れたときは何もせずに通す。
- `hooks/hooks.json`: この repo の hook の登録（形は agents の README の使い方）。
- `bin/chrome_beta.py`: エージェント専用の Chrome Beta（CDP 9290）を確かめ、止まっていれば起こす。`python3 bin/chrome_beta.py`（本人がログインするときも同じ）。

## data に書く場所
- data/agent-setup/browser_profiles
- data/agent-setup/state

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
- `./test.sh`（`tests/` の pytest）

## してはいけないこと
- 共通ルールを2本に分けない。特定のエージェントだけの物を置かない（`<エージェント名>-setup` の repo に置く）。
