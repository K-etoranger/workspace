# work

新しい物を作り、既存の repo を直すための作業場。ここから何も稼働させない。

## 新しい物を作る
- `work/<案件>/<task-exec>/` で始める。案件が無ければ `work/<task-exec>/`。
- `<task-exec>` はその作業のタスクの ID（日付から始まる）。

## 既存の repo を直す
- `src/<repo>` と `sb` の本番の branch は稼働中なので、直接編集しない。
- worktree を切って、その中で直す:
  ```bash
  git -C <本番の repo> worktree add ~/Workspace/work/worktrees/<repo>/<task-exec> -b <task-exec>
  ```
  本番の repo の場所は `Workspace/README.md` からたどる。
- commit のメッセージの末尾に `Task-Exec: <task-exec>` と `Agent: <エージェント名（小文字）>` を付ける。
- repo の試験を worktree の中で流して通す。
- 通ったら本番へは入れずに止め、差分・変えた文書の全文・試験の結果・本番で変わること（定時処理・配置・data の移動）を本人に見せ、タスクを needs_review にする。
- 本人の承認を得てから本番の branch へ取り込み（例: `git -C <本番の repo> merge --ff-only <task-exec>`）、配置と data の移動をして、確かめる。
- Workspace 本体（config/ など）は worktree を切らない。直した案を `work/<task-exec>/` に作り、差分を本人に見せて承認を得てから、本体を直して commit する。commit には上と同じく `Task-Exec` と `Agent` を付ける。

## 本番へ移す
- 新しい物も既存の repo の直しも、本人の承認を得てから、置き場ごとに移す:
  - コード → `src/<repo>`
  - データ → `data/`
  - md → その案件の資料として SecondBrain へ（やり方は sb の README）。下書き・途中の記録は work に残す
  - 会社の具体値 → `company/`
- repo や置き場を増やした・減らした作業の最後に、一覧の README を1回作り直す（やり方は workspace-index の README の「使い方」）。

## してはいけないこと
- `work/` の中から定時処理・常駐を動かさない。稼働させる物は本番へ移してから動かす。
- `work/` の中の物を本番の repo・定時処理から参照しない。

## 片付け
- `work/` は古い物が残っていてよい唯一の場所。
- 取り込み済みの worktree は、本人に確かめてから `git -C <本番の repo> worktree remove <パス>` で外す。
