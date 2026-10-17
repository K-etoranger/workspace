"""launchd_deploy の試験。一時フォルダだけを使う。"""
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


# ---------------------------------------------------------------- launchd-deploy

def plist(path: Path, label: str, extra="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(plistlib.dumps({"Label": label, "ProgramArguments": ["/bin/echo", extra]}))


def test_launchd_deploy_check_apply_archive(tmp_path):
    ws, agents, archive = tmp_path / "ws", tmp_path / "LaunchAgents", tmp_path / "archive"
    plist(ws / "src/a/launchd/com.taro.a.job.plist", "com.taro.a.job")
    plist(ws / "src/b/launchd/com.taro.b.job.plist", "com.taro.b.job")
    plist(agents / "com.taro.b.job.plist", "com.taro.b.job", "old")
    plist(agents / "com.taro.retired.plist", "com.taro.retired")
    plist(agents / "com.other.keep.plist", "com.other.keep")
    env = {"WORKSPACE": str(ws), "LAUNCH_AGENTS": str(agents), "LAUNCHD_ARCHIVE": str(archive)}
    script = [sys.executable, str(ROOT / "bin/launchd_deploy.py")]
    check = run(script, **env)
    assert check.returncode == 1
    assert "install\tcom.taro.a.job" in check.stdout and "replace\tcom.taro.b.job" in check.stdout
    assert "archive\tcom.taro.retired" in check.stdout
    assert not (agents / "com.taro.a.job.plist").exists()  # 確認だけでは書かない
    applied = run(script + ["--apply"], **env)
    assert applied.returncode == 0, applied.stdout
    assert "launchctl bootstrap" in applied.stdout
    for name in ("a", "b"):
        src = ws / f"src/{name}/launchd/com.taro.{name}.job.plist"
        assert (agents / src.name).read_bytes() == src.read_bytes()
    assert (archive / "com.taro.retired.plist").exists() and (agents / "com.other.keep.plist").exists()
    assert run(script, **env).returncode == 0


def test_launchd_deploy_refuses_duplicate_labels(tmp_path):
    ws = tmp_path / "ws"
    plist(ws / "src/a/launchd/com.taro.dup.plist", "com.taro.dup")
    plist(ws / "src/b/launchd/com.taro.dup.plist", "com.taro.dup")
    p = run([sys.executable, str(ROOT / "bin/launchd_deploy.py")],
            WORKSPACE=str(ws), LAUNCH_AGENTS=str(tmp_path / "la"))
    assert p.returncode != 0 and "同じ Label" in p.stderr




def test_launchd_deploy_reads_sb_launchd(tmp_path):
    ws, agents = tmp_path / "ws", tmp_path / "LaunchAgents"
    plist(ws / "sb/launchd/com.taro.sb.job.plist", "com.taro.sb.job")
    p = run([sys.executable, str(ROOT / "bin/launchd_deploy.py")], WORKSPACE=str(ws), LAUNCH_AGENTS=str(agents),
            LAUNCHD_ARCHIVE=str(tmp_path / "archive"))
    assert "install\tcom.taro.sb.job" in p.stdout
