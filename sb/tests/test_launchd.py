"""sb の定時処理（launchd/）は sb 自身の手入れ3本だけで、どれも sb を呼ぶ。"""
import plistlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SB = "/Users/taro/Workspace/sb/bin/sb"
EXPECTED = {
    "com.taro.sb.views-refresh": ["views", "refresh", "--by", "sb/views-refresh"],
    "com.taro.sb.check": ["check", "--by", "sb/check"],
    "com.taro.sb.tidy": ["task", "tidy", "--by", "sb/tidy"],
}


def test_plists():
    found = {p.stem: plistlib.loads(p.read_bytes()) for p in (ROOT / "launchd").glob("*.plist")}
    assert set(found) == set(EXPECTED)
    for label, d in found.items():
        args = d["ProgramArguments"]
        assert d["Label"] == label
        assert args == [SB, *EXPECTED[label]]  # 包み（別 repo の道具）を挟まず sb を直接呼ぶ
        short = label.removeprefix("com.taro.")
        assert d["StandardOutPath"].endswith(f"/logs/{short}.log")
        assert d["StandardErrorPath"].endswith(f"/logs/{short}.err.log")
