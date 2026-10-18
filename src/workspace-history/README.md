# workspace-history

Workspace と SecondBrain の、人が書く物の変更を1時間ごとに git へ記録する。

## 使い方

```sh
./workspace-history                                       # 変更があれば commit する
./workspace-history --agent <エージェント名（小文字）> --task-exec <ID> "<メッセージ>"   # 作業の区切りで手で記録する
```

- 記録する所: `Workspace/.git`（対象は `Workspace/.gitignore` が決める。README・config など）と `SecondBrain/.git`（対象は `SecondBrain/.gitignore` が決める。md）。
- commit には、変わったファイルの一覧と `Agent:`（と `Task-Exec:`）を付ける。
- 変更が無ければ何もしない。別の commit の途中（`index.lock` がある）なら次の回に回す。`.git` が無い所は飛ばす。
- 記録する所は `WS_HISTORY_REPOS`（改行か空白で区切る）で差し替えられる（試験用）。

## data に書く場所
- なし

## data から読む場所
- なし

## SecondBrain に書く層
- なし

## SecondBrain から読む層
- SecondBrain 全体（`git add -A`。対象は `SecondBrain/.gitignore` が決める）

## 使うモデル
- なし

## 定時処理
- workspace-history.snapshot: Workspace と SecondBrain の変更を git へ commit する。

## 試験
```sh
python3 -m pytest -q tests
```
一時フォルダの git だけを使う。

## してはいけないこと
- 記録する所のファイルを書き換えない。するのは `git add` と `git commit` だけ。
- 別の commit の途中（`index.lock` がある）に割り込まない。
- 記録を消したり書き換えたりする git 操作（reset・rebase・push --force など）をこの道具に入れない。
