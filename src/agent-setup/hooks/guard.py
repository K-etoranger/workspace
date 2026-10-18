#!/usr/bin/env python3
"""PreToolUse の hook: 一時置き場（/tmp・/private/tmp・/var/folders・mktemp・$TMPDIR・tempfile）を使う操作を止める。

ファイルの書き込みは行き先を、シェルはコマンドの文を見る。標準の Python だけで動き、壊れたときは何もせずに通す。
"""
import json
import re
import sys

TEMP = re.compile(r"(?<![\w.~-])/(?:private/)?tmp(?![\w.-])|(?<![\w.-])(?:/private)?/var/folders(?![\w.-])|\b(?:mktemp|tempfile)\b|\$\{?TMPDIR\b")
REASON = "一時置き場は使わない（共通ルール7章: 一時ファイルは Workspace/work/ に作り、使い終わったら消す）。"


def main() -> int:
    try:
        tool_input = json.load(sys.stdin).get("tool_input", {})
        text = str(tool_input.get("command") or tool_input.get("file_path") or tool_input.get("notebook_path") or "")
    except Exception:
        return 0
    if TEMP.search(text):
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": REASON}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
