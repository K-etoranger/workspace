import hashlib

from tests.conftest import MARKER


def new_task(sbv, title="洗濯", **opts):
    argv = ["task", "new", "--title", title, "--owner", opts.pop("owner", "本人"), "--by", "claude"]
    for k, v in opts.items():
        argv += [f"--{k.replace('_', '-')}", v]
    code, r = sbv.json(*argv)
    assert code == 0, sbv.out
    return r["id"]


def test_task_lifecycle(sbv):
    tid = new_task(sbv, "Laundry day", due="2026-09-30", priority="高", estimate="本人15分", text="干す")
    assert tid == "20260929-laundry-day"
    text = sbv.read(f"40_tasks/active/{tid}.md")
    assert "期限: 2026-09-30 23:59" in text and "状態: open" in text and "## 内容\n干す" in text
    assert new_task(sbv, "Laundry day") == "20260929-laundry-day-2"
    jp = new_task(sbv, "洗濯")
    assert jp == "20260929-t" + hashlib.sha1("洗濯".encode()).hexdigest()[:6]
    assert sbv.run("task", "update", tid, "--title", "Laundry", "--due", "2026-10-01 10:00", "--by", "c") == 0
    text = sbv.read(f"40_tasks/active/{tid}.md")
    assert "# Laundry\n" in text and "件名: Laundry" in text and "期限: 2026-10-01 10:00" in text
    assert sbv.run("task", "note", tid, "--text", "洗剤を買った", "--by", "c") == 0
    assert sbv.run("task", "start", tid, "--by", "c") == 0 and "状態: in_progress" in sbv.read(f"40_tasks/active/{tid}.md")
    assert sbv.run("task", "wait", tid, "--for", "晴れ", "--recheck", "2026-10-02", "--by", "c") == 0
    text = sbv.read(f"40_tasks/active/{tid}.md")
    assert "状態: waiting" in text and "待ち: 晴れ" in text and "次の確認: 2026-10-02" in text
    assert sbv.run("task", "review", tid, "--text", "干し方を見て", "--by", "c") == 0
    text = sbv.read(f"40_tasks/active/{tid}.md")
    assert "状態: needs_review" in text and "待ち:\n" in text and "確認依頼: 干し方を見て" in text
    assert sbv.run("task", "done", tid, "--text", "乾いた", "--by", "本人") == 0
    arel = f"40_tasks/archive/2026/09/{tid}.md"
    assert "状態: done" in sbv.read(arel) and not (sbv.vault / f"40_tasks/active/{tid}.md").exists()
    assert sbv.run("task", "note", tid, "--text", "x", "--by", "c") == 4  # archive は読み取り専用
    assert sbv.run("task", "done", tid, "--by", "c") == 4
    code, r = sbv.json("task", "list")
    assert tid not in [t["ID"] for t in r["tasks"]]
    code, r = sbv.json("task", "list", "--all", "--state", "done")
    assert [t["ID"] for t in r["tasks"]] == [tid]
    assert sbv.run("task", "show", tid) == 0 and "乾いた" in sbv.out
    assert sbv.run("task", "reopen", tid, "--by", "本人") == 0
    assert "状態: open" in sbv.read(f"40_tasks/active/{tid}.md") and not (sbv.vault / arel).exists()
    assert sbv.run("task", "reopen", tid, "--by", "本人") == 1
    assert sbv.run("task", "cancel", tid, "--reason", "不要", "--by", "本人") == 0


def test_task_list_filters(sbv):
    sbv.run("project", "new", "生活", "--purpose", "暮らし", "--by", "本人")
    a = new_task(sbv, "a task", due="2026-09-29", project="生活")
    b = new_task(sbv, "b task", owner="エージェント", due="2026-10-10")
    c = new_task(sbv, "c event", type="予定", start="2026-09-29 21:00")
    ids = lambda *argv: [t["ID"] for t in sbv.json("task", "list", *argv)[1]["tasks"]]
    assert ids("--owner", "エージェント") == [b]
    assert ids("--project", "生活") == [a]
    assert ids("--type", "予定") == [c]
    assert ids("--due-before", "2026-09-30") == [a]


def test_task_refusals(sbv):
    assert sbv.run("task", "new", "--title", "x", "--owner", "本人", "--project", "無い案件", "--by", "c") == 3
    assert sbv.run("task", "new", "--title", "x", "--owner", "誰か", "--by", "c") == 1
    assert sbv.run("task", "new", "--title", "x", "--owner", "本人", "--id", "Bad_ID", "--by", "c") == 1
    assert sbv.run("task", "new", "--title", "x", "--owner", "本人", "--due", "明日", "--by", "c") == 1
    assert sbv.run("task", "new", "--title", "x", "--owner", "本人", "--repeat", "毎時", "--by", "c") == 1
    assert sbv.run("task", "new", "--title", "x", "--owner", "本人", "--type", "予定", "--by", "c") == 1
    assert sbv.run("task", "new", "--title", "x", "--owner", "本人", "--text", "sk-abcdefghijklmnopqrstuvwx", "--by", "c") == 4
    assert sbv.run("task", "new", "--title", "x", "--owner", "本人", "--text", "ghp_" + "a" * 30, "--by", "c") == 4
    assert sbv.run("task", "start", "20260101-none", "--by", "c") == 3
    tid = new_task(sbv, "dup", id="20260929-dup")
    assert sbv.run("task", "new", "--title", "x", "--owner", "本人", "--id", tid, "--by", "c") == 1
    assert sbv.run("task", "update", tid, "--by", "c") == 1
    assert sbv.run("task", "update", tid, "--project", "無い案件", "--by", "c") == 3
    assert sbv.run("task", "cancel", tid, "--reason", " ", "--by", "c") == 1
    assert not list((sbv.vault / "40_tasks").rglob("*-x*.md"))


def test_repeat_daily_and_cancel_streak(sbv):
    tid = new_task(sbv, "dishwashing", id="20260929-dishwashing", due="2026-09-29", repeat="毎日")
    ids = [tid]
    for _ in range(3):
        code, r = sbv.json("task", "cancel", ids[-1], "--reason", "疲れた", "--by", "本人")
        assert code == 0 and r["next"]["created"]
        ids.append(r["next"]["id"])
    assert ids == ["20260929-dishwashing", "20260930-dishwashing", "20261001-dishwashing", "20261002-dishwashing"]
    last = sbv.read("40_tasks/active/20261002-dishwashing.md")
    assert "連続取消: 3" in last and "期限: 2026-10-02 23:59" in last and "前回 20261001-dishwashing を取消" in last
    assert sbv.run("task", "cancel", ids[-1], "--reason", "x", "--by", "本人") == 1  # 4回目は取り消せない
    assert "3回続けて" in sbv.err
    code, r = sbv.json("task", "done", ids[-1], "--by", "本人")
    assert r["next"]["連続取消"] == 0
    assert "連続取消: 0" in sbv.read("40_tasks/active/20261003-dishwashing.md")
    # 前回を戻してもう一度終えても、次の回は二重に作らない
    sbv.run("task", "reopen", ids[-1], "--by", "本人")
    code, r = sbv.json("task", "done", ids[-1], "--by", "本人")
    assert r["next"]["created"] is False


def test_repeat_weekly_monthly(sbv):
    w = new_task(sbv, "trash", due="2026-09-29", repeat="毎週金")  # 2026-09-29 は火曜
    code, r = sbv.json("task", "done", w, "--by", "c")
    assert r["next"]["id"] == "20261002-trash"
    m = new_task(sbv, "rent", id="20260131-rent", due="2026-01-31", repeat="毎月31日")
    code, r = sbv.json("task", "done", m, "--by", "c")
    assert r["next"]["id"] == "20260228-rent"
    ev = new_task(sbv, "piano", type="予定", start="2026-09-29 19:00", end="2026-09-29 20:00", repeat="毎日")
    code, r = sbv.json("task", "done", ev, "--by", "c")
    nxt = sbv.read(f"40_tasks/active/{r['next']['id']}.md")
    assert "開始: 2026-09-30 19:00" in nxt and "終了: 2026-09-30 20:00" in nxt


def test_tidy_moves_past_events_unchanged(sbv):
    past = new_task(sbv, "old event", type="予定", start="2026-09-20 10:00")
    future = new_task(sbv, "new event", type="予定", start="2026-10-20 10:00")
    before = sbv.read(f"40_tasks/active/{past}.md")
    assert sbv.run("task", "tidy", "--by", "sb/tidy", "--dry-run") == 0
    assert (sbv.vault / f"40_tasks/active/{past}.md").exists()
    code, r = sbv.json("task", "tidy", "--by", "sb/tidy")
    assert r["moved"] == [f"40_tasks/active/{past}.md"]
    assert sbv.read(f"40_tasks/archive/2026/09/{past}.md") == before
    assert (sbv.vault / f"40_tasks/active/{future}.md").exists()


def test_tidy_repeating_event_makes_next_from_today(sbv):
    # 今日は 2026-09-29。毎日の予定が 9/25 から止まっていても、次の回は今日の分を1つだけ作る
    ev = new_task(sbv, "morning", type="予定", id="20260925-morning", start="2026-09-25 07:00", repeat="毎日")
    code, r = sbv.json("task", "tidy", "--by", "sb/tidy")
    assert code == 0 and r["next"][0]["id"] == "20260929-morning" and r["next"][0]["created"]
    nxt = sbv.read("40_tasks/active/20260929-morning.md")
    assert "開始: 2026-09-29 07:00" in nxt and "連続取消: 0" in nxt
    assert (sbv.vault / f"40_tasks/archive/2026/09/{ev}.md").exists()
    code, r = sbv.json("task", "tidy", "--by", "sb/tidy")
    assert r["moved"] == []  # 今日の回はまだ片付けない


def test_project_lifecycle(sbv):
    assert sbv.run("project", "new", "庭づくり", "--purpose", "庭を作る", "--repo", "src/garden-planner", "--by", "本人") == 0
    memo = sbv.read("30_projects/active/庭づくり/メモ.md")
    assert "関連repo: [src/garden-planner]" in memo and "状態: 進行中" in memo and "## 目的\n庭を作る" in memo
    assert sbv.run("project", "new", "庭づくり", "--purpose", "x", "--by", "本人") == 1
    assert sbv.run("project", "new", "a/b", "--purpose", "x", "--by", "本人") == 1
    assert sbv.run("project", "status", "庭づくり", "--stdin", "--by", "c", stdin="苗を植えた\n### 次\n水やりの当番") == 0
    assert sbv.run("project", "log", "庭づくり", "--text", "苗の植え付け完了", "--by", "c") == 0
    memo = sbv.read("30_projects/active/庭づくり/メモ.md")
    assert "## 今の状態\n苗を植えた\n### 次\n水やりの当番" in memo and "- 2026-09-29 苗の植え付け完了" in memo
    doc = sbv.ws / "work" / "plan.md"
    doc.parent.mkdir()
    doc.write_text("# 計画\n中身\n", encoding="utf-8")
    assert sbv.run("project", "attach", "庭づくり", "--file", doc, "--by", "c") == 0
    att = sbv.read("30_projects/active/庭づくり/資料/plan.md")
    assert "種類: project" in att and "資料: true" in att and "案件: 庭づくり" in att
    png = sbv.ws / "work" / "x.png"
    png.write_bytes(b"x")
    assert sbv.run("project", "attach", "庭づくり", "--file", png, "--by", "c") == 1
    tid = new_task(sbv, "watering", project="庭づくり")
    assert sbv.run("project", "show", "庭づくり") == 0 and tid in sbv.out
    assert sbv.run("project", "close", "庭づくり", "--result", "完了", "--text", "終わり", "--by", "本人") == 1
    sbv.run("task", "done", tid, "--by", "本人")
    assert sbv.run("project", "close", "庭づくり", "--result", "完了", "--text", "庭が完成", "--by", "本人") == 0
    memo = sbv.read("30_projects/archive/庭づくり/メモ.md")
    assert "状態: 完了" in memo and "終了: 2026-09-29" in memo and "**完了（2026-09-29）**: 庭が完成" in memo
    assert (sbv.vault / "30_projects/archive/庭づくり/資料/plan.md").exists()
    # archive は読み取り専用
    assert sbv.run("project", "log", "庭づくり", "--text", "x", "--by", "c") == 4
    assert sbv.run("project", "status", "庭づくり", "--text", "x", "--by", "c") == 4
    assert sbv.run("task", "new", "--title", "x", "--owner", "本人", "--project", "庭づくり", "--by", "c") == 3
    code, r = sbv.json("project", "list", "--all")
    assert r["projects"] == [{"name": "庭づくり", "where": "archive", "状態": "完了",
                              "path": "30_projects/archive/庭づくり/メモ.md"}]
    assert sbv.run("project", "list", "--all") == 0 and "庭づくり [完了]" in sbv.out
    assert sbv.run("project", "reopen", "庭づくり", "--by", "本人") == 0
    memo = sbv.read("30_projects/active/庭づくり/メモ.md")
    assert "状態: 進行中" in memo and "終了:\n" in memo and "再開" in memo
    assert sbv.run("project", "show", "無い") == 3


def test_project_refusals(sbv, tmp_path):
    sbv.run("project", "new", "p", "--purpose", "x", "--by", "c")
    out = tmp_path / "o.md"
    out.write_text("# x", encoding="utf-8")
    assert sbv.run("project", "attach", "p", "--file", out, "--by", "c") == 4
    assert sbv.run("project", "status", "p", "--text", "## 見出し", "--by", "c") == 1
    assert sbv.run("project", "log", "p", "--text", "access_token=abcdefgh12345678xyz", "--by", "c") == 4
    assert sbv.run("project", "close", "p", "--result", "完了", "--text", "sk-abcdefghijklmnopqrstuvwx", "--by", "c") == 4
    assert (sbv.vault / "30_projects/active/p/メモ.md").exists()


def test_reopen_returns_active_waiting_and_in_progress_to_open(sbv):
    assert sbv.run("task", "new", "--title", "待つ", "--owner", "本人", "--due", "2026-10-05", "--id", "20260929-wait", "--by", "c") == 0
    assert sbv.run("task", "wait", "20260929-wait", "--for", "返事", "--recheck", "2026-10-06", "--by", "c") == 0
    assert sbv.run("task", "reopen", "20260929-wait", "--by", "本人") == 0
    text = sbv.read("40_tasks/active/20260929-wait.md")
    assert "状態: open" in text and "待ち:\n" in text and "次の確認:\n" in text and "open に戻す" in text
    assert sbv.run("task", "start", "20260929-wait", "--by", "c") == 0
    assert sbv.run("task", "reopen", "20260929-wait", "--by", "本人") == 0 and "状態: open" in sbv.read("40_tasks/active/20260929-wait.md")
    assert sbv.run("task", "reopen", "20260929-wait", "--by", "本人") == 1  # もう open


def test_task_new_records_creator_and_keeps_it(sbv):
    assert sbv.run("task", "new", "--title", "made by", "--owner", "本人", "--due", "2026-10-20", "--id", "20261017-made-by", "--by", "taskizer/task-checks") == 0
    assert sbv.run("task", "note", "20261017-made-by", "--text", "経緯", "--by", "c") == 0
    _, out = sbv.json("task", "list")
    task = next(t for t in out["tasks"] if t["ID"] == "20261017-made-by")
    assert task["作った物"] == "taskizer/task-checks" and task["書いた物"] == "c"
