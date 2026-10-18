---
name: write-workspace-readme
description: Workspace の中の README を作る・直すときに使う。README の種類ごとの決まった形と、書かないこと（予定・他の repo のこと）を守らせる。一覧の README は手で書かない。
---

# README の書き方

## 1. README の種類

| 種類 | 置き場 | 形 |
|---|---|---|
| repo と sb の README | `src/<repo>/README.md`・`sb/README.md` | 3章 |
| repo の中のフォルダの README | repo の中のフォルダ | 4章 |
| config の README | `config/README.md` | 5章 |
| work の README | `work/README.md` | 6章 |
| 一覧の README（自動で作る。手で直さない） | `Workspace/README.md`・`src/README.md`・`data/README.md`・`models/README.md`・`logs/README.md`・`SecondBrain/README.md` | 変えたいときは、材料の方（各 README の欄・plist）を直す |

`company/README.md` は会社側の物。個人側から中身を変えない。

## 2. 冒頭の形（全部の README）

    # <名前>

    <何をする物か。1文。>

一覧の README が3行目の1文を使う。URL や「〜してください」ではなく、「何をする物か」を1文で書く。

## 3. repo と sb の README

欄の名前と順番は固定。一覧の README が欄を読む。当てはまらない欄は空にせず `- なし` と書く。

    ## 使い方
    ## data に書く場所
    ## data から読む場所
    ## SecondBrain に書く層
    ## SecondBrain から読む層
    ## 使うモデル
    ## 定時処理
    ## 試験
    ## してはいけないこと

- **使い方:** 入口・コマンド・設定の置き場。repo の中のフォルダの README があれば、どれを読むかを1行で案内する。
- **data に書く場所:** 1行1場所で `- data/<パス>`。この repo だけが書く場所。実際にコードが書く場所を確かめて書く。
- **data から読む場所:** `- data/<パス>（書き手: <repo>）`。
- **SecondBrain に書く層・読む層:** 層と、自分が使う sb のコマンド（`- 50_media（sb media add --by <repo>/<処理>）`）。`--by` は `<repo名>/<処理>`。
- **使うモデル:** `- models/<名前>`。
- **定時処理:** 自分の定時処理ごとに `- <名前>: 何をするか1行`。launchd の物は Label から `com.taro.` を除いた名前（Label は `com.taro.<repo>.<処理>`）。エージェントの定時処理（本文が repo の `scheduled/<名前>/SKILL.md` にある物）も同じく1行。時刻は書かない（一覧の README が実物から出す）。
- **試験:** 流し方のコマンド。
- **してはいけないこと:** この repo 固有の禁止だけ。共通ルールにある一般論は書かない。

sb の README は、この欄の後ろに、コマンドと書式（層ごとの形）を書く。

## 4. repo の中のフォルダの README

冒頭の形のあとに、次の欄を書く。

    ## 使い方
    ## してはいけないこと

## 5. config の README

冒頭の形のあとに、config に置くファイルごとに1つの節を書く。節の中の項目は固定。

    ## <ファイル名>
    - 何か: 1文
    - 形: 中の項目と意味
    - 直し方: 誰の承認で、どう直し、どう確かめるか
    - してはいけないこと: このファイル固有の禁止

ファイルを読む repo の名前は書かない（読む側の README の「使い方」に書く）。

## 6. work の README

冒頭の形のあとに、次の欄を書く。

    ## 新しい物を作る
    ## 既存の repo を直す
    ## 本番へ移す
    ## してはいけないこと
    ## 片付け

## 7. 書かないこと（全部の README）

- 進み具合・予定・「要確認」・条件つきの将来の話。それらはタスクに書く。
- 他の repo・共通ルール・skill・SecondBrain の構造のこと。README は自分のことだけを書き、他が変わってもずれないようにする。他の repo について書いてよいのは、3章の「data から読む場所」の書き手の名前と、下の「手順に他の repo の道具が要るとき」の書き方だけ。
- 他の README に書いてあること。上の README は下の README を案内するだけ。
- 手順に他の repo の道具が要るときは、その repo の名前と README の欄の名前だけを書く（例:「workspace-index の README の使い方」）。コマンドやパスは書かない。
- 秘密の値。会社の具体的な情報。

## 8. docs

- docs は原則作らない。使い方は README に書く。README に収まらない長い手順だけを repo の `docs/` に置き、README から1行で案内する。
- 理由・選ばなかった案・実装の記録は docs にも書かない。

## 9. 書いたあと

workspace-index の README の「使い方」にある点検を流し、警告（冒頭1行が無い・欄が無い・data の書き手が0か2以上・書いた場所が無い）が0件になるまで直す。repo や置き場を増やしたときは、最後に同じ欄にある一覧の README の作り直しを1回流す。
