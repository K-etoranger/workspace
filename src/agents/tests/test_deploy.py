import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(home, *args):
    return subprocess.run([sys.executable, str(ROOT / "deploy.py"), *args], capture_output=True, text=True,
                          env=dict(os.environ, AGENTS_DEPLOY_HOME=str(home)))


def put(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def workspace(home, cron="5 4 * * *"):
    """配る物を repo に分けて持つ小さな Workspace と、Claude アプリの定時処理の登録。"""
    src = home / "Workspace/src"
    put(src / "setup/rules/AGENTS.md", "rules\n")
    put(src / "setup/rules/claude-home.md", "@rules\n")
    put(src / "setup/settings/claude.json", json.dumps({"permissions": {"deny": ["Edit(//x/.codex/auth.json)"]}}))
    put(src / "setup/hooks/hooks.json", json.dumps({"PreToolUse": [{"matcher": "Bash", "command": ["/usr/bin/python3", "hooks/g.py"]}]}))
    put(src / "recall/hooks/hooks.json", json.dumps({"UserPromptSubmit": [{"command": ["/usr/bin/python3", "hooks/r.py"], "timeout": 60}]}))
    put(src / "owner/skills/tool/SKILL.md", "---\nname: tool\n---\n")
    put(src / "owner/skills/tool/scripts/a.py", "x\n")
    put(src / "owner/scheduled/job/SKILL.md", '---\nname: job\nschedule: "5 4 * * *"\n---\n# job\n')
    put(home / "Library/Application Support/Claude/claude-code-sessions/a/b/scheduled-tasks.json",
        json.dumps({"scheduledTasks": [{"id": "job", "cronExpression": cron, "enabled": True}]}))
    return src


def test_check_apply_check_collects_from_every_repo(tmp_path):
    src = workspace(tmp_path)
    locked = tmp_path / "Workspace/src/owner/gate.py"
    put(locked, "x")
    subprocess.run(["chflags", "uchg", str(locked)], check=True)
    try:
        assert run(tmp_path).returncode == 1                      # 配置先が空なら差分あり
        assert run(tmp_path, "--apply").returncode == 0
        r = run(tmp_path)
        assert r.returncode == 0 and "drift=0 stale=0 orphan=0 schedule=0" in r.stdout, r.stdout
    finally:
        subprocess.run(["chflags", "nouchg", str(locked)], check=True)
    assert (tmp_path / ".codex/AGENTS.md").read_text() == "rules\n"
    assert (tmp_path / ".claude/CLAUDE.md").read_text() == "@rules\n"
    for root in (".claude/skills", ".codex/skills"):
        assert (tmp_path / root / "tool/scripts/a.py").is_file()
    assert (tmp_path / ".claude/scheduled-tasks/job/SKILL.md").read_bytes() == (src / "owner/scheduled/job/SKILL.md").read_bytes()
    s = json.loads((tmp_path / ".claude/settings.json").read_text())
    assert s["hooks"]["PreToolUse"] == [{"matcher": "Bash", "hooks": [{"type": "command", "command": f"/usr/bin/python3 {src}/setup/hooks/g.py"}]}]
    assert s["hooks"]["UserPromptSubmit"] == [{"hooks": [{"type": "command", "command": f"/usr/bin/python3 {src}/recall/hooks/r.py", "timeout": 60}]}]
    assert f"Edit(/{locked})" in s["permissions"]["deny"] and "Edit(//x/.codex/auth.json)" in s["permissions"]["deny"]


def test_same_name_in_two_repos_stops(tmp_path):
    src = workspace(tmp_path)
    put(src / "other/skills/tool/SKILL.md", "y")
    r = run(tmp_path)
    assert r.returncode != 0 and "同じ名前が2つある: tool" in r.stderr
    shutil.rmtree(src / "other")
    put(src / "other/rules/AGENTS.md", "y")
    r = run(tmp_path)
    assert r.returncode != 0 and "*/rules/AGENTS.md が全 repo で1つではない" in r.stderr
    shutil.rmtree(src / "other")
    put(src / "setup/settings/claude.json", json.dumps({"hooks": {}}))
    r = run(tmp_path)
    assert r.returncode != 0 and "hooks がある" in r.stderr


def test_schedule_is_compared_with_the_app(tmp_path):
    workspace(tmp_path, cron="05 04 * * *")                      # 0 の付け方の違いは同じ時刻
    run(tmp_path, "--apply")
    assert "schedule=0" in run(tmp_path).stdout
    workspace(tmp_path, cron="0 6 * * *")
    r = run(tmp_path)
    assert r.returncode == 1 and "schedule\tjob\t正本=5 4 * * *\t登録=0 6 * * *" in r.stdout
    put(tmp_path / "Library/Application Support/Claude/claude-code-sessions/a/b/scheduled-tasks.json", json.dumps({"scheduledTasks": [
        {"id": "job", "cronExpression": "5 4 * * *", "enabled": False}, {"id": "gone", "cronExpression": "0 1 * * *"}]}))
    r = run(tmp_path).stdout
    assert "schedule\tjob\t正本=5 4 * * *\t登録=5 4 * * *（停止中）" in r and "schedule\tgone\t登録だけあり、原本が無い" in r
    put(tmp_path / "Workspace/src/owner/scheduled/job/SKILL.md", "---\nname: job\n---\n# schedule: は本文の頭にだけ書く\n")
    assert "schedule\tjob\t本文に schedule: が無い" in run(tmp_path).stdout
    shutil.rmtree(tmp_path / "Library")
    assert "schedule\t登録が読めない" in run(tmp_path).stdout   # 読めないことを「食い違い無し」にしない


def test_orphan_is_listed_and_moved_only_by_archive(tmp_path):
    src = workspace(tmp_path)
    run(tmp_path, "--apply")
    (src / "owner/skills/tool/scripts/a.py").unlink()
    r = run(tmp_path)
    assert f"stale\t{tmp_path}/.claude/skills/tool/scripts/a.py" in r.stdout
    run(tmp_path, "--apply")
    assert not (tmp_path / ".claude/skills/tool/scripts/a.py").exists()
    shutil.rmtree(src / "owner/skills/tool")
    put(tmp_path / ".claude/skills/app-own/SKILL.md", "アプリの物")   # 配っていない物には触れない
    r = run(tmp_path)
    assert r.returncode == 1 and f"orphan\t{tmp_path}/.claude/skills/tool" in r.stdout and "app-own" not in r.stdout
    run(tmp_path, "--apply")                                      # --apply では移さず、次の確認でも出る
    assert (tmp_path / ".claude/skills/tool").is_dir() and "orphan=2" in run(tmp_path).stdout
    assert run(tmp_path, "--archive").returncode == 0
    assert not (tmp_path / ".claude/skills/tool").exists() and not (tmp_path / ".codex/skills/tool").exists()
    assert list((tmp_path / "Documents").glob("_archive_*/agents/.claude/skills/tool/SKILL.md"))
    assert "orphan=0" in run(tmp_path).stdout
