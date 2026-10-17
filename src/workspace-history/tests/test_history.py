"""workspace-history の試験。一時フォルダだけを使う。"""
from __future__ import annotations

import json
import os
import plistlib
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(argv, **env):
    return subprocess.run(argv, capture_output=True, text=True, env={**os.environ, **env})


# ---------------------------------------------------------------- history

def git(d, *a):
    return subprocess.run(["git", "-C", str(d), *a], capture_output=True, text=True, check=True).stdout


def test_history_commits_each_repo_once_and_skips_non_git(tmp_path):
    a, b, plain = tmp_path / "ws", tmp_path / "ws/SecondBrain", tmp_path / "plain"
    for d in (a, b):
        d.mkdir(parents=True, exist_ok=True)
        git(d, "init", "-q")
        git(d, "config", "user.email", "t@example.com")
        git(d, "config", "user.name", "t")
    (a / ".gitignore").write_text("SecondBrain/\n")
    (a / "README.md").write_text("x\n")
    (b / "n.md").write_text("y\n")
    plain.mkdir()
    env = {"WS_HISTORY_REPOS": f"{a} {b} {plain}"}
    p = run(["/bin/zsh", str(ROOT / "workspace-history"), "--agent", "Claude", "--task-exec", "t1", "snap"], **env)
    assert p.returncode == 0, p.stderr
    assert "no git, skipped" in p.stderr
    for d in (a, b):
        log = git(d, "log", "--format=%B")
        assert "snap" in log and "Task-Exec: t1" in log and "Agent: Claude" in log
    run(["/bin/zsh", str(ROOT / "workspace-history")], **env)
    assert git(a, "rev-list", "--count", "HEAD").strip() == "1"  # 変更が無ければ commit しない




def test_plist():
    d = plistlib.loads((ROOT / "launchd/com.taro.workspace-history.snapshot.plist").read_bytes())
    assert d["Label"] == "com.taro.workspace-history.snapshot"
    assert "/Users/taro/Workspace/src/workspace-history/workspace-history" in d["ProgramArguments"]
    assert all(k in d and d[k] == v for k, v in {'StartInterval': 3600}.items())
    short = "com.taro.workspace-history.snapshot".removeprefix("com.taro.")
    assert d["StandardOutPath"] == f"/Users/taro/Workspace/logs/{short}.log"
