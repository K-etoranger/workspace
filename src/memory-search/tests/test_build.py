import json
import sqlite3
import struct

import pytest
import sqlite_vec

from conftest import write
from memory_search import build as b
from memory_search.chunk import chunk_file


def fake_embed(calls):
    def embed(texts):
        calls.extend(texts)
        return [[float(len(t) % 7 + 1)] + [0.0] * (b.DIM - 1) for t in texts]
    return embed


@pytest.fixture
def vault(workspace):
    sb = workspace / "SecondBrain"
    write(sb / "20_identity/profile.md", "---\n形式: 1\n---\n# プロフィール\n\n## 今の状態\n- 読書会に毎月出ている。\n- 隣人は鈴木さん。\n")
    write(sb / "10_daily/2026/2026-10-03.md", "---\n論理日: 2026-10-03\n---\n# 2026-10-03\n\n## 今日の要約\n- 田中さんに相談した。\n")
    write(sb / "00_inbox/conversations/claude/2026-10-04.md",
          "---\n論理日: 2026-10-04\n---\n# claude 2026-10-04\n\n"
          "## 08:38 aaa\n<!-- id: x -->\n### 山田\n<scheduled-task name=\"distill\">指示文</scheduled-task>\n\n### Claude\n実行した。\n\n"
          "## 08:50 ccc\n### 山田\n<heartbeat>\n  <automation_id>monitor</automation_id>\n</heartbeat>\n\n### Codex\n見た。\n\n"
          "## 09:00 bbb\n<!-- id: y -->\n### 山田\n図書カードを作りたい。\n\n### Claude\nタスクにしました。\n")
    write(sb / "00_inbox/messages/talk/2026-10-03.md",
          "---\n論理日: 2026-10-03\n---\n# talk 2026-10-03\n\n## 16:55 鈴木 — 鈴木 → other\n<!-- id: 1 -->\n庭に水をやった\n\n"
          "## 16:56 鈴木 — 鈴木 → other\n<!-- id: 2 -->\n肥料どうする\n\n## 21:14 田中 — 田中 → other\n<!-- id: 3 -->\n5/20 植えよう\n")
    write(sb / "50_media/songs/history/2026-10-03.md", "# songs\n\n| 時刻 | 曲 |\n|---|---|\n| 10:00 | Song A |\n")
    write(sb / "40_tasks/archive/2026/09/x.md", "---\n件名: 棚を組み立てる\n状態: done\n作成: 2026-09-12T10:00+09:00\n---\n# 棚を組み立てる\n\n## 内容\n入れた。\n")
    write(sb / "90_logs/handoff.md", "# handoff\n\n- 入れない\n")
    write(workspace / "company/案件/メモ.md", "# 案件\n\n## 今\n- 会社の具体値\n")
    write(workspace / "company/.system_recovery/x.md", "# 退避\n\n- 入れない\n")
    write(workspace / "company/repo/node_modules/pkg/README.md", "# pkg\n\n- 入れない\n")
    for i in range(10):
        write(sb / f"60_distilled/talk/2026-09-{i + 10:02d}.md", f"# line\n\n## 分かったこと\n- 事実 {i}\n")
    return sb


def test_chunks_follow_layer_rules(vault):
    identity, _ = chunk_file(vault / "20_identity/profile.md")
    assert [c.text for c in identity] == ["- 読書会に毎月出ている。", "- 隣人は鈴木さん。"]  # 箇条1行ずつ
    assert identity[0].line_start == identity[0].line_end == 7
    assert identity[0].date == "" and identity[0].context() == "20_identity > プロフィール > 今の状態"

    conv, _ = chunk_file(vault / "00_inbox/conversations/claude/2026-10-04.md")
    assert [(c.speaker, c.text, c.date) for c in conv] == [
        ("山田", "図書カードを作りたい。", "2026-10-04 09:00"), ("Claude", "タスクにしました。", "2026-10-04 09:00")]  # 定時処理の会話は外す

    msgs, _ = chunk_file(vault / "00_inbox/messages/talk/2026-10-03.md")
    assert [c.speaker for c in msgs] == ["鈴木", "田中"]  # 続いた同じ相手の通はまとめる
    assert "庭に水をやった" in msgs[0].text and "肥料どうする" in msgs[0].text and "<!--" not in msgs[0].text

    task, _ = chunk_file(vault / "40_tasks/archive/2026/09/x.md")
    assert task[0].status == "archive" and task[0].title == "棚を組み立てる（done）" and task[0].date == "2026-09-12"
    assert (task[0].heading, task[0].text, task[0].line_start, task[0].line_end) == ("頭書き", "件名: 棚を組み立てる\n状態: done", 2, 3)
    assert task[1].text == "入れた。"  # 頭書きの「作成」など仕組みの欄は入れない

    company, _ = chunk_file(vault.parent / "company/案件/メモ.md")
    assert [(c.layer, c.status, c.path, c.heading) for c in company] == [("company", "current", "company/案件/メモ.md", "今")]

    media, _ = chunk_file(vault / "50_media/songs/history/2026-10-03.md")
    assert media and not any(c.embed for c in media)


def test_long_paragraph_is_split_with_overlap():
    from memory_search.chunk import MAX_CHARS, OVERLAP, pieces
    out = pieces([[(0, "あ" * 2500)]], 0)
    assert [len(t) for _, _, t in out] == [MAX_CHARS, MAX_CHARS, 2500 - 2 * (MAX_CHARS - OVERLAP)]
    assert {(a, b) for a, b, _ in out} == {(0, 0)}


def test_long_table_pieces_keep_their_own_lines(workspace):
    rows = "".join(f"| 2026-10-0{i % 9 + 1} | 曲{i:03d} {'x' * 40} |\n" for i in range(100))
    path = write(workspace / "SecondBrain/50_media/songs/history/2026-10-03.md", "# songs\n\n| 時刻 | 曲 |\n|---|---|\n" + rows)
    lines = path.read_text().split("\n")
    got, _ = chunk_file(path)
    assert len(got) > 3
    for c in got:  # どの塊も、指す行の範囲の中身だけでできている
        assert all(line in "\n".join(lines[c.line_start - 1 : c.line_end]) for line in c.text.split("\n"))
    assert got[-1].line_end == len(lines) - 1


def test_lines_count_only_newlines_and_fences_close_properly(workspace):
    path = write(workspace / "SecondBrain/30_projects/active/x/メモ.md",
                 "# x\n\n## A\n- 行\u2028の中\n\n```sh\n# コメント\n```)\n\n```\n\n## B\n- 後ろ\n")
    got, _ = chunk_file(path)
    assert [(c.heading, c.line_start) for c in got if "後ろ" in c.text] == [("B", 13)]
    assert [c.line_start for c in got if "行" in c.text] == [4]


def test_machine_turns_are_skipped(workspace):
    path = write(workspace / "SecondBrain/00_inbox/conversations/claude/2026-10-02.md",
                 "# claude\n\n## 10:00 a\n### 山田\n<task-notification>\n終わった\n</task-notification>\n\n"
                 "### 山田\nStop hook feedback: x\n\n### 山田\n本物の発言\n```\n## 中の見出し\n```\n")
    got, _ = chunk_file(path)
    assert [(c.speaker, c.line_start) for c in got] == [("山田", 13)]
    assert "## 中の見出し" not in got[0].text  # 記録の本文の見出しは \\# に逃がしてあるはずなので、行頭の ## は区切り


def test_scheduled_session_is_skipped_across_split_headings(workspace):
    path = write(workspace / "SecondBrain/00_inbox/conversations/claude/2026-08-20.md",
                 "# claude\n\n## 02:00 cccc3333\n### 山田\n<scheduled-task name=\"x\">\n\n### Claude\n定時の返事\n\n"
                 "## 02:10 dddd4444\n### 山田\n本物の発言\n\n## 02:12 dddd4444\n### 山田\n<heartbeat><automation_id>x</automation_id>\n\n### Codex\n見回りの返事\n\n"
                 "## 02:15 cccc3333\n### 山田\n<task-notification>\n終わった\n</task-notification>\n\n### Claude\n定時の完了報告\n\n"
                 "### 山田\n今日は止めて\n")
    got, _ = chunk_file(path)
    assert [c.text for c in got] == ["本物の発言", "今日は止めて"]  # 定時処理の続きの見出しでも返事は外し、本人の発言は残す
    nxt = write(workspace / "SecondBrain/00_inbox/conversations/claude/2026-08-21.md",
                "# claude\n\n## 05:00 cccc3333\n### Claude\n翌日の続きの報告\n")
    shared: dict[str, bool] = {}
    chunk_file(path, shared)
    assert chunk_file(nxt, shared)[0] == []  # 日をまたいだ続きも外す


def test_work_sessions_are_skipped(workspace, monkeypatch):
    from memory_search import chunk
    monkeypatch.setattr(chunk, "WORK_SESSIONS", {"bbbb1111"})
    path = write(workspace / "SecondBrain/00_inbox/conversations/claude/2026-10-04.md",
                 "# claude\n\n## 10:00 aaaa2222\n### 山田\n苗の植え替え\n\n## 11:00 bbbb1111\n### 山田\n問題集を作って\n\n### Claude\n問題集の苗\n\n"
                 "## 12:00 aaaa2222\n### 山田\n続き\n")
    got, _ = chunk_file(path)
    assert [c.text for c in got] == ["苗の植え替え", "問題集を作って", "続き"]  # 作業の会話は本人の発言だけを残す
    path.write_text("# claude\n\n### 山田\n見出しの無い発言\n", encoding="utf-8")
    assert [c.text for c in chunk_file(path)[0]] == ["見出しの無い発言"]  # 見出しが空でも止まらない


def test_fts_tokens_bigram():
    assert b.fts_tokens("読書した Model 7") == ["読書", "書し", "した", "model", "7"]
    assert b.fts_tokens("ｐｌａｎｔｓ") == ["plants"]


def test_build_writes_index_manifest_and_reuses_cache(vault, workspace):
    out = workspace / "out"
    calls: list[str] = []
    state = b.build(out, embed=fake_embed(calls))
    assert state["status"] == "ok" and state["embedded_texts"] == len(calls) > 0
    assert all(t.startswith("passage: ") for t in calls)
    assert not any("handoff" in t or "Song A" in t for t in calls)  # 90_logs は入れない・50_media は埋め込まない
    assert any("会社の具体値" in t for t in calls) and not any("入れない" in t for t in calls)  # company は入れる。「.」の付く置き場・node_modules は入れない

    db = sqlite3.connect(out / "index.sqlite")
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    hit = db.execute("SELECT c.path, c.line_start FROM chunks_fts f JOIN chunks c ON c.id=f.rowid WHERE chunks_fts MATCH ?",
                     ('"読書"',)).fetchall()
    assert hit == [("SecondBrain/20_identity/profile.md", 7)]
    assert db.execute("SELECT count(*) FROM chunk_vectors").fetchone()[0] == state["embedded_chunks"]
    assert db.execute("SELECT count(*) FROM chunks WHERE layer='50_media' AND embedded=0").fetchone()[0] >= 1
    vec = struct.pack(f"{b.DIM}f", *([1.0] + [0.0] * (b.DIM - 1)))
    assert db.execute("SELECT count(*) FROM chunk_vectors WHERE embedding MATCH ? AND k=3", (vec,)).fetchone()[0] == 3

    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["embedding"]["model"] == b.MODEL and manifest["embedding"]["query_prefix"] == "query: "
    assert manifest["fts"]["rule"].startswith("bigram-v1")

    again: list[str] = []
    b.build(out, embed=fake_embed(again))
    assert again == []  # 変わっていない塊は埋め込み直さない

    write(vault / "20_identity/profile.md", "# プロフィール\n\n- 書き換えた事実\n")
    state = b.build(out, embed=fake_embed([]))
    cache = sqlite3.connect(out / "embeddings.sqlite")
    assert cache.execute("SELECT count(*) FROM vectors").fetchone()[0] == state["embedded_texts"]  # 使わなくなった埋め込みは消す
    assert not list(out.glob(".*.tmp"))


def test_failed_embedding_keeps_previous_index(vault, workspace):
    out = workspace / "out"
    b.build(out, embed=fake_embed([]))
    before = (out / "index.sqlite").read_bytes()
    write(vault / "20_identity/profile.md", "# プロフィール\n\n- 新しい事実\n")

    def broken(texts):
        raise OSError("down")

    with pytest.raises(OSError):
        b.build(out, embed=broken)
    assert (out / "index.sqlite").read_bytes() == before
