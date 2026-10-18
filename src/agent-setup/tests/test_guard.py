import json
import subprocess
import sys
from pathlib import Path

GUARD = Path(__file__).resolve().parents[1] / "hooks" / "guard.py"


def decide(tool_input):
    r = subprocess.run([sys.executable, str(GUARD)], input=json.dumps({"tool_input": tool_input}), capture_output=True, text=True)
    return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] if r.stdout else "allow"


def test_temp_places_are_denied_and_workspace_passes():
    assert decide({"command": "echo x > /tmp/a"}) == "deny"
    assert decide({"file_path": "/private/var/folders/x/y"}) == "deny"
    assert decide({"command": "f=$(mktemp)"}) == "deny"
    assert decide({"file_path": "/Users/taro/Workspace/work/a.txt"}) == "allow"
