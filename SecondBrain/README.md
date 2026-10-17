---
形式: 1
種類: view
画面: README
更新: 2026-10-15T21:00+09:00
書いた物: sb/views-refresh
---
# SecondBrain

本人の記憶を md だけで置く場所。層ごとの書き方と sb のコマンドは `sb/README.md` を見る。

この README は `sb views refresh` が `sb/layers.toml` から作る。手で直さない。書き込みは sb だけ（本人は Obsidian で直接書いてよい）。

## 層ごとの決まり
| 層 | 何を置くか | 単位 |
|---|---|---|
| 00_inbox/messages | 届いた連絡の本文（秘密の値は伏せ字。会社の言葉は残す） | ソース×論理日 |
| 00_inbox/conversations | エージェントとの本人可視の会話 | エージェント×論理日 |
| 10_daily | その日の要約と出来事、本人像の変化（20_identity で足した行・消した行） | 論理日 |
| 20_identity | 今の本人（最新だけ） | ファイル（名前は自由） |
| 30_projects | 案件 | 案件 |
| 40_tasks | タスクと予定・進捗 | タスク |
| 50_media | 見た・聴いた・いいねした履歴 | 種類×論理日（＋現在値） |
| 60_distilled | ソースごとの蒸留 | ソース×論理日 |
| 90_logs | 仕組みの記録 | 種類ごと |
| README・NOW | 地図・今やること | 1ファイル |

## ファイルの置き場
| パス | 種類 | 書くコマンド |  |
|---|---|---|---|
| `00_inbox/messages/{inbox_messages}/{date}.md` | inbox | sb inbox |  |
| `00_inbox/conversations/{inbox_conversations}/{date}.md` | inbox | sb inbox |  |
| `10_daily/{year}/{date}.md` | daily | sb daily / sb identity |  |
| `20_identity/{identity}.md` | identity | sb identity |  |
| `30_projects/active/{project}/メモ.md` | project | sb project |  |
| `30_projects/active/{project}/資料/{name}.md` | project | sb project |  |
| `30_projects/archive/{project}/メモ.md` | project | sb project | 読み取り専用 |
| `30_projects/archive/{project}/資料/{name}.md` | project | sb project | 読み取り専用 |
| `40_tasks/active/{id}.md` | task | sb task |  |
| `40_tasks/archive/{year}/{month}/{id}.md` | task | sb task | 読み取り専用 |
| `40_tasks/タスク.base` | view | sb views |  |
| `50_media/{media_current}/current.md` | media | sb media |  |
| `50_media/{media_daily}/{date}.md` | media | sb media |  |
| `60_distilled/{distill}/{date}.md` | distilled | sb distill |  |
| `90_logs/check/{date}.md` | log | sb check |  |
| `90_logs/audits/{name}/{date}.md` | log | sb log |  |
| `90_logs/schedule/{name}.md` | log | sb log |  |
| `90_logs/handoff.md` | log | sb log |  |
| `NOW.md` | view | sb views |  |
| `README.md` | view | sb views |  |

## 項目
- 層の中のファイル名（00_inbox と 60_distilled のソース・50_media の種類・20_identity のファイル）は決めていない。英小文字・数字・_・-・/ の名前なら何でも置ける。
- 50_media で表の列を決めてある種類: browsing/web・browsing/video・likes/photo（＋current）・likes/sns（＋current）・movies（＋current）・songs/history・songs/liked（＋current）・books（＋current）・video_liked（＋current）・garden_tools（＋current）・plants。ほかの種類の列は、受け取った項目の名前。
- 90_logs の種類: check・audits・schedule・handoff
