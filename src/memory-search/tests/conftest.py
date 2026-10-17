import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """一時の Workspace。memory-search の置き場をすべてそこへ向ける。"""
    monkeypatch.setenv("WORKSPACE", str(tmp_path))
    (tmp_path / "SecondBrain").mkdir()
    return tmp_path


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
