#!/usr/bin/env python3
"""このrepoの原本（共通ルール・共有skill・定時処理の本文）を、Codex/Claudeが読む配置先へ写す。

原本（src/agents/）                   配置先
rules/AGENTS.md                       ~/.codex/AGENTS.md
rules/claude-home.md                  ~/.claude/CLAUDE.md
settings/claude.json                  ~/.claude/settings.json（編集禁止の行に、Workspace 内で uchg の付いたファイルを足す）
skills/<skill>/                       ~/.claude/skills/<skill>/ と ~/.codex/skills/<skill>/
scheduled/<name>/SKILL.md             ~/.claude/scheduled-tasks/<name>/SKILL.md
Workspace/src/<repo>/scheduled/<name>/SKILL.md  同じ（全 repo の定時処理の本文。同じ名前が2つあれば止まる）

usage: deploy.py [--apply]
既定は確認だけ（差分があれば exit 1）。配置先を直接編集した差分は上書きされるので、先に原本へ取り込む。
settings.json は Claude Code 自身も書き換える（/model・テーマ等）。差分が出たら原本へ取り込んでから --apply する。
原本に無い配置先のskill・定時処理（Codex組込みの .system など）には触れない。
RETIRED_SCHEDULED・RETIRED_SKILLS は廃止した定時処理・skillで、配置先に残っていれば差分として出し、--apply で消す（空になったフォルダも消す）。
編集禁止の行: Workspace の外の物は原本に書き、Workspace の中は uchg（chflags uchg）の付いたファイルを配置のたびに探して作る。
"""
import filecmp, json, os, shutil, stat, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOME = Path(os.environ.get("AGENTS_DEPLOY_HOME") or Path.home())  # 試験用に差し替える
IGNORE = {"__pycache__", ".DS_Store", ".pytest_cache"}
RETIRED_SCHEDULED = (
    "old-daily-update",  # distill-messages/-preferences/-daily へ分割
    "old-liked-knowledge",  # 廃止
    "old-weekly-audit",  # 廃止（定時処理は SecondBrain を読み sb で書くだけ）
)
RETIRED_SKILLS = ("old-secondbrain-skill", "old-memory-skill")
WORKSPACE = HOME / "Workspace"
LOCKED_ROOTS = ("config", "sb", "src")  # uchg を探す所。SecondBrain（md だけ）・company・data・models・work は見ない
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "data", "models", "__pycache__"}
SETTINGS = ROOT / "settings/claude.json"


def locked_files():
    """Workspace の中で uchg（変更不可）の付いたファイル。"""
    for top in LOCKED_ROOTS:
        for dirpath, dirnames, filenames in os.walk(WORKSPACE / top):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                path = os.path.join(dirpath, name)
                if not name.endswith(".md") and os.lstat(path).st_flags & stat.UF_IMMUTABLE:
                    yield path


def settings_text():
    s = json.loads(SETTINGS.read_text(encoding="utf-8"))
    deny = s.setdefault("permissions", {}).setdefault("deny", [])
    deny[:] = sorted(set(deny) | {f"Edit(/{p})" for p in locked_files()})
    return json.dumps(s, indent=2, ensure_ascii=False) + "\n"


def _skills():
    return sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir())


def pairs():
    yield ROOT / "rules/AGENTS.md", HOME / ".codex/AGENTS.md"
    yield ROOT / "rules/claude-home.md", HOME / ".claude/CLAUDE.md"
    for skill in _skills():
        for f in sorted(skill.rglob("*")):
            if f.is_file() and not IGNORE & set(f.relative_to(skill).parts):
                rel = f.relative_to(ROOT / "skills")
                yield f, HOME / ".claude/skills" / rel
                yield f, HOME / ".codex/skills" / rel
    for name, body in _scheduled().items():
        yield body, HOME / ".claude/scheduled-tasks" / name / "SKILL.md"


def _scheduled() -> dict:
    """定時処理の本文: この repo の scheduled/ と、Workspace/src/<repo>/scheduled/（agents 自身は ROOT 側を使う）。"""
    roots = [ROOT / "scheduled"] + sorted(p / "scheduled" for p in (WORKSPACE / "src").glob("*")
                                          if p.is_dir() and p.name != "agents")
    found: dict = {}
    for root in roots:
        for body in sorted(root.glob("*/SKILL.md")):
            name = body.parent.name
            if name in found:
                sys.exit(f"同じ名前の定時処理が2つある: {name}（{found[name]} と {body}）")
            found[name] = body
    return found


def stale_files():
    """原本のskillから消えたfileが配置先に残っていないか（管理対象のskillフォルダ内だけ）と、廃止した定時処理・skill。"""
    for skill in _skills():
        for root in (HOME / ".claude/skills", HOME / ".codex/skills"):
            target = root / skill.name
            if not target.is_dir():
                continue
            for f in target.rglob("*"):
                if f.is_file() and not IGNORE & set(f.relative_to(target).parts):
                    if not (skill / f.relative_to(target)).exists():
                        yield f
    for name in RETIRED_SCHEDULED:
        f = HOME / ".claude/scheduled-tasks" / name / "SKILL.md"
        if f.is_file():
            yield f
    for d in retired_dirs():
        if d.name in RETIRED_SKILLS:
            yield from sorted(f for f in d.rglob("*") if f.is_file() or f.is_symlink())


def retired_dirs():
    for name in RETIRED_SCHEDULED:
        yield HOME / ".claude/scheduled-tasks" / name
    for name in RETIRED_SKILLS:
        for root in (HOME / ".claude/skills", HOME / ".codex/skills"):
            yield root / name


def main():
    apply = "--apply" in sys.argv
    drift = [(s, t) for s, t in pairs() if not t.exists() or not filecmp.cmp(s, t, shallow=False)]
    stale = list(stale_files())
    for s, t in drift:
        print(f"{'copy' if apply else 'differs'}\t{t}")
        if apply:
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, t)
    settings, target = settings_text(), HOME / ".claude/settings.json"
    if not target.exists() or target.read_text(encoding="utf-8") != settings:
        drift.append((SETTINGS, target))
        print(f"{'copy' if apply else 'differs'}\t{target}")
        if apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(settings, encoding="utf-8")
    for f in stale:
        print(f"{'remove' if apply else 'stale'}\t{f}")
        if apply:
            f.unlink()
    if apply:
        for d in (d for d in retired_dirs() if d.is_dir()):  # 空になったフォルダを下から消す
            for sub in sorted((p for p in d.rglob("*") if p.is_dir()), reverse=True) + [d]:
                if not any(sub.iterdir()):
                    sub.rmdir()
    print(f"# drift={len(drift)} stale={len(stale)} {'APPLIED' if apply else 'check'}")
    return 0 if apply or not (drift or stale) else 1


if __name__ == "__main__":
    sys.exit(main())
