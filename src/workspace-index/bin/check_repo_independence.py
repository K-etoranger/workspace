#!/usr/bin/env python3
"""repo（src/* と sb）が、他の repo のコード・道具・設定を名指ししていないかを調べる。

usage: check_repo_independence.py [WORKSPACE]
repo が関わってよいのは sb のコマンド・data・models・config・外の場所だけ。
`src/<別の repo>` の名指しを見つけたら1行ずつ出し、終了コード 1。試験（tests・test）と md は見ない。
"""
import os
import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", "tests", "test", "dist", "build"}
EXTS = {".py", ".mjs", ".js", ".cjs", ".ts", ".sh", ".command", ".json", ".jsonc", ".toml", ".plist", ".swift", ".yaml", ".yml", ""}


def repos(ws: Path) -> dict[str, Path]:
    found = {p.name: p for p in sorted((ws / "src").iterdir()) if p.is_dir() and not p.name.startswith(".")}
    if (ws / "sb").is_dir():
        found["sb"] = ws / "sb"
    return found


def violations(ws: Path) -> list[str]:
    all_repos = repos(ws)
    out = []
    for name, root in all_repos.items():
        others = [o for o in all_repos if o not in (name, "sb")]
        if not others:
            continue
        pat = re.compile(r"src[/\"', ]+\"?'?(" + "|".join(re.escape(o) for o in others) + r")(?![\w-])")
        for dp, ds, fs in os.walk(root):
            ds[:] = sorted(d for d in ds if d not in SKIP_DIRS)
            for f in sorted(fs):
                p = Path(dp) / f
                if p.suffix not in EXTS or ".test." in f or f.startswith("test_") or p.is_symlink():
                    continue
                try:
                    text = p.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue
                for i, line in enumerate(text.splitlines(), 1):
                    m = pat.search(line)
                    if m:
                        out.append(f"{name}\t{m.group(1)}\t{p.relative_to(ws)}:{i}")
    return out


if __name__ == "__main__":
    if sys.argv[1:2] and sys.argv[1].startswith("-"):
        print(__doc__)
        sys.exit(0 if sys.argv[1] in ("-h", "--help") else 2)
    ws = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("WORKSPACE") or "/Users/taro/Workspace")
    found = violations(ws)
    for v in found:
        print(v)
    print(f"# {len(found)} 件")
    sys.exit(1 if found else 0)
