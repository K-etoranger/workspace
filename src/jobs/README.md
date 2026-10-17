# jobs

全部の repo の定時処理を Mac へ配置する。

## 使い方

定時処理の配置（`bin/launchd_deploy.py`）:

```sh
python3 bin/launchd_deploy.py           # 確認だけ。入れる・置き換える・控えへ移す予定と、読み込み直しのコマンドを出す
python3 bin/launchd_deploy.py --apply   # 実際に置き、原本とバイト単位で同じかを確かめる
```

- 原本は `src/*/launchd/com.taro.*.plist` と `sb/launchd/com.taro.*.plist`。置き先は `~/Library/LaunchAgents`。
- LaunchAgents にある `com.taro.*` で、どの原本にも無い物は `~/Documents/_archive_<日付>/LaunchAgents/` へ移す。
- Label とファイル名が違う物、同じ Label が2つの repo にある物があれば、何もしないで止まる。
- launchctl は呼ばない。最後に出る読み込み直しのコマンド（`launchctl bootout` / `bootstrap`）を、要る分だけ手で流す。
- 確認だけのとき、変更があれば終了コードは 1。
- Workspace・置き先・控えの場所は環境変数 `WORKSPACE`・`LAUNCH_AGENTS`・`LAUNCHD_ARCHIVE` で変えられる（試験用）。

配置の手順:

1. 持ち主の README と、今の source・runtime・plist・状態・ログを見る。
2. 証拠とハッシュを残して source を直す。
3. 試験する（境界・失敗・実際の事例）。
4. `bin/launchd_deploy.py` で同期し、source と runtime のハッシュを揃える。
5. 変えた常駐だけ、動いている作業を確かめてから再起動する。文章だけの変更で無関係の常駐を再起動しない。
6. 変えた入口で動きを確かめる。

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

定時処理の時刻を変える前に、今入っている LaunchAgent と各エージェントの定時処理を全部見る（過去の説明を信じない）。前の処理の結果を使う処理は、前の処理が終わる時刻より後に起動する。

## 試験
```sh
python3 -m pytest -q tests
```
一時フォルダだけを使う。本物の LaunchAgents・launchd には触れない。

## してはいけないこと
- `--apply` の前に、確認だけを流して `archive` の行を見る。repo の `launchd/` から消えた plist は、`--apply` で LaunchAgents からも外れる。
- 出てきた読み込み直しのコマンド（bootout / bootstrap）を、まとめて流さない。対象の repo の README の「してはいけないこと」を見てから、1本ずつ流す。
