#!/usr/bin/env python3
"""Workspaceの外を指すpathが、config/external_paths.json で宣言した接点以外に無いかを数える。

usage: check_workspace_paths.py [--list] [ROOT...]
既定の走査先: Workspace/src・Workspace/sb・Workspace/SecondBrain/README.md・Workspace/config・
~/.claude と ~/.codex の skill・指示・定時処理・設定。exit 0 = 違反0件。
"""
import json, os, re, sys
from pathlib import Path

HOME = Path.home()
WS = next(p for p in Path(__file__).resolve().parents if (p / "config" / "external_paths.json").exists())
EXT = json.loads((WS / "config" / "external_paths.json").read_text())
ALLOWED = [str(WS)] + [v["path"] for v in EXT["external"].values() if v["path"].startswith("/")]
# 廃止済みの場所は、過去の記録で名前が出るだけなら違反にしない
ALLOWED += [v["path"] for v in EXT.get("retired", {}).values()]
ABS = re.compile(r"(?:/Users/taro|~|\$HOME|\"\$HOME\")(/(?:[^\s\"'`)\],;|<>$]|\s(?=Support|Documents|Containers))*)")
SKIP_DIRS = {".git", ".deps", "synced", "node_modules", ".venv", "venv", "__pycache__", ".jobs", "out", "qa", "dist", "build",
             "logs", "data", "state", "test", "tests", "fixtures",
             ".system"}  # Codex に組み込みの skill（~/.codex/skills/.system）。管理の外
EXTS = {".py", ".mjs", ".js", ".cjs", ".ts", ".sh", ".command", ".json", ".toml", ".plist", ".swift", ".md", ".yaml"}


def default_roots():
    return [WS / "src", WS / "sb", WS / "SecondBrain" / "README.md", WS / "config",
            HOME / ".claude" / "skills", HOME / ".codex" / "skills", HOME / ".claude" / "CLAUDE.md",
            HOME / ".codex" / "AGENTS.md", HOME / ".codex" / "automations", HOME / ".claude" / "scheduled-tasks",
            HOME / ".claude" / "settings.json", HOME / ".codex" / "hooks.json", HOME / ".claude" / "agents"]


def violations_in(text):
    out = []
    for m in ABS.finditer(text):
        p = m.group(0)
        for prefix in ("~", '"$HOME"', "$HOME"):  # $HOME 形式も絶対パスとして扱う
            if p.startswith(prefix):
                p = str(HOME) + p[len(prefix):]
                break
        if len(p) <= len(str(HOME)) + 2 or "<" in p or "*" in p or p == str(HOME / "Library"):  # 例示・テンプレートの断片
            continue
        if not any(p == a or p.startswith(a + "/") or p.startswith(a) or a.startswith(p + " ") for a in ALLOWED) and p != str(HOME):
            out.append(p)
    return out


def scan(roots):
    found = {}
    for r in roots:
        r = Path(r)
        if not r.exists():
            continue
        it = [(str(r.parent), [], [r.name])] if r.is_file() else os.walk(r)
        for dp, ds, fs in it:
            ds[:] = [d for d in ds if d not in SKIP_DIRS]
            for f in fs:
                p = Path(dp) / f
                if p.name in ("company_confidential.json", "external_paths.json") or p.suffix not in EXTS or p.is_symlink() or f.startswith("test_") or ".test." in f or f == Path(__file__).name:
                    continue
                try:
                    text = p.read_text()
                except (UnicodeDecodeError, OSError):
                    continue
                v = violations_in(text)
                if v:
                    found[str(p)] = v
    return found


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    found = scan(args or default_roots())
    total = sum(len(v) for v in found.values())
    if "--list" in sys.argv:
        for f, v in sorted(found.items(), key=lambda x: -len(x[1])):
            print(f"{len(v)}\t{f}\t{sorted(set(v))[:3]}")
    print(json.dumps({"files": len(found), "violations": total}))
    sys.exit(1 if total else 0)
