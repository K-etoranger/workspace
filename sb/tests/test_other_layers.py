import hashlib

from tests.conftest import MARKER


def test_identity_set_writes_daily(sbv):
    assert sbv.run("identity", "set", "music", "--section", "今の状態", "--why", "貸出の履歴",
                   "--stdin", "--by", "distill-preferences", stdin="### ジャンル\nミステリー") == 0
    text = sbv.read("20_identity/music.md")
    assert "ファイル: music" in text and "# music" in text and "## 今の状態\n### ジャンル\nミステリー" in text
    daily = sbv.read("10_daily/2026/2026-09-29.md")
    assert "- music: 足した「### ジャンル」\n- music: 足した「ミステリー」\n- music: 理由: 貸出の履歴" in daily
    assert sbv.run("identity", "show", "music") == 0 and "ミステリー" in sbv.out
    assert sbv.run("identity", "set", "Secrets", "--section", "今の状態", "--why", "w", "--text", "x", "--by", "c") == 1
    assert sbv.run("identity", "set", "../x", "--section", "今の状態", "--why", "w", "--text", "x", "--by", "c") == 1
    assert sbv.run("identity", "set", "profile", "--section", "謎の節", "--why", "w", "--text", "x", "--by", "c") == 1
    assert sbv.run("identity", "set", "profile", "--section", "今の状態", "--why", "w", "--text", "sk-abcdefghijklmnopqrstuvwx", "--by", "c") == 4
    assert not (sbv.vault / "20_identity/profile.md").exists()
    assert sbv.run("identity", "show", "profile") == 3


def _changes(sbv):
    from sb import frontmatter
    return frontmatter.get_section(frontmatter.parse(sbv.read("10_daily/2026/2026-09-29.md"))[1], "本人像の変化")


def test_identity_change_lines(sbv):
    def put(sec, text, *why):
        return sbv.run("identity", "set", "music", "--section", sec, *why, "--stdin", "--by", "c", stdin=text)
    assert put("今の状態", "- A\n- B\n\n  C  ") == 0  # --why 無し・足しだけ
    assert _changes(sbv) == "- music: 足した「A」\n- music: 足した「B」\n- music: 足した「C」"
    daily = sbv.read("10_daily/2026/2026-09-29.md")
    assert put("今の状態", "B\nC\nA", "--why", "w") == 0  # 順番だけ・箇条書きの有無だけ: 20_identity は書き、10_daily は書かない
    assert "## 今の状態\nB\nC\nA" in sbv.read("20_identity/music.md") and sbv.read("10_daily/2026/2026-09-29.md") == daily
    assert put("今の状態", "A\nD", "--why", "新しい") == 0  # 書き換え=消した→足した（元の順）
    assert _changes(sbv).split("\n")[3:] == ["- music: 消した「B」", "- music: 消した「C」", "- music: 足した「D」", "- music: 理由: 新しい"]
    before, daily = sbv.read("20_identity/music.md"), sbv.read("10_daily/2026/2026-09-29.md")
    assert put("今の状態", "A\nD", "--why", "同じ") == 0  # 中身が同じ: 何も書かない
    assert sbv.read("20_identity/music.md") == before and sbv.read("10_daily/2026/2026-09-29.md") == daily
    assert put("根拠の出どころ", "X") == 0 and "- music（根拠の出どころ）: 足した「X」" in _changes(sbv)
    assert not (sbv.vault / "20_identity/new.md").exists()
    assert sbv.run("identity", "set", "new", "--section", "今の状態", "--text", "", "--by", "c") == 0  # 新規で空: 差なし
    assert not (sbv.vault / "20_identity/new.md").exists()


def test_daily_write(sbv):
    assert sbv.run("daily", "write", "--date", "2026-09-28", "--section", "今日の要約", "--text", "静かな日", "--by", "distill-daily") == 0
    assert sbv.run("daily", "write", "--date", "2026-09-28", "--section", "出来事", "--text", "- 10:00 水やり", "--by", "distill-daily") == 0
    text = sbv.read("10_daily/2026/2026-09-28.md")
    assert "## 今日の要約\n静かな日" in text and "- 10:00 水やり" in text and "## 使えた記録" in text
    assert sbv.run("daily", "write", "--section", "感想", "--text", "x", "--by", "c") == 1


def test_distill_write(sbv):
    body = "## 分かったこと\n- 紅茶派 — 根拠: x\n## 読んだが使わなかった物\n- 3件（広告）\n"
    assert sbv.run("distill", "write", "--source", "talk", "--date", "2026-09-29", "--read-count", "12", "--adopted", "3",
                   "--stdin", "--by", "distill-messages", stdin=body) == 0
    text = sbv.read("60_distilled/talk/2026-09-29.md")
    assert "読んだ件数: 12" in text and "採用: 3" in text and "## 分かったこと\n- 紅茶派" in text
    assert "## 要対応（タスクにした物・しなかった物）" in text
    assert sbv.run("distill", "write", "--source", "talk", "--stdin", "--by", "c", stdin="## 変な節\nx") == 1
    assert sbv.run("distill", "write", "--source", "talk", "--stdin", "--by", "c", stdin="見出し無し") == 1
    assert sbv.run("distill", "write", "--source", "Podcast", "--stdin", "--by", "c", stdin="") == 1


def test_logs(sbv):
    assert sbv.run("log", "weather", "--text", "x", "--by", "w") == 1  # 書く物がいないので無い
    assert sbv.run("log", "audit", "--name", "task-ledger", "--date", "2026-09-29", "--text", "結論: 問題なし", "--by", "c") == 0
    assert sbv.run("log", "audit", "--name", "task-ledger", "--date", "2026-09-29", "--text", "上書き", "--by", "c") == 1
    assert sbv.run("log", "audit", "--name", "../x", "--text", "x", "--by", "c") == 1
    assert sbv.run("log", "schedule", "--task", "task-checks", "--text", "3件タスク化", "--by", "w") == 0
    assert sbv.run("log", "schedule", "--task", "task-checks", "--text", "次は0件", "--by", "w") == 0
    sched = sbv.read("90_logs/schedule/task-checks.md")
    assert sched.count("## 2026-09-29 20:00") == 2
    assert sbv.run("log", "handoff", "--text", "要旨 / sb / pytest / task:20260929-x", "--by", "codex") == 0
    assert "- 2026-09-29 20:00 [codex] 要旨 / sb / pytest / task:20260929-x" in sbv.read("90_logs/handoff.md")
    assert sbv.run("log", "handoff", "--text", "x", "--by", "assistant") == 0   # エージェントの名前は限らない
    assert "[assistant] x" in sbv.read("90_logs/handoff.md")


def _snapshot(root):
    return {p.relative_to(root).as_posix(): hashlib.sha1(p.read_bytes()).hexdigest() + str(p.stat().st_mtime_ns)
            for p in (root / "40_tasks").rglob("*.md")}


def test_views_now_and_never_touch_tasks(sbv):
    sbv.run("project", "new", "生活", "--purpose", "x", "--by", "c")
    mk = lambda *a: sbv.json("task", "new", "--owner", "本人", "--by", "c", *a)[1]["id"]
    overdue = mk("--title", "overdue", "--due", "2026-09-28")
    today = mk("--title", "today", "--due", "2026-09-29", "--estimate", "本人15分")
    tomorrow = mk("--title", "tomorrow", "--due", "2026-09-30")
    later = mk("--title", "later", "--due", "2026-10-10")
    ev = mk("--title", "event", "--type", "予定", "--start", "2026-09-30 01:00")  # 論理日は 29 日
    rv = mk("--title", "review me")
    sbv.run("task", "review", rv, "--text", "見て", "--by", "c")
    wt = mk("--title", "waiting")
    sbv.run("task", "wait", wt, "--for", "返信", "--recheck", "2026-09-29", "--by", "c")
    wt2 = mk("--title", "waiting later")
    sbv.run("task", "wait", wt2, "--for", "返信", "--recheck", "2026-10-05", "--by", "c")
    ip = mk("--title", "doing", "--due", "2026-09-29")
    sbv.run("task", "start", ip, "--by", "c")
    before = _snapshot(sbv.vault)
    assert sbv.run("views", "refresh", "--by", "sb/views-refresh") == 0
    assert _snapshot(sbv.vault) == before
    from sb import frontmatter
    now = sbv.read("NOW.md")
    _, body = frontmatter.parse(now)
    sec = lambda n: frontmatter.get_section(body, n)
    assert frontmatter.headings(body) == ["今日の予定", "期限切れ", "今日まで", "明日まで", "本人の確認待ち", "待ち", "作業中"]
    assert ev in sec("今日の予定") and overdue in sec("期限切れ")
    assert today in sec("今日まで") and ip in sec("今日まで") and "本人15分" in sec("今日まで")
    assert tomorrow in sec("明日まで") and later not in now
    assert rv in sec("本人の確認待ち") and wt in sec("待ち") and wt2 not in now and ip in sec("作業中")
    assert f"[[40_tasks/active/{today}|today]]" in now
    base = sbv.read("40_tasks/タスク.base")
    assert 'file.inFolder("40_tasks/active")' in base and "name: 案件別" in base and "name: 今日" in base
    readme = sbv.read("README.md")
    assert "00_inbox/messages" in readme and "名前なら何でも" in readme and "weather" not in readme and "索引" not in readme and "書く物" not in readme
    # 日付が同じなら2回目は書かない
    code, r = sbv.json("views", "refresh", "--by", "sb/views-refresh")
    assert all(e["action"] != "write" for e in r["plan"])


def test_views_skip_task_deleted_while_reading(sbv, monkeypatch):
    """一覧を取った後にタスクのファイルが消えても（別の書き込みで archive へ移った）、飛ばして続ける。"""
    from pathlib import Path
    keep = sbv.json("task", "new", "--title", "keep", "--owner", "本人", "--due", "2026-09-29", "--by", "c")[1]["id"]
    gone = sbv.json("task", "new", "--title", "gone", "--owner", "本人", "--due", "2026-09-29", "--by", "c")[1]["id"]
    real = Path.read_text

    def vanish(self, *a, **k):
        if self.name == f"{gone}.md":
            raise FileNotFoundError(2, "No such file or directory", str(self))
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", vanish)
    assert sbv.run("views", "refresh", "--by", "sb/views-refresh") == 0
    monkeypatch.setattr(Path, "read_text", real)
    now = sbv.read("NOW.md")
    assert keep in now and gone not in now


def test_check_malformed_vault(sbv):
    sbv.run("project", "new", "p", "--purpose", "x", "--by", "c")
    sbv.write("20_identity/profile.md", "# Profile\n\n## 今の状態\nx\n\n## 根拠の出どころ\n")
    sbv.write("60_distilled/talk/notes.md", "---\n形式: 1\n種類: distilled\n---\n# m\n")
    sbv.write("40_tasks/active/20260929-bad.md", "---\n種類: task\n---\n# 件名だけ\n")
    sbv.write("10_daily/2026/2026-09-28.md", "---\n形式: 1\n種類: daily\n壊れた行\n---\n# x\n")
    sbv.write("30_projects/active/p/資料/note.md", "---\n形式: 1\n種類: project\n---\n# note\n")
    sbv.write("50_media/movies/.2026-09-29.md.sb-tmp-9-abc", "書きかけ")
    sbv.write("misc/image.png", "x")
    code, r = sbv.json("check", "--by", "sb/check")
    assert code == 1
    probs = {p["path"]: p["problem"] for p in r["problems"]}
    assert probs["20_identity/profile.md"] == "頭書きが無い"
    assert "置き場所が決まりにない" in probs["60_distilled/talk/notes.md"]
    assert "形式" in probs["40_tasks/active/20260929-bad.md"] and "見出しが無い: 内容・経緯" in probs["40_tasks/active/20260929-bad.md"]
    assert "頭書きが読めない" in probs["10_daily/2026/2026-09-28.md"]
    assert probs["misc/image.png"] == "md 以外のファイル"
    assert "30_projects/active/p/メモ.md" not in probs and "30_projects/active/p/資料/note.md" not in probs
    assert not any("sb-tmp" in p for p in probs)
    log = sbv.read("90_logs/check/2026-09-29.md")
    assert "20_identity/profile.md" in log and "件数: 5" in log
    code, r = sbv.json("check", "--fix", "--by", "sb/check")
    fixed = {p["path"]: p["fixed"] for p in r["problems"]}
    assert fixed["20_identity/profile.md"] == "頭書きを補完" and fixed["60_distilled/talk/notes.md"] == "いいえ"
    prof = sbv.read("20_identity/profile.md")
    assert prof.startswith("---\n形式: 1\n種類: identity\n") and prof.endswith("## 今の状態\nx\n\n## 根拠の出どころ\n")
    assert "形式: 1" in sbv.read("40_tasks/active/20260929-bad.md")
    code, r = sbv.json("check", "--by", "sb/check")
    assert "20_identity/profile.md" not in {p["path"] for p in r["problems"]}
    assert "40_tasks/active/20260929-bad.md" in {p["path"] for p in r["problems"]}  # 見出しは直さない


def test_check_clean_vault(sbv):
    sbv.run("views", "refresh", "--by", "c")
    code, r = sbv.json("check", "--by", "c")
    assert code == 0 and r["problems"] == [] and r["checked"] == 2


def test_project_status_can_replace_decided_section(sbv):
    assert sbv.run("project", "new", "p1", "--purpose", "試す", "--by", "本人") == 0
    assert sbv.run("project", "status", "p1", "--section", "決まっていること", "--stdin", "--by", "claude", stdin="- 決めたこと") == 0
    assert sbv.run("project", "status", "p1", "--stdin", "--by", "claude", stdin="- 今のこと") == 0
    text = sbv.read("30_projects/active/p1/メモ.md")
    assert "## 決まっていること\n- 決めたこと" in text and "## 今の状態\n- 今のこと" in text
    assert sbv.run("project", "status", "p1", "--section", "目的", "--stdin", "--by", "claude", stdin="新しい目的") == 0
    assert sbv.run("project", "status", "p1", "--section", "経緯", "--stdin", "--by", "claude", stdin="- 2026-09-01 始めた\n- 2026-09-02 決めた") == 0
    assert sbv.run("project", "meta", "p1", "--start", "2026-09-01", "--repo", "src/a", "--repo", "src/b", "--by", "claude") == 0
    text = sbv.read("30_projects/active/p1/メモ.md")
    assert "## 目的\n新しい目的" in text and "## 経緯\n- 2026-09-01 始めた\n- 2026-09-02 決めた" in text
    assert "開始: 2026-09-01" in text and "関連repo: [src/a, src/b]" in text and "関連data: []" in text
    assert sbv.run("project", "meta", "p1", "--by", "claude") == 1  # 何も渡さない
    assert sbv.run("project", "status", "p1", "--section", "謎", "--stdin", "--by", "claude", stdin="x") != 0
