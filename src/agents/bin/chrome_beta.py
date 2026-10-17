"""エージェント専用の Chrome Beta（CDP 9290）を確かめ、止まっていれば起こす。

`python3 bin/chrome_beta.py` で起こす（本人がログインするときも同じ）。
プロファイルと状態は data/agents の下。Stable・他の Beta には触れない。
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PORT = 9290
EXECUTABLE = "/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta"
BUNDLE_ID = "com.google.Chrome.beta"
DATA = Path(os.environ.get("AGENTS_DATA", Path.home() / "Workspace/data/agents"))
PROFILE = DATA / "browser_profiles" / "chrome_beta"
STATE = DATA / "state" / "chrome_beta.json"
CDP_URL = f"http://127.0.0.1:{PORT}"


def cdp_alive(url=CDP_URL):
    try:
        with urllib.request.urlopen(f"{url}/json/version", timeout=2):
            return True
    except Exception:
        return False


def _command(pid):
    r = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def owns(pid, executable=EXECUTABLE, profile=PROFILE, port=PORT):
    c = _command(pid) if isinstance(pid, int) and pid > 1 else ""
    return bool(c) and c.startswith(executable) and f"--user-data-dir={profile}" in c and f"--remote-debugging-port={port}" in c


def _read_state():
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def ensure_running(executable=EXECUTABLE):
    """CDP が生きていれば CDP の URL を返す。止まっていれば専用 Beta を起こす。"""
    if not executable.endswith("/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta") or not os.path.exists(executable):
        raise RuntimeError("BETA_NOT_INSTALLED")
    plist = str(Path(executable).parents[1] / "Info.plist")
    r = subprocess.run(["/usr/bin/defaults", "read", plist, "CFBundleIdentifier"], capture_output=True, text=True)
    if r.stdout.strip() != BUNDLE_ID:
        raise RuntimeError("BETA_BUNDLE_ID_MISMATCH")
    state = _read_state()
    if cdp_alive():
        if not owns(state.get("pid")):
            raise RuntimeError("BETA_PORT_NOT_OWNED")  # 9290 を別の物が使っている
        return CDP_URL
    if owns(state.get("pid")):
        raise RuntimeError("BETA_ALIVE_WITHOUT_CDP")
    PROFILE.mkdir(parents=True, exist_ok=True, mode=0o700)
    child = subprocess.Popen(
        [executable, "--remote-debugging-address=127.0.0.1", f"--remote-debugging-port={PORT}",
         f"--user-data-dir={PROFILE}", "--no-first-run", "--no-default-browser-check",
         "--disable-session-crashed-bubble", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    STATE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    STATE.write_text(json.dumps({"pid": child.pid, "port": PORT, "profileDir": str(PROFILE)}))
    for _ in range(40):
        time.sleep(0.5)
        if cdp_alive() and owns(child.pid):
            return CDP_URL
    raise RuntimeError("BETA_STARTED_WITHOUT_OWNED_CDP")


if __name__ == "__main__":
    try:
        print(ensure_running())
    except RuntimeError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
