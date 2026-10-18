# claude-setup

Claude だけが使う入口・設定の原本を持つ。

## 使い方

- `rules/claude-home.md`: Claude に共通ルールを読み込ませる入口。共通ルールの本文は持たない。
- `settings/claude.json`: Claude Code の設定の土台。hook は書かない。編集禁止の行には Workspace の外の物だけを書く。
- 配置と、配置先との差分の扱いは agents の README の使い方。配置先を直接直さない。

## data に書く場所
- なし

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
- 自動の試験はない。

## してはいけないこと
- `rules/claude-home.md` に規則を書かない。
