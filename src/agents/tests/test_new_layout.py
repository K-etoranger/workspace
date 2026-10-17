"""新しい置き場（deploy.py・指示文書の旧置き場）の試験。"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DeployTest(unittest.TestCase):
    def run_deploy(self, home, *args):
        env = dict(os.environ, AGENTS_DEPLOY_HOME=str(home))
        return subprocess.run([sys.executable, str(ROOT / "deploy.py"), *args], env=env, capture_output=True, text=True)

    def test_check_apply_check_and_retired_schedule(self):
        with tempfile.TemporaryDirectory() as home:
            home = Path(home)
            olds = [home / ".claude/scheduled-tasks" / n / "SKILL.md" for n in ("old-daily-update", "old-liked-knowledge")]
            other = home / ".claude/scheduled-tasks/garden-daily/SKILL.md"
            for f in (*olds, other):
                f.parent.mkdir(parents=True)
                f.write_text("old", encoding="utf-8")
            first = self.run_deploy(home)
            self.assertEqual(first.returncode, 1)
            for old in olds:
                self.assertIn("stale\t" + str(old), first.stdout)
            self.assertEqual(self.run_deploy(home, "--apply").returncode, 0)
            again = self.run_deploy(home)
            self.assertEqual(again.returncode, 0, again.stdout)
            self.assertIn("# drift=0 stale=0 check", again.stdout)
            for old in olds:
                self.assertFalse(old.parent.exists())
            self.assertTrue(other.exists())  # 他repoの定時処理には触れない
            self.assertEqual((home / ".codex/AGENTS.md").read_bytes(), (ROOT / "rules/AGENTS.md").read_bytes())
            for name in ("distill-messages", "distill-preferences", "distill-daily"):
                self.assertTrue((home / ".claude/scheduled-tasks" / name / "SKILL.md").is_file())
            self.assertTrue((home / ".codex/skills/write-workspace-readme/SKILL.md").is_file())


class RulesPathTest(unittest.TestCase):
    def test_no_old_places_left_in_instruction_files(self):
        old = ("old-place-a", "old-place-b")
        hits = []
        for d in ("rules", "skills", "scheduled", "docs", "launchd"):
            for f in (ROOT / d).rglob("*"):
                if f.is_file() and f.suffix in {".md", ".yaml", ".command", ".plist"}:
                    text = f.read_text(encoding="utf-8")
                    hits += [f"{f.relative_to(ROOT)}: {o}" for o in old if o in text]
        self.assertEqual(hits, [])
