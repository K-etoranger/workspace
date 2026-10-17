# src

仕組み（コード）の置き場。1システム1repo。

この README は `src/workspace-index` が作る。手で直さない。

repo を使うなら、その repo の README.md を読む。

| repo | 何か | 定時処理（launchd は時刻、エージェントの定時処理は「エージェント」） |
|---|---|---|
| [`agents`](agents/README.md) | エージェントが読む共通ルール・skill・定時処理の本文・設定の原本を持ち、配置先へ写す。 | `distill-daily` エージェント<br>`distill-messages` エージェント<br>`distill-preferences` エージェント<br>`distill-projects` エージェント |
| [`jobs`](jobs/README.md) | 全部の repo の定時処理を Mac へ配置する。 | なし |
| [`memory-recall`](memory-recall/README.md) | data にある記憶の索引から、本人の発言や問いに関係する記憶（md の行）を引き、問題集で引き方の点を測る。 | `memory-recall.serve` 常駐 |
| [`memory-search`](memory-search/README.md) | SecondBrain と company/ の md を元の文のまま小さな塊に切り、意味の埋め込みと全文検索の索引を作って data に置く。 | `memory-search.index` 3時間ごと |
| [`taskizer`](taskizer/README.md) | 00_inbox に届いた連絡の新着を読み、対応が要る物だけを 40_tasks のタスクにする。自分が作ったタスクは、新着を根拠に直し・閉じる。 | `taskizer.task-checks-report` 08:00・12:00・17:00 |
| [`workspace-history`](workspace-history/README.md) | Workspace と SecondBrain の、人が書く物の変更を1時間ごとに git へ記録する。 | `workspace-history.snapshot` 1時間ごと |
| [`workspace-index`](workspace-index/README.md) | Workspace の地図になる README を自動で作り、置き場の決まりに合わない所を知らせる。 | `workspace-index.refresh` 1時間ごと |
