import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(home, *args):
    return subprocess.run([sys.executable, str(ROOT / "deploy.py"), *args], capture_output=True, text=True,
                          env=dict(os.environ, AGENTS_DEPLOY_HOME=str(home)))


def test_settings_is_deployed_and_check_is_clean_after_apply(tmp_path):
    locked = tmp_path / "Workspace/src/some-repo/gate.py"
    skipped = tmp_path / "Workspace/src/some-repo/node_modules/x.js"
    plain = tmp_path / "Workspace/config/plain.json"
    for f in (locked, skipped, plain):
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x", encoding="utf-8")
    subprocess.run(["chflags", "uchg", str(locked), str(skipped)], check=True)
    try:
        assert run(tmp_path).returncode == 1                      # 配置先が空なら差分あり
        assert run(tmp_path, "--apply").returncode == 0
        r = run(tmp_path)
        assert r.returncode == 0 and "drift=0 stale=0" in r.stdout
        deployed = json.loads((tmp_path / ".claude/settings.json").read_text(encoding="utf-8"))
        deny = deployed["permissions"]["deny"]
        assert f"Edit(/{locked})" in deny                         # uchg の付いたファイルから作る
        assert not any("node_modules" in d or "plain.json" in d for d in deny)
        assert any(".ssh/**" in d for d in deny)         # Workspace の外は原本のまま
        subprocess.run(["chflags", "nouchg", str(locked)], check=True)
        assert run(tmp_path).returncode == 1                      # 印を外すと差分になる
    finally:
        subprocess.run(["chflags", "nouchg", str(locked), str(skipped)], check=True)


def test_retired_skill_is_listed_then_removed_only_on_apply(tmp_path):
    for root in (".claude/skills", ".codex/skills"):
        ref = tmp_path / root / "old-secondbrain-skill/references/task-policy.md"
        ref.parent.mkdir(parents=True)
        ref.write_text("old", encoding="utf-8")
    first = run(tmp_path)
    assert first.returncode == 1 and "stale\t" + str(ref) in first.stdout
    assert ref.exists()                                        # 確認だけでは消さない
    assert run(tmp_path, "--apply").returncode == 0
    for root in (".claude/skills", ".codex/skills"):
        assert not (tmp_path / root / "old-secondbrain-skill").exists()
        for name in ("write-workspace-readme",):
            assert (tmp_path / root / name / "SKILL.md").is_file()
    assert "drift=0 stale=0" in run(tmp_path).stdout


def test_other_repos_scheduled_bodies_are_deployed_and_duplicates_stop(tmp_path):
    body = tmp_path / "Workspace/src/other-repo/scheduled/other-job/SKILL.md"
    body.parent.mkdir(parents=True)
    body.write_text("---\nname: other-job\n---\n# x\n", encoding="utf-8")
    assert run(tmp_path, "--apply").returncode == 0
    assert (tmp_path / ".claude/scheduled-tasks/other-job/SKILL.md").read_text(encoding="utf-8") == body.read_text(encoding="utf-8")
    dup = tmp_path / "Workspace/src/third-repo/scheduled/other-job/SKILL.md"
    dup.parent.mkdir(parents=True)
    dup.write_text("y", encoding="utf-8")
    r = run(tmp_path)
    assert r.returncode != 0 and "同じ名前の定時処理が2つある: other-job" in (r.stdout + r.stderr)
