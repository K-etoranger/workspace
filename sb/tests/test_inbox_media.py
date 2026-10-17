import json

from tests.conftest import MARKER


def jl(*items):
    return "\n".join(json.dumps(i, ensure_ascii=False) for i in items)


MSG = {"id": "m1", "時刻": "2026-09-29T21:05:00+09:00", "相手": "佐藤", "場所": "読書会 — 5月", "向き": "other",
       "本文": "こんにちは\n# 見出しっぽい行", "元データ": "data/secondbrain/raw/talk/x.json"}


def test_inbox_add_dedupe_list_ack_show(sbv):
    assert sbv.run("inbox", "add", "--source", "talk", "--stdin", "--by", "importer/talk", stdin=jl(MSG, {**MSG, "id": "m2", "向き": "self"})) == 0
    text = sbv.read("00_inbox/messages/talk/2026-09-29.md")
    assert "## 21:05 読書会 — 5月 — 佐藤 → other" in text and "件数: 2" in text and "\\# 見出しっぽい行" in text
    code, r = sbv.json("inbox", "add", "--source", "talk", "--stdin", "--by", "c", stdin=jl(MSG, {**MSG, "id": "m3"}))
    assert code == 0 and r["added"] == 1 and r["skipped"] == 1
    code, r = sbv.json("inbox", "list", "--source", "talk")
    assert [i["id"] for i in r["items"]] == ["m1", "m2", "m3"]
    assert r["items"][0]["本文"] == MSG["本文"] and r["items"][0]["場所"] == "読書会 — 5月" and r["items"][0]["元データ"]
    assert sbv.run("inbox", "ack", "--reader", "taskizer", "--until", "m2") == 0
    code, r = sbv.json("inbox", "list", "--source", "talk", "--since", "taskizer")
    assert [i["id"] for i in r["items"]] == ["m3"]
    code, r = sbv.json("inbox", "ack", "--reader", "taskizer", "--until", "m1")
    assert r["moved"] is False  # 戻さない
    assert sbv.run("inbox", "ack", "--reader", "taskizer", "--until", "nope") == 3
    assert sbv.run("inbox", "show", "--source", "talk", "--date", "2026-09-29") == 0 and "佐藤" in sbv.out
    assert sbv.run("inbox", "show", "--source", "talk", "--date", "2026-01-01") == 3


def test_inbox_hhmm_uses_at(sbv):
    # HH:MM は --at 以前で最も近いその時刻。04:59 は前の論理日、05:00 からはその日
    for iid, t in (("a", "04:59"), ("b", "05:00")):
        assert sbv.run("inbox", "add", "--source", "mail", "--at", "2026-09-30T05:10:00+09:00", "--stdin", "--by", "c",
                       stdin=jl({**MSG, "id": iid, "時刻": t})) == 0
    assert "id: a" in sbv.read("00_inbox/messages/mail/2026-09-29.md")
    assert "id: b" in sbv.read("00_inbox/messages/mail/2026-09-30.md")
    # --at より後の時刻は前の日のその時刻（日付をまたぐ）: 09-30 01:00 に取った 23:30 は 09-29 23:30
    code, r = sbv.json("inbox", "add", "--source", "mail", "--at", "2026-09-30T01:00:00+09:00", "--stdin", "--by", "c",
                       stdin=jl({**MSG, "id": "c", "時刻": "23:30:15"}))
    assert code == 0 and r["days"] == {"2026-09-29": 1}
    assert "## 23:30 読書会" in sbv.read("00_inbox/messages/mail/2026-09-29.md")
    # SB_NOW は日を決めない（時刻から決める）
    sbv.now("2026-10-05T12:00:00+09:00")
    code, r = sbv.json("inbox", "add", "--source", "mail", "--stdin", "--by", "c", stdin=jl({**MSG, "id": "d"}))
    assert r["path"] == "00_inbox/messages/mail/2026-09-29.md"


def test_inbox_splits_days(sbv):
    items = [{**MSG, "id": "x1", "時刻": "2026-09-30T04:59:00+09:00"}, {**MSG, "id": "x2", "時刻": "2026-09-29T20:00:00Z"},
             {**MSG, "id": "x3", "時刻": "2026-09-28T10:00:00+09:00"}]
    code, r = sbv.json("inbox", "add", "--source", "talk", "--stdin", "--by", "c", stdin=jl(*items))
    assert code == 0 and r["added"] == 3 and "path" not in r
    assert r["days"] == {"2026-09-28": 1, "2026-09-29": 1, "2026-09-30": 1}  # 20:00Z は 09-30 05:00 JST
    assert r["paths"] == [f"00_inbox/messages/talk/2026-09-{d}.md" for d in ("28", "29", "30")]
    assert "id: x2" in sbv.read("00_inbox/messages/talk/2026-09-30.md") and "## 05:00" in sbv.read("00_inbox/messages/talk/2026-09-30.md")
    code, r = sbv.json("inbox", "list", "--source", "talk")
    assert [(i["id"], i["date"]) for i in r["items"]] == [("x3", "2026-09-28"), ("x1", "2026-09-29"), ("x2", "2026-09-30")]
    code, r = sbv.json("inbox", "add", "--source", "talk", "--stdin", "--by", "c", stdin=jl(*items))
    assert r["added"] == 0 and r["skipped"] == 3


def test_inbox_refuses_undated_and_mismatch(sbv):
    ok = {**MSG, "id": "ok"}
    # 1件でも日が決まらなければ何も書かない
    for bad in ({**MSG, "id": "n1", "時刻": "20:00"}, {**MSG, "id": "n2", "時刻": "2026-09-29T20:00:00"}):
        assert sbv.run("inbox", "add", "--source", "talk", "--stdin", "--by", "c", stdin=jl(ok, bad)) == 1
    assert not (sbv.vault / "00_inbox").exists() and sbv.json("inbox", "list", "--source", "talk")[1]["items"] == []
    assert sbv.run("inbox", "add", "--source", "talk", "--at", "2026-09-29T20:00", "--stdin", "--by", "c", stdin=jl(ok)) == 1
    # --date は今どおり。HH:MM・タイムゾーンの無い ISO はその日、タイムゾーン付き ISO が別の日なら断る
    assert sbv.run("inbox", "add", "--source", "talk", "--date", "2026-09-30", "--stdin", "--by", "c", stdin=jl(ok)) == 1
    assert sbv.run("inbox", "add", "--source", "talk", "--date", "2026-09-30", "--stdin", "--by", "c",
                   stdin=jl({**MSG, "id": "h", "時刻": "04:00"}, {**MSG, "id": "i", "時刻": "2026-09-30T06:00:00+09:00"})) == 0
    assert "id: h" in sbv.read("00_inbox/messages/talk/2026-09-30.md")
    assert sbv.run("inbox", "add", "--source", "talk", "--date", "2026-09-29", "--stdin", "--by", "c", stdin=jl(ok)) == 0


def test_day_command(sbv):
    code, r = sbv.json("day")  # SB_NOW 2026-09-29T20:00
    assert r["date"] == "2026-09-29" and r["start"] == "2026-09-29T05:00+09:00" and r["end"] == "2026-09-30T05:00+09:00"
    assert sbv.json("day", "--at", "2026-09-30T04:59:59+09:00")[1]["date"] == "2026-09-29"
    assert sbv.json("day", "--at", "2026-09-30T05:00:00+09:00")[1]["date"] == "2026-09-30"
    assert sbv.json("day", "--at", "2026-09-29T20:00:00Z")[1]["date"] == "2026-09-30"
    assert sbv.json("day", "--date", "2026-12-31")[1]["end"] == "2027-01-01T05:00+09:00"
    code, r = sbv.json("day", "--stdin", stdin="2026-09-30T04:59+09:00\n\n2026-09-30T05:00+09:00\n")
    assert r["days"] == [{"at": "2026-09-30T04:59+09:00", "date": "2026-09-29"}, {"at": "2026-09-30T05:00+09:00", "date": "2026-09-30"}]
    assert sbv.run("day", "--stdin", stdin="2026-09-30T05:00") == 1  # タイムゾーンの無い日時
    assert sbv.run("day", "--at", "2026-09-30T05:00+09:00", "--date", "2026-09-30") == 1


def test_conversation_format(sbv):
    item = {"id": "abcdef1234567:2026-09-29T20:00", "時刻": "20:00", "本人": "質問", "返答": "答え\n## 混入"}
    assert sbv.run("inbox", "add", "--source", "claude", "--at", "2026-09-29T20:30+09:00", "--stdin", "--by", "c", stdin=jl(item)) == 0
    text = sbv.read("00_inbox/conversations/claude/2026-09-29.md")
    assert "## 20:00 abcdef12" in text and "### 山田\n質問\n### Claude" in text and "会話数: 1" in text
    code, r = sbv.json("inbox", "list", "--source", "claude")
    assert r["items"][0]["返答"] == "答え\n## 混入"


def test_inbox_refusals(sbv):
    # 秘密の値だけ伏せて書く。終了コードは 0（収集が止まり続けないように）。会社の言葉はそのまま書く
    code, r = sbv.json("inbox", "add", "--source", "talk", "--stdin", "--by", "c",
                       stdin=jl({**MSG, "本文": "今日 password=hunter2x だよ"}, {**MSG, "id": "m9", "本文": MARKER}))
    assert code == 0 and r["added"] == 2 and r["masked"] == [{"id": "m1", "伏せた": ["パスワード"]}]
    text = sbv.read("00_inbox/messages/talk/2026-09-29.md")
    assert "hunter2x" not in sbv.out + text and "今日 password=〈伏せた〉 だよ" in text and MARKER in text
    assert sbv.run("inbox", "add", "--source", "Team", "--stdin", "--by", "c", stdin=jl(MSG)) == 1
    assert sbv.run("inbox", "add", "--source", "talk", "--stdin", "--by", "c", stdin="{bad") == 1
    assert sbv.run("inbox", "add", "--source", "talk", "--stdin", "--by", "c", stdin=jl({**MSG, "向き": "x"})) == 1
    assert sbv.run("inbox", "add", "--source", "talk", "--stdin", "--by", "c", stdin=jl({**MSG, "謎": 1})) == 1
    code, r = sbv.json("inbox", "list", "--source", "talk")
    assert [i["id"] for i in r["items"]] == ["m1", "m9"]


def test_inbox_mask_keeps_every_item(sbv):
    code, r = sbv.json("inbox", "add", "--source", "talk", "--stdin", "--by", "c",
                       stdin=jl({**MSG, "本文": "key sk-abcdefghijklmnopqrstuvwx と eyJhbGciOiJIUzI1.eyJzdWIiOiIxMjM0.abc"}))
    assert code == 0 and r["added"] == 1 and sorted(r["masked"][0]["伏せた"]) == ["JWT", "sk- のAPIキー"]
    text = sbv.read("00_inbox/messages/talk/2026-09-29.md")
    assert "key 〈伏せた〉 と 〈伏せた〉" in text
    code, r = sbv.json("inbox", "list", "--source", "talk")
    assert [i["id"] for i in r["items"]] == ["m1"]


def test_media_add_current_item_show(sbv):
    rows = jl({"時刻": "21:00", "題名": "作品A", "詳細": "S1E1", "元データ": "data/x"}, {"時刻": "22:00", "題名": "作品B|x"})
    at = "2026-09-29T23:00+09:00"
    assert sbv.run("media", "add", "--kind", "movies", "--at", at, "--stdin", "--by", "importer/movies", stdin=rows) == 0
    code, r = sbv.json("media", "add", "--kind", "movies", "--at", at, "--stdin", "--by", "c", stdin=rows)
    assert r["added"] == 0 and r["path"] == "50_media/movies/2026-09-29.md"
    text = sbv.read("50_media/movies/2026-09-29.md")
    assert "| 21:00 | 作品A | S1E1 | data/x |" in text and "作品B\\|x" in text and "件数: 2" in text
    assert sbv.run("media", "current", "--kind", "songs/liked", "--total", "163", "--stdin", "--by", "c",
                   stdin=jl({"曲名": "s", "アーティスト": "a", "追加日": "2026-09-01"})) == 0
    cur = sbv.read("50_media/songs/liked/current.md")
    assert "総数: 163" in cur and "現在値: true" in cur and "| s | a | 2026-09-01 |" in cur
    assert sbv.run("media", "add", "--kind", "video_liked", "--at", at, "--stdin", "--by", "c",
                   stdin=jl({"時刻": "21:30", "チャンネル": "c", "題名": "t", "リンク": "https://example.com/v/x"})) == 0
    assert "| 21:30 | c | t | https://example.com/v/x |" in sbv.read("50_media/video_liked/2026-09-29.md")
    assert sbv.run("media", "current", "--kind", "video_liked", "--stdin", "--by", "c",
                   stdin=jl({"時刻": "2026-09-29T12:30:00Z", "チャンネル": "c", "題名": "t", "リンク": "u"},
                            {"時刻": "08:05", "チャンネル": "c2", "題名": "t2", "リンク": "u2"},
                            {"時刻": "2026-09-30", "チャンネル": "c3", "題名": "t3", "リンク": "u3"})) == 0
    cur = sbv.read("50_media/video_liked/current.md")
    assert "| 2026-09-29 21:30 | c | t | u |" in cur and "| 08:05 | c2 | t2 | u2 |" in cur  # 一覧は日付も残す
    assert "| 2026-09-30 | c3 | t3 | u3 |" in cur  # 日付だけなら時刻を作らない
    assert sbv.run("media", "show", "--kind", "movies") == 3  # current.md はまだ無い
    assert sbv.run("media", "show", "--kind", "movies", "--date", "2026-09-29") == 0 and "作品A" in sbv.out
    assert sbv.run("media", "show", "--kind", "songs/liked") == 0 and "163" in sbv.out


def test_media_refusals(sbv):
    assert sbv.run("media", "add", "--kind", "Podcast", "--stdin", "--by", "c", stdin="{}") == 1
    assert sbv.run("media", "current", "--kind", "browsing/web", "--stdin", "--by", "c", stdin="{}") == 1
    assert sbv.run("media", "add", "--kind", "garden_tools", "--stdin", "--by", "c", stdin="{}") == 1
    assert sbv.run("media", "add", "--kind", "movies", "--stdin", "--by", "c", stdin=jl({"題名": "x", "謎": 1})) == 1
    assert sbv.run("media", "add", "--kind", "video_liked", "--at", "2026-09-29T20:00+09:00", "--stdin", "--by", "c", stdin=jl({"動画ID": "x"})) == 1
    code, r = sbv.json("media", "add", "--kind", "movies", "--at", "2026-09-29T20:00+09:00", "--stdin", "--by", "c",
                       stdin=jl({"題名": "sk-abcdefghijklmnopqrstuvwx"}, {"題名": "ok"}))
    assert code == 0 and r["added"] == 2 and r["masked"] == [{"line": 1, "伏せた": ["sk- のAPIキー"]}]
    text = sbv.read("50_media/movies/2026-09-29.md")
    assert "sk-abc" not in text and "〈伏せた〉" in text
    assert sbv.run("media", "show", "--kind", "books") == 3


def test_media_days(sbv):
    rows = jl({"時刻": "2026-09-30T04:59:00+09:00", "曲名": "a"}, {"時刻": "2026-09-30T05:00:00+09:00", "曲名": "b"}, {"曲名": "c"})
    code, r = sbv.json("media", "add", "--kind", "songs/history", "--at", "2026-09-30T06:00+09:00", "--stdin", "--by", "c", stdin=rows)
    assert code == 0 and r["days"] == {"2026-09-29": 1, "2026-09-30": 2} and "path" not in r
    assert "| 04:59 | a |" in sbv.read("50_media/songs/history/2026-09-29.md")
    today = sbv.read("50_media/songs/history/2026-09-30.md")
    assert "| 05:00 | b |" in today and "|  | c |" in today and "件数: 2" in today
    # 日の決まらない件（時刻が空で --at も無い）があれば何も書かない
    assert sbv.run("media", "add", "--kind", "plants", "--stdin", "--by", "c",
                   stdin=jl({"時刻": "2026-09-29T20:00+09:00", "内容": "x"}, {"内容": "y"})) == 1
    assert not (sbv.vault / "50_media/plants").exists()
    # --date と食い違うタイムゾーン付き ISO は断る。合う物・HH:MM はその日に書く
    assert sbv.run("media", "add", "--kind", "plants", "--date", "2026-09-28", "--stdin", "--by", "c",
                   stdin=jl({"時刻": "2026-09-29T20:00+09:00", "内容": "x"})) == 1
    assert sbv.run("media", "add", "--kind", "plants", "--date", "2026-09-28", "--stdin", "--by", "c",
                   stdin=jl({"時刻": "2026-09-29T04:00+09:00", "内容": "x"}, {"時刻": "20:00", "内容": "y"})) == 0
    assert "件数: 2" in sbv.read("50_media/plants/2026-09-28.md")
