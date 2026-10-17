#!/usr/bin/env python3
"""UserPromptSubmit の hook: 本人の発言を、手元の記憶の窓口（127.0.0.1:8767）へ送り、返ってきた記憶の候補を会話に添える。

標準の Python だけで動く。窓口が止まっている・遅い・壊れているときは、何も添えずに終わる（会話は止めない）。
"""
import json
import os
import sys
import urllib.request

URL = os.environ.get("MEMORY_RECALL_HOOK_URL", "http://127.0.0.1:8767/hook")  # 試験だけが別の窓口へ向ける


def main() -> int:
    try:
        event = json.load(sys.stdin)
        body = json.dumps({"session_id": event.get("session_id", ""), "prompt": event.get("prompt", "")}).encode()
        request = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request) as response:  # 待つ上限は settings の timeout（Claude Code が打ち切る）
            context = json.loads(response.read()).get("context", "")
    except Exception:
        return 0
    if context:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
