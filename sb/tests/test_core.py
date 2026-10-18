import os
from pathlib import Path

import pytest

from sb import SbError, frontmatter, guard, layers, logical_day, paths, write
from tests.conftest import MARKER


def test_paths_env_independent(monkeypatch):
    for v in ("SB_WORKSPACE", "SB_VAULT", "SB_DATA", "SB_CONFIG"):
        monkeypatch.delenv(v, raising=False)
    assert paths.workspace_root() == Path("/Users/taro/Workspace")
    assert paths.vault_root() == Path("/Users/taro/Workspace/SecondBrain")
    monkeypatch.setenv("SB_WORKSPACE", "/w")
    monkeypatch.setenv("SB_DATA", "/d")
    assert (paths.vault_root(), paths.data_root(), paths.config_root()) == (Path("/w/SecondBrain"), Path("/d"), Path("/w/config"))
    monkeypatch.setenv("SB_VAULT", "/v")
    assert paths.vault_root() == Path("/v") and paths.sb_data() == Path("/d/sb")


def test_layers_own_parser_and_helpers():
    d = layers.parse_toml(layers.LAYERS_FILE.read_text(encoding="utf-8"))
    assert d == layers.load_layers()
    assert not {"inbox", "distill", "identity"} & set(d)  # 層の中のファイル名は決めない
    k = layers.kinds()
    assert len(k) == 11 and not any("item" in v for v in k.values()) and k["movies"]["has_current"] and not k["browsing/web"]["has_current"]
    assert layers.kind_spec("podcast/saved") == {"label": "podcast/saved", "daily": True, "has_current": True}
    assert layers.log_kinds() == ["check", "audits", "schedule", "handoff"]
    assert len(d["layers"]) == 10
    for bad in ("Talk", "a//b", "/a", "a/", "../x", "a.b", ""):
        with pytest.raises(SbError):
            layers.check_name(bad, "名前")
    assert layers.match_file("50_media/songs/liked/current.md")[0] == "media_current"
    assert layers.match_file("50_media/browsing/web/current.md") is None  # 列を決めた種類は current を持たない
    assert layers.match_file("50_media/podcast/saved/current.md")[0] == "media_current"
    assert layers.match_file("50_media/podcast/2026-09-29.md")[0] == "media_daily"
    assert layers.match_file("50_media/video_liked/2026-09-29.md")[0] == "media_daily"
    assert layers.match_file("50_media/video_liked/current.md")[0] == "media_current"
    assert layers.match_file("50_media/video_liked/abc123def45.md") is None  # 1件1ファイルは無い
    assert layers.match_file("50_media/movies/notes.md") is None
    assert layers.match_file("20_identity/hobby/knitting.md")[0] == "identity"
    assert layers.match_file("20_identity/Knitting.md") is None
    assert layers.match_file("00_inbox/messages/team/2026-09-29.md")[0] == "inbox_messages"
    assert layers.match_file("00_inbox/conversations/assistant/2026-09-29.md")[0] == "inbox_conversations"
    assert layers.match_file("00_inbox/team/2026-09-29.md") is None
    assert layers.match_file("60_distilled/team/2026-09-29.md")[0] == "distilled"
    assert layers.match_file("60_distilled/team/notes.md") is None
    assert layers.match_file("90_logs/weather/2026-09-29.md") is None
    assert layers.match_file("40_tasks/active/Bad_ID.md") is None
    assert layers.match_file("30_projects/active/.x/メモ.md") is None


def test_toml_subset_parser():
    d = layers.parse_toml('# c\n[a."b/c"]\nx = "q\\"s" # c\ny = [1, "z", true]\nz = { k = [ "a" ], n = -3 }\n')
    assert d == {"a": {"b/c": {"x": 'q"s', "y": [1, "z", True], "z": {"k": ["a"], "n": -3}}}}
    with pytest.raises(SbError):
        layers.parse_toml("x = oops\n")


def test_frontmatter_roundtrip_and_sections():
    text = "---\n形式: 1\n種類: task\n関連: [a, b]\n空:\n旗: true\n---\n# t\n\n## 経緯\n- x\n"
    meta, body = frontmatter.parse(text)
    assert meta == {"形式": 1, "種類": "task", "関連": ["a", "b"], "空": "", "旗": True}
    assert frontmatter.dump(meta, body) == text
    body = frontmatter.append_to_section(body, "経緯", "- y")
    assert frontmatter.get_section(body, "経緯") == "- x\n- y"
    body = frontmatter.replace_section(body, "新", "中身")
    assert frontmatter.headings(body) == ["経緯", "新"]
    with pytest.raises(SbError):
        frontmatter.replace_section(body, "経緯", "## 混入")
    with pytest.raises(SbError):
        frontmatter.parse("---\n壊れ\n---\n")


@pytest.mark.parametrize("iso,day", [("2026-09-30T04:59:00+09:00", "2026-09-29"),
                                     ("2026-09-30T05:00:00+09:00", "2026-09-30"),
                                     ("2026-09-29T20:00:00+00:00", "2026-09-30")])
def test_logical_day_boundary(monkeypatch, iso, day):
    monkeypatch.setenv("SB_NOW", iso)
    assert str(logical_day.today()) == day


def test_canonical_due():
    assert logical_day.canonical_due("2026-09-29 23:59").isoformat() == "2026-09-30T05:00:00+09:00"
    assert logical_day.canonical_due("2026-09-29 13:00").hour == 13


def test_secret_patterns():
    assert guard.find_secret("api_key=abcd1234efgh5678ijkl")[0] == "鍵名=値"
    assert guard.find_secret("password=hunter2x")[0] == "パスワード"
    # トークンの形でない値は秘密ではない（品名・手順の文・短い値）
    assert guard.find_secret("Authorization: Sunflower") is None
    assert guard.find_secret("authorization: yes（本人の許可）") is None
    assert guard.find_secret("Authorization: Bearer") is None
    assert guard.find_secret('"api_key": "k",') is None
    assert guard.find_secret("SESSION_ID=01a2b3c4-d5e6-7890-abcd-ef1234567890") is None
    assert guard.find_secret("x\ntoken sk-abcdefghijklmnopqrstu") == ("sk- のAPIキー", 2)
    assert guard.find_secret("認証コード: 123456")
    assert guard.find_secret("password: [REDACTED]") is None
    assert guard.find_secret("password: キーチェーン") is None
    assert guard.find_secret("普通の文章 2026-09-29") is None


def test_guard_company(sbv):
    guard.check("10_daily/2026/2026-09-29.md", f"x {MARKER} y")  # 会社の言葉は vault に書ける
    with pytest.raises(SbError):
        guard.check("x/会社資料/a.md", "ok")
    guard.check("10_daily/2026/2026-09-29.md", f"old {MARKER}\nnew", old_text=f"old {MARKER}")  # 既存の行は止めない
    (sbv.ws / "config" / "company_confidential.json").write_text("{", encoding="utf-8")
    with pytest.raises(SbError) as e:
        guard.check("a.md", "ok")
    assert e.value.code == 4


def test_wrong_layer_and_unknown_place(sbv):
    text = write.new_doc("daily", "t", 論理日="2026-09-29")
    with write.Tx("media") as tx:
        tx.put("10_daily/2026/2026-09-29.md", text)
        with pytest.raises(SbError) as e:
            tx.commit()
    assert e.value.code == 4
    with write.Tx("daily") as tx:
        tx.put("99_other/x.md", text)
        with pytest.raises(SbError) as e:
            tx.commit()
    assert e.value.code == 4


def test_validation_before_replace(sbv):
    with write.Tx("daily") as tx:
        tx.put("10_daily/2026/2026-09-29.md", "---\n形式: 1\n種類: daily\n---\n# x\n")
        with pytest.raises(SbError) as e:
            tx.commit()
    assert e.value.code == 1 and not (sbv.vault / "10_daily").exists()


def test_lock_contention(sbv):
    fd = write.acquire("vault:NOW.md")
    try:
        assert sbv.run("views", "refresh", "--by", "t") == 2
    finally:
        write.release(fd)
    assert sbv.run("views", "refresh", "--by", "t") == 0


def test_crash_safety(sbv, monkeypatch):
    assert sbv.run("log", "handoff", "--text", "一回目", "--by", "claude") == 0
    before = sbv.read("90_logs/handoff.md")
    # 前回の書きかけの一時ファイルが残っていても壊れない・検査に出ない
    (sbv.vault / "90_logs" / ".handoff.md.sb-tmp-1-abc").write_text("garbage", encoding="utf-8")

    def boom(*a, **k):
        raise OSError("停電")
    with monkeypatch.context() as m:
        m.setattr(os, "replace", boom)
        assert sbv.run("log", "handoff", "--text", "二回目", "--by", "claude") == 5
    assert sbv.read("90_logs/handoff.md") == before
    leftovers = [p.name for p in (sbv.vault / "90_logs").iterdir()]
    assert leftovers.count(".handoff.md.sb-tmp-1-abc") == 1 and len(leftovers) == 2
    assert sbv.run("log", "handoff", "--text", "三回目", "--by", "claude", "--json") == 0
    assert "三回目" in sbv.read("90_logs/handoff.md")


def test_by_required_and_version_and_dry_run(sbv):
    assert sbv.run("views", "refresh") == 1
    assert sbv.run("version") == 0 and "1.0.0" in sbv.out
    assert sbv.run("views", "refresh", "--by", "t", "--dry-run") == 0
    assert "(dry-run) write: NOW.md" in sbv.out and not (sbv.vault / "NOW.md").exists()


def test_file_input_outside_workspace(sbv, tmp_path):
    outside = tmp_path / "out.txt"
    outside.write_text("x", encoding="utf-8")
    assert sbv.run("log", "schedule", "--task", "t", "--file", outside, "--by", "t") == 4
    inside = sbv.ws / "in.txt"
    inside.write_text("結果 ok", encoding="utf-8")
    assert sbv.run("log", "schedule", "--task", "t", "--file", inside, "--by", "t") == 0
