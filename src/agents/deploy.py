#!/usr/bin/env python3
"""全 repo のエージェント向けの原本を集め、Codex/Claude が読む配置先へ写す。中身は持たない。

原本（Workspace/src/<repo>/）               配置先
rules/AGENTS.md（全 repo で1つ）            ~/.codex/AGENTS.md
rules/claude-home.md（全 repo で1つ）       ~/.claude/CLAUDE.md
settings/claude.json（全 repo で1つ）       ~/.claude/settings.json（hooks/hooks.json を合わせ、編集禁止の行に uchg のファイルを足す）
hooks/hooks.json                            同じ settings.json の hooks
skills/<skill>/                             ~/.claude/skills/<skill>/ と ~/.codex/skills/<skill>/
scheduled/<name>/SKILL.md                   ~/.claude/scheduled-tasks/<name>/SKILL.md
同じ名前が2つの repo にあれば止まる。

usage: deploy.py [--apply | --archive]
既定は確認だけ（差分があれば exit 1）。--apply は写すだけ。
- 配った skill・定時処理の名前を data/agents/state/deployed.json に残し、原本から消えた物を orphan として出す。
  --archive はそれを ~/Documents/_archive_<日付>/agents/ へ移す（一覧を本人に見せてから流す）。
- 定時処理の時刻は本文の頭の schedule: が正本。Claude アプリの登録を読むだけで比べ、違えば schedule として出す。
- 原本の skill から消えたファイルは stale として出し、--apply で消す。原本に無い配置先の物（アプリの物など）には触れない。
- settings.json は Claude Code 自身も書き換える。差分が出たら原本へ取り込んでから --apply する。
"""
import filecmp, glob, json, os, re, shlex, shutil, stat, sys
from datetime import date
from pathlib import Path

HOME = Path(os.environ.get("AGENTS_DEPLOY_HOME") or Path.home())  # 試験用に差し替える
WORKSPACE = HOME / "Workspace"
SRC = WORKSPACE / "src"
STATE = WORKSPACE / "data/agents/state/deployed.json"
CLAUDE_STORES = HOME / "Library/Application Support/Claude/claude-code-sessions/*/*/scheduled-tasks.json"
IGNORE = {"__pycache__", ".DS_Store", ".pytest_cache"}
LOCKED_ROOTS = ("config", "sb", "src")  # uchg を探す所。SecondBrain（md だけ）・company・data・models・work は見ない
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "data", "models", "__pycache__"}
TARGETS = {"skills": (".claude/skills", ".codex/skills"), "scheduled": (".claude/scheduled-tasks",)}


def one(pattern):
    found = sorted(SRC.glob(pattern))
    if len(found) != 1:
        sys.exit(f"{pattern} が全 repo で1つではない: {[str(p) for p in found]}")
    return found[0]


def named(pattern):
    """<repo>/<kind>/<name>/SKILL.md の name → フォルダ。同じ名前が2つあれば止まる。"""
    found = {}
    for body in sorted(SRC.glob(pattern)):
        name = body.parent.name
        if name in found:
            sys.exit(f"同じ名前が2つある: {name}（{found[name]} と {body.parent}）")
        found[name] = body.parent
    return found


def sources():
    return {"skills": named("*/skills/*/SKILL.md"), "scheduled": named("*/scheduled/*/SKILL.md")}


def locked_files():
    """Workspace の中で uchg（変更不可）の付いたファイル。"""
    for top in LOCKED_ROOTS:
        for dirpath, dirnames, filenames in os.walk(WORKSPACE / top):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                path = os.path.join(dirpath, name)
                if not name.endswith(".md") and os.lstat(path).st_flags & stat.UF_IMMUTABLE:
                    yield path


def hooks():
    """各 repo の hooks/hooks.json を settings の hooks の形にする。command の / で始まらない要素は repo からのパス。"""
    merged = {}
    for f in sorted(SRC.glob("*/hooks/hooks.json")):
        for event, entries in json.loads(f.read_text(encoding="utf-8")).items():
            for e in entries:
                cmd = " ".join(shlex.quote(a if a.startswith("/") else str(f.parent.parent / a)) for a in e["command"])
                hook = {"type": "command", "command": cmd, **({"timeout": e["timeout"]} if "timeout" in e else {})}
                merged.setdefault(event, []).append({**({"matcher": e["matcher"]} if "matcher" in e else {}), "hooks": [hook]})
    return merged


def settings_text():
    base = one("*/settings/claude.json")
    s = json.loads(base.read_text(encoding="utf-8"))
    if "hooks" in s:
        sys.exit(f"{base} に hooks がある（hook は各 repo の hooks/hooks.json に書く）")
    deny = s.setdefault("permissions", {}).setdefault("deny", [])
    deny[:] = sorted(set(deny) | {f"Edit(/{p})" for p in locked_files()})
    if h := hooks():
        s["hooks"] = h
    return json.dumps(s, indent=2, ensure_ascii=False) + "\n"


def pairs(src):
    yield one("*/rules/AGENTS.md"), HOME / ".codex/AGENTS.md"
    yield one("*/rules/claude-home.md"), HOME / ".claude/CLAUDE.md"
    for kind, items in src.items():
        for name, folder in items.items():
            for f in sorted(folder.rglob("*")):
                if f.is_file() and not IGNORE & set(f.relative_to(folder).parts):
                    for root in TARGETS[kind]:
                        yield f, HOME / root / name / f.relative_to(folder)


def stale_files(src):
    """原本の skill から消えたファイルが、配置先の同じ skill のフォルダに残っていないか。"""
    for name, folder in src["skills"].items():
        for root in TARGETS["skills"]:
            target = HOME / root / name
            for f in (target.rglob("*") if target.is_dir() else ()):
                if f.is_file() and not IGNORE & set(f.relative_to(target).parts) and not (folder / f.relative_to(target)).exists():
                    yield f


def read_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def orphans(src):
    """前に配ったのに今は原本の無い skill・定時処理の、配置先に残っているフォルダ。"""
    state = read_state()
    for kind, roots in TARGETS.items():
        for name in sorted(set(state.get(kind, [])) - set(src[kind])):
            for root in roots:
                if (HOME / root / name).exists():
                    yield kind, name, HOME / root / name


def _cron(text):
    return " ".join(re.sub(r"\b0+(\d)", r"\1", t) for t in text.split())


def schedule_diffs(src):
    """本文の schedule: と Claude アプリの登録の食い違い。登録が読めなければそれも食い違いとして出す。"""
    stores = sorted(glob.glob(str(CLAUDE_STORES)), key=os.path.getmtime)
    if not stores:
        yield f"schedule\t登録が読めない\t{CLAUDE_STORES}"
        return
    rows = {r["id"]: r for r in json.loads(Path(stores[-1]).read_text(encoding="utf-8")).get("scheduledTasks", [])}
    for name, folder in src["scheduled"].items():
        m = re.search(r'^schedule:\s*"?([^"\n]+)"?\s*$', (folder / "SKILL.md").read_text(encoding="utf-8").split("\n---", 1)[0], re.M)
        row = rows.get(name)
        if not m:
            yield f"schedule\t{name}\t本文に schedule: が無い"
        elif not row:
            yield f"schedule\t{name}\t正本={m[1]}\t登録=無し"
        elif _cron(m[1]) != _cron(row.get("cronExpression", "")) or not row.get("enabled", True):
            yield f"schedule\t{name}\t正本={m[1]}\t登録={row.get('cronExpression')}{'' if row.get('enabled', True) else '（停止中）'}"
    for name in sorted(set(rows) - set(src["scheduled"])):
        yield f"schedule\t{name}\t登録だけあり、原本が無い"


def main():
    apply, archive = "--apply" in sys.argv, "--archive" in sys.argv
    src = sources()
    drift = [(s, t) for s, t in pairs(src) if not t.exists() or not filecmp.cmp(s, t, shallow=False)]
    for s, t in drift:
        print(f"{'copy' if apply else 'differs'}\t{t}")
        if apply:
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, t)
    settings, target = settings_text(), HOME / ".claude/settings.json"
    if not target.exists() or target.read_text(encoding="utf-8") != settings:
        drift.append((None, target))
        print(f"{'copy' if apply else 'differs'}\t{target}")
        if apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(settings, encoding="utf-8")
    stale = list(stale_files(src))
    for f in stale:
        print(f"{'remove' if apply else 'stale'}\t{f}")
        if apply:
            f.unlink()
    left = list(orphans(src))
    for kind, name, path in left:
        dest = HOME / "Documents" / f"_archive_{date.today().isoformat()}" / "agents" / path.relative_to(HOME)
        print(f"{'archive' if archive else 'orphan'}\t{path}" + (f" -> {dest}" if archive else ""))
        if archive:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(dest))
    if apply or archive:
        kept = {(k, n) for k, n, p in left if p.exists()}
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({k: sorted(set(src[k]) | {n for kk, n in kept if kk == k}) for k in TARGETS},
                                    indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    sched = list(schedule_diffs(src))
    for line in sched:
        print(line)
    print(f"# drift={len(drift)} stale={len(stale)} orphan={len(left)} schedule={len(sched)} "
          f"{'ARCHIVED' if archive else 'APPLIED' if apply else 'check'}")
    return 0 if apply or archive or not (drift or stale or left or sched) else 1


if __name__ == "__main__":
    sys.exit(main())
