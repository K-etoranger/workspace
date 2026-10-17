"""頭書きは YAML として読める形で書く（sb の読み方でも同じ値に戻る）。"""
import yaml

from sb import frontmatter


def _yaml(text):
    return yaml.safe_load(text.split("\n---\n", 1)[0][4:])


def test_round_trip_tricky_values():
    for v in ["前回報告: /Users/x", "- dash", "#hash", " sp", "end:", "x #y", "[x]", 'a "b" \\ c', "普通", "2026-10-02 23:59"]:
        text = frontmatter.dump({"k": v, "l": ["src/a", "x: y"], "n": 3}, "# t\n")
        meta, _ = frontmatter.parse(text)
        assert meta == {"k": v, "l": ["src/a", "x: y"], "n": 3}
        assert _yaml(text) == {"k": v, "l": ["src/a", "x: y"], "n": 3}


def test_new_task_with_colon_is_yaml(sbv):
    assert sbv.run("task", "new", "--title", "件名: コロンあり", "--owner", "本人", "--source", "出典: メモ", "--id", "20260929-colon", "--by", "c") == 0
    text = sbv.read("40_tasks/active/20260929-colon.md")
    assert _yaml(text)["件名"] == "件名: コロンあり" and _yaml(text)["出典"] == "出典: メモ"


def test_check_fix_rewrites_old_form_without_touching(sbv):
    assert sbv.run("task", "new", "--title", "t", "--owner", "本人", "--id", "20260929-old", "--by", "c") == 0
    rel = "40_tasks/active/20260929-old.md"
    path = sbv.vault / rel
    old = path.read_text().replace("出典:", "出典: 前回: 古い書き方", 1)
    path.write_text(old)
    assert sbv.run("check", "--fix", "--by", "c") == 0
    new = path.read_text()
    assert _yaml(new)["出典"] == "前回: 古い書き方"
    assert [ln for ln in new.splitlines() if ln.startswith(("更新:", "書いた物:"))] == [ln for ln in old.splitlines() if ln.startswith(("更新:", "書いた物:"))]
