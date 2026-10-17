import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
import check_repo_independence as c  # noqa: E402


def test_names_other_repo_but_not_itself_or_sb(tmp_path):
    for r in ("a", "b"):
        (tmp_path / "src" / r).mkdir(parents=True)
    (tmp_path / "sb").mkdir()
    (tmp_path / "src/a/run.js").write_text('require("/Users/x/Workspace/src/b/tool.js")\nconst self = "src/a/x";\nrun("sb/bin/sb")\n')
    (tmp_path / "src/b/x.py").write_text('p = os.path.join(ws, "src", "a", "y")\n')
    (tmp_path / "src/b/tests").mkdir()
    (tmp_path / "src/b/tests/t.py").write_text('"src/a/fake"\n')
    found = c.violations(tmp_path)
    assert found == ["a\tb\tsrc/a/run.js:1", "b\ta\tsrc/b/x.py:1"]


def test_help_prints_usage_without_traceback():
    import subprocess
    script = str(Path(__file__).resolve().parents[1] / "bin" / "check_repo_independence.py")
    r = subprocess.run([sys.executable, script, "--help"], capture_output=True, text=True)
    assert r.returncode == 0 and "usage:" in r.stdout and "Traceback" not in r.stderr
