import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "memory_recall.py"
EVENT = {"session_id": "s1", "prompt": "トマトってどうなった", "hook_event_name": "UserPromptSubmit"}


def run(url):
    env = {**os.environ, "MEMORY_RECALL_HOOK_URL": url}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(EVENT), capture_output=True, text=True, env=env, timeout=60)


def test_adds_context_from_window():
    got = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            got.update(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            body = json.dumps({"context": "【記憶の候補】…", "count": 1}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    result = run(f"http://127.0.0.1:{server.server_address[1]}/hook")
    server.shutdown()
    assert got == {"session_id": "s1", "prompt": "トマトってどうなった"}
    out = json.loads(result.stdout)
    assert result.returncode == 0 and out["hookSpecificOutput"] == {"hookEventName": "UserPromptSubmit", "additionalContext": "【記憶の候補】…"}


def test_window_down_adds_nothing():
    result = run("http://127.0.0.1:9/hook")  # 何も待ち受けていない
    assert result.returncode == 0 and result.stdout == ""
