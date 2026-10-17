"""sb の試験用の一時 vault。本物の vault には決して触れない。"""

import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MARKER = "ZZCORP-CONFIDENTIAL-42"


class Env:
    def __init__(self, root, monkeypatch, capsys):
        self.root, self.mp, self.capsys = root, monkeypatch, capsys
        self.ws = root / "ws"
        self.vault = self.ws / "SecondBrain"

    def now(self, iso):
        self.mp.setenv("SB_NOW", iso)

    def run(self, *argv, stdin=""):
        from sb.cli import main
        from sb.paths import data_root, vault_root
        # 本物の vault・data に書かないための安全装置
        assert str(vault_root()).startswith(str(self.root)) and str(data_root()).startswith(str(self.root))
        self.capsys.readouterr()
        self.mp.setattr(sys, "stdin", io.StringIO(stdin))
        code = main([str(a) for a in argv])
        out = self.capsys.readouterr()
        self.out, self.err = out.out, out.err
        return code

    def json(self, *argv, stdin=""):
        code = self.run(*argv, "--json", stdin=stdin)
        return code, json.loads(self.out)

    def read(self, rel):
        return (self.vault / rel).read_text(encoding="utf-8")

    def write(self, rel, text):
        p = self.vault / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


@pytest.fixture
def sbv(tmp_path, monkeypatch, capsys):
    ws = tmp_path / "ws"
    (ws / "config").mkdir(parents=True)
    (ws / "SecondBrain").mkdir()
    policy = {
        "enforcement": "fail_closed", "path_prefixes": ["company/"], "path_globs": ["**/会社資料/**"],
        "content_markers": [MARKER], "content_scan_extensions": [".md"],
        "local_only_source_paths": [str(ws / "company")],
    }
    (ws / "config" / "company_confidential.json").write_text(json.dumps(policy), encoding="utf-8")
    for var in ("SB_VAULT", "SB_DATA", "SB_CONFIG"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("SB_WORKSPACE", str(ws))
    monkeypatch.setenv("SB_NOW", "2026-09-29T20:00:00+09:00")
    monkeypatch.setenv("SB_LOCK_WAIT", "0")
    return Env(tmp_path, monkeypatch, capsys)
