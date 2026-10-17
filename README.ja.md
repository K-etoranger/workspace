# Workspace

山田太郎の作業・記憶・仕組みの置き場。この中だけで作業する。

この README は `src/workspace-index` が作る。手で直さない。

| 置き場 | 何か | 使うなら読む |
|---|---|---|
| `SecondBrain/` | 本人の記憶を md だけで置く場所。層ごとの書き方と sb のコマンドは `sb/README.md` を見る。 | [`SecondBrain/README.md`](SecondBrain/README.md) |
| `company/` | 勤務先の資料。会社側が持ち、個人側から中身を変えない。 | [`company/README.md`](company/README.md) |
| `config/` | Workspace 全体で使う設定ファイルを置く。この公開用の Workspace では、どれも偽の値。 | [`config/README.md`](config/README.md) |
| `data/` | 仕組みが書くデータの置き場。フォルダごとに書き手は1つの repo だけ。 | [`data/README.md`](data/README.md) |
| `logs/` | 定時処理のログの置き場。 | [`logs/README.md`](logs/README.md) |
| `models/` | 仕組みが使うモデルの置き場。直下はモデル名のフォルダだけ。 | [`models/README.md`](models/README.md) |
| `sb/` | SecondBrain を読み書きする唯一の入口（CLI）。 | [`sb/README.md`](sb/README.md) |
| `src/` | 仕組み（コード）の置き場。1システム1repo。 | [`src/README.md`](src/README.md) |
| `work/` | 新しい物を作り、既存の repo を直すための作業場。ここから何も稼働させない。 | [`work/README.md`](work/README.md) |

Workspace の外に触れてよい場所は [`config/README.md`](config/README.md) を見る。
