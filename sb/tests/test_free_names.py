"""層の中のファイル名を sb が決めない（新しい名前は無ければ作る）ことと、名前を省いた show の全部返し。"""

from tests.test_inbox_media import MSG, jl

AT = "2026-09-29T23:00+09:00"


def test_new_names_are_created_and_pass_check(sbv):
    # 00_inbox: 知らないソース。件の形で messages / conversations を決め、次からは置き場に従う
    assert sbv.run("inbox", "add", "--source", "team/club", "--stdin", "--by", "c", stdin=jl(MSG)) == 0
    assert "## 21:05 読書会 — 5月 — 佐藤 → other" in sbv.read("00_inbox/messages/team/club/2026-09-29.md")
    conv = {"id": "g1:1", "時刻": "20:00", "本人": "q", "返答": "a"}
    assert sbv.run("inbox", "add", "--source", "assistant", "--at", AT, "--stdin", "--by", "c", stdin=jl(conv)) == 0
    assert "### 山田\nq\n### Assistant\na" in sbv.read("00_inbox/conversations/assistant/2026-09-29.md")
    assert sbv.run("inbox", "add", "--source", "assistant", "--stdin", "--by", "c", stdin=jl(MSG)) == 1  # 会話の置き場に連絡の形は書かない
    code, r = sbv.json("inbox", "list", "--source", "team/club")
    assert [i["id"] for i in r["items"]] == ["m1"]
    code, r = sbv.json("inbox", "ack", "--reader", "t", "--until", "g1:1")  # --source なしでも新しいソースを探す
    assert code == 0 and r["source"] == "assistant"
    # 50_media: 列を決めていない種類は JSON のキーが列。あるファイルはその表の列に従う
    rows = jl({"時刻": "21:00", "題名": "v1", "作者": "a"}, {"時刻": "22:00", "題名": "v2", "メモ": "m"})
    assert sbv.run("media", "add", "--kind", "podcast/saved", "--at", AT, "--stdin", "--by", "c", stdin=rows) == 0
    text = sbv.read("50_media/podcast/saved/2026-09-29.md")
    assert "| 時刻 | 題名 | 作者 | メモ |" in text and "| 22:00 | v2 |  | m |" in text and "# podcast/saved 2026-09-29" in text
    assert sbv.run("media", "add", "--kind", "podcast/saved", "--at", AT, "--stdin", "--by", "c",
                   stdin=jl({"時刻": "23:00", "題名": "v3"})) == 0
    assert "| 23:00 | v3 |  |  |" in sbv.read("50_media/podcast/saved/2026-09-29.md")
    assert sbv.run("media", "add", "--kind", "podcast/saved", "--at", AT, "--stdin", "--by", "c",
                   stdin=jl({"時刻": "22:50", "新しい列": "x"})) == 1
    assert sbv.run("media", "current", "--kind", "podcast/saved", "--stdin", "--by", "c", stdin=jl({"題名": "v1", "保存日": "09-29"})) == 0
    assert "| 題名 | 保存日 |" in sbv.read("50_media/podcast/saved/current.md")
    # 20_identity・60_distilled: 知らない名前も作る
    assert sbv.run("identity", "set", "hobby/knitting", "--section", "今の状態", "--why", "w", "--text", "x", "--by", "c") == 0
    assert sbv.run("distill", "write", "--source", "team", "--date", "2026-09-29", "--stdin", "--by", "c", stdin="## 分かったこと\n- y") == 0
    code, r = sbv.json("check", "--by", "c")
    assert code == 0 and r["problems"] == []


def test_show_without_name_returns_all(sbv):
    sbv.run("inbox", "add", "--source", "talk", "--stdin", "--by", "c", stdin=jl(MSG))
    sbv.run("inbox", "add", "--source", "claude", "--at", AT, "--stdin", "--by", "c",
            stdin=jl({"id": "c1:1", "時刻": "20:00", "本人": "q", "返答": "a"}))
    sbv.run("inbox", "add", "--source", "mail", "--date", "2026-09-28", "--stdin", "--by", "c",
            stdin=jl({**MSG, "時刻": "10:00"}))
    code, r = sbv.json("inbox", "show", "--date", "2026-09-29")
    assert code == 0 and r["date"] == "2026-09-29" and sorted(r["sources"]) == ["claude", "talk"]  # 記録の無いソースは含めない
    assert r["sources"]["talk"]["dir"] == "messages" and r["sources"]["talk"]["items"][0]["id"] == "m1"
    assert r["sources"]["claude"]["path"] == "00_inbox/conversations/claude/2026-09-29.md"
    code, r = sbv.json("inbox", "show")  # --date を省くと今日の論理日
    assert r["date"] == "2026-09-29" and len(r["sources"]) == 2
    code, r = sbv.json("inbox", "show", "--date", "2026-01-01")
    assert code == 0 and r["sources"] == {}

    sbv.run("media", "add", "--kind", "movies", "--at", AT, "--stdin", "--by", "c", stdin=jl({"時刻": "21:00", "題名": "A"}))
    sbv.run("media", "add", "--kind", "songs/history", "--at", AT, "--stdin", "--by", "c", stdin=jl({"時刻": "21:00", "曲名": "s"}))
    sbv.run("media", "current", "--kind", "songs/liked", "--total", "3", "--stdin", "--by", "c", stdin=jl({"曲名": "s"}))
    code, r = sbv.json("media", "show", "--date", "2026-09-29")
    assert sorted(r["kinds"]) == ["movies", "songs/history"] and "| 21:00 | A |" in r["kinds"]["movies"]["text"]
    code, r = sbv.json("media", "show")  # --date も省くと各種類の current
    assert r["date"] is None and list(r["kinds"]) == ["songs/liked"] and "総数: 3" in r["kinds"]["songs/liked"]["text"]

    sbv.run("distill", "write", "--source", "talk", "--stdin", "--by", "c", stdin="## 分かったこと\n- a")
    sbv.run("distill", "write", "--source", "mail", "--date", "2026-09-28", "--stdin", "--by", "c", stdin="## 分かったこと\n- b")
    code, r = sbv.json("distill", "show", "--date", "2026-09-29")
    assert list(r["sources"]) == ["talk"] and "- a" in r["sources"]["talk"]["text"]

    sbv.run("identity", "set", "music", "--section", "今の状態", "--why", "w", "--text", "m", "--by", "c")
    sbv.run("identity", "set", "hobby/knitting", "--section", "今の状態", "--why", "w", "--text", "c", "--by", "c")
    code, r = sbv.json("identity", "show")
    assert sorted(r["files"]) == ["hobby/knitting", "music"] and r["files"]["music"]["path"] == "20_identity/music.md"
    assert sbv.run("identity", "show") == 0 and "hobby/knitting" in sbv.out  # 人向けも JSON で出す


def test_many_files_in_one_write_open_few_locks(sbv):
    import json, resource
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    resource.setrlimit(resource.RLIMIT_NOFILE, (min(256, hard), hard))
    try:
        import datetime
        d0 = datetime.date(2024, 1, 1)  # 日ごとに1ファイル → 600ファイル
        rows = "".join(json.dumps({"時刻": f"{d0 + datetime.timedelta(days=i)}T12:00+09:00", "題名": "t", "チャンネル": "c"}, ensure_ascii=False) + "\n" for i in range(600))
        assert sbv.run("media", "add", "--kind", "video_liked", "--stdin", "--by", "importer/video", stdin=rows) == 0
    finally:
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))
    locks = list((sbv.ws / "data" / "sb" / "locks").glob("*.lock"))
    assert 1 <= len(locks) <= 3
