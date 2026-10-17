# config

Workspace 全体で使う設定ファイルを置く。この公開用の Workspace では、どれも偽の値。

## external_paths.json
- 何か: Workspace の外で触れてよい場所の一覧。一覧そのものはこのファイルが正本なので、README には写さない。
- 形: `workspace`・`home`（Workspace と home の場所）、`external`（触れてよい場所。項目ごとに `path` と、何のために触れるかの `why`）、`retired`（使うのをやめた場所。触れない）。
- 直し方: 足す・直す・移すときは、差分（場所と理由）を先に本人に示し、承認を得てから直す。直したら、workspace-index の README の「使い方」にある点検を流して違反0件を確かめる。

## company_confidential.json
- 何か: 会社機密ゲートの設定。会社の情報を個人側へ書き出す前に止めるための決まり。sb は書き込みのたびにこれを読み、読めなければ書かない。
- 形: 会社の目印（`content_markers`）と、書き出してはいけない置き場（`path_prefixes`・`path_globs`・`local_only_source_paths`）。
- 直し方: 本人だけが直す。
