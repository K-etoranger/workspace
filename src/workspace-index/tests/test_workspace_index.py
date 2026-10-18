import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import workspace_index as wi  # noqa: E402

TEMPLATE = """# {name}

{name} をする。

## 使い方
- x

## data に書く場所
{writes}

## data から読む場所
- なし

## SecondBrain に書く層
- なし

## SecondBrain から読む層
- なし

## 使うモデル
{models}

## 定時処理
- なし

## 試験
- x

## してはいけないこと
- なし
"""


def make(ws: Path, name: str, writes="- なし", models="- なし"):
    p = ws / "src" / name
    p.mkdir(parents=True)
    (p / "README.md").write_text(TEMPLATE.format(name=name, writes=writes, models=models), encoding="utf-8")


def test_first_line_skips_frontmatter_and_needs_blank_line():
    assert wi.first_line("---\n種類: view\n---\n# SB\n\n層の一覧。\n") == "層の一覧。"
    assert wi.first_line("# x\nすぐ本文\n") is None
    assert wi.first_line("# x\n\n| 表 |\n") is None


def test_data_writers_one_two_and_none(tmp_path):
    for d in ("data/a", "data/shared/x", "data/shared/y", "data/orphan", "models/m1"):
        (tmp_path / d).mkdir(parents=True)
    make(tmp_path, "one", writes="- `data/a`（この repo だけ）", models="- `models/m1`")
    make(tmp_path, "two", writes="- data/shared/x\n- data/a")
    make(tmp_path, "three", writes="- data/shared/y")
    files, warnings = wi.build(tmp_path)
    assert "data の書き手が2つ以上: data/a（one・two）" in warnings
    assert "data の書き手が無い: data/orphan" in warnings
    assert not any("data/shared" in w for w in warnings)          # 深い宣言まで下りて書き手が1つずつ
    assert "| `data/shared/x` | `two` |" in files["data/README.md"]
    assert "| `m1` | `one` |" in files["models/README.md"]
    assert not any("欄" in w for w in warnings)                    # 「なし」は空欄ではない


def test_refresh_writes_only_changes(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    monkeypatch.setenv("WORKSPACE", str(tmp_path))
    out = tmp_path / "out"
    assert wi.main(["refresh", "--out", str(out)]) == 0
    first = (out / "src/README.md").stat().st_mtime_ns
    assert wi.main(["refresh", "--out", str(out)]) == 0
    assert (out / "src/README.md").stat().st_mtime_ns == first
    assert wi.main(["refresh", "--nope"]) == 1


def test_src_lists_agent_jobs_and_data_has_no_cloud_column(tmp_path):
    (tmp_path / "data" / "a").mkdir(parents=True)
    make(tmp_path, "one", writes="- data/a")
    (tmp_path / "src" / "one" / "scheduled" / "daily-job").mkdir(parents=True)
    (tmp_path / "src" / "one" / "scheduled" / "daily-job" / "SKILL.md").write_text('---\nschedule: "05 8,17 * * *"\n---\n', encoding="utf-8")
    (tmp_path / "src" / "one" / "scheduled" / "odd-job").mkdir(parents=True)
    (tmp_path / "src" / "one" / "scheduled" / "odd-job" / "SKILL.md").write_text("x", encoding="utf-8")
    files, _ = wi.build(tmp_path)
    assert "`daily-job` 08:05・17:05（エージェント）" in files["src/README.md"]
    assert "`odd-job` 時刻なし（エージェント）" in files["src/README.md"]
    assert "クラウド" not in files["data/README.md"]


def test_data_readme_is_not_counted_as_data(tmp_path):
    (tmp_path / "data" / "a").mkdir(parents=True)
    (tmp_path / "data" / "README.md").write_text("# data\n", encoding="utf-8")
    make(tmp_path, "one", writes="- data/a")
    files, warnings = wi.build(tmp_path)
    assert "data/README.md" not in files["data/README.md"].split("| フォルダ")[1]
    assert not any("data/README.md" in w for w in warnings)
