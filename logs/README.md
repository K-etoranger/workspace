# logs

定時処理のログの置き場。

この README は `src/workspace-index` が作る。手で直さない。

ログの置き場は各 repo の `launchd/*.plist` が決める。

| ログ | 書く定時処理 | repo |
|---|---|---|
| `memory-recall.serve.err.log`・`memory-recall.serve.log` | `com.taro.memory-recall.serve` | `memory-recall` |
| `memory-search.index.err.log`・`memory-search.index.log` | `com.taro.memory-search.index` | `memory-search` |
| `sb.check.err.log`・`sb.check.log` | `com.taro.sb.check` | `sb` |
| `sb.tidy.err.log`・`sb.tidy.log` | `com.taro.sb.tidy` | `sb` |
| `sb.views-refresh.err.log`・`sb.views-refresh.log` | `com.taro.sb.views-refresh` | `sb` |
| `taskizer.task-checks-report.err.log`・`taskizer.task-checks-report.log` | `com.taro.taskizer.task-checks-report` | `taskizer` |
| `workspace-history.snapshot.err.log`・`workspace-history.snapshot.log` | `com.taro.workspace-history.snapshot` | `workspace-history` |
| `workspace-index.refresh.err.log`・`workspace-index.refresh.log` | `com.taro.workspace-index.refresh` | `workspace-index` |
