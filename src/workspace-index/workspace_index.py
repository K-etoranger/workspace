#!/usr/bin/env python3
"""Workspace の地図（一覧になる README）を作り、置き場の決まりを確かめる。

  workspace_index.py refresh [--out DIR]   Workspace/README・src/README・data/README・models/README・logs/README を作る。
                                           中身が変わらなければ書かない。--out を付けると DIR の下に同じ形で書く（試し）
  workspace_index.py check                 作らずに、決まりに合わない所（警告）だけを出す。警告があれば終了コード 1

材料は各 repo（src/* と sb）の README の欄（5 章のテンプレート）・launchd/*.plist・コード。
警告は中身が前回と変わったときだけ `sb log schedule --task workspace-index` に書き、1件以上ならタスクを1件作る。
"""

from __future__ import annotations

import json
import os
import plistlib
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "bin"))
import check_repo_independence as independence  # noqa: E402

HEADER_NOTE = "この README は `src/workspace-index` が作る。手で直さない。"
BY = "workspace-index/refresh"
FIELDS = ("使い方", "data に書く場所", "data から読む場所", "SecondBrain に書く層", "SecondBrain から読む層",
          "使うモデル", "定時処理", "試験", "してはいけないこと")
# 直下の置き場。company は会社側の物なので、中身（README の文）を個人側へ写さない。
COMPANY_TEXT = "勤務先の資料。会社側が持ち、個人側から中身を変えない。"
TOP_TEXT = {
    "src": "仕組み（コード）の置き場。1システム1repo。",
    "data": "仕組みが書くデータの置き場。フォルダごとに書き手は1つの repo だけ。",
    "models": "仕組みが使うモデルの置き場。直下はモデル名のフォルダだけ。",
    "logs": "定時処理のログの置き場。",
}
DATA_PATH = re.compile(r"`?(data/[^\s`（(、,]+)")
MODEL_PATH = re.compile(r"`?models/([^\s`（(、,/]+)")


def workspace() -> Path:
    return Path(os.environ.get("WORKSPACE") or "/Users/taro/Workspace")


# ---------------------------------------------------------------- README を読む


def first_line(text: str) -> str | None:
    """`# 名前` の次の空行の次の1文。頭書き（--- … ---）があれば飛ばす。形が違えば None。"""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        end = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == "---"), None)
        lines = lines[end + 1:] if end else []
    while lines and not lines[0].strip():
        lines = lines[1:]
    if len(lines) < 3 or not lines[0].startswith("# ") or lines[1].strip():
        return None
    line = lines[2].strip()
    return line if line and not line.startswith(("#", "|", "-", "```", ">")) else None


def sections(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            out[current] = []
        elif current is not None and line.strip():
            out[current].append(line.rstrip())
    return out


@dataclass
class Repo:
    name: str          # README で表示する名前（src の repo は名前、sb は sb）
    path: Path
    readme: str | None
    first: str | None = None
    fields: dict[str, list[str]] = field(default_factory=dict)
    writes: list[str] = field(default_factory=list)
    reads: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    jobs: list[dict] = field(default_factory=list)
    agent_jobs: list[tuple[str, str]] = field(default_factory=list)  # (名前, schedule:) scheduled/<名前>/SKILL.md のエージェントの定時処理


def load_repo(name: str, path: Path) -> Repo:
    readme_path = path / "README.md"
    text = readme_path.read_text(encoding="utf-8") if readme_path.is_file() else None
    repo = Repo(name, path, text)
    if text is not None:
        repo.first = first_line(text)
        repo.fields = sections(text)
        repo.writes = [m.group(1).rstrip("/") for l in repo.fields.get("data に書く場所", []) for m in [DATA_PATH.search(l)] if m]
        repo.reads = [m.group(1).rstrip("/") for l in repo.fields.get("data から読む場所", []) for m in [DATA_PATH.search(l)] if m]
        repo.models = [m.group(1) for l in repo.fields.get("使うモデル", []) for m in [MODEL_PATH.search(l)] if m]
    for plist in sorted((path / "launchd").glob("*.plist")):
        try:
            data = plistlib.loads(plist.read_bytes())
        except Exception:  # noqa: BLE001 - 壊れた plist は警告にする
            data = {"Label": plist.stem, "_broken": True}
        repo.jobs.append(data)
    repo.agent_jobs = [(p.parent.name, schedule(p)) for p in sorted((path / "scheduled").glob("*/SKILL.md"))]
    return repo


def schedule(body: Path) -> str:
    """本文の頭の schedule:（cron）。無ければ空。"""
    m = re.search(r'^schedule:\s*"?([^"\n]+)"?\s*$', body.read_text(encoding="utf-8").split("\n---", 1)[0], re.M)
    return m[1].strip() if m else ""


def cron_when(cron: str) -> str:
    """毎日の「分 時」だけの cron は 04:05・08:05 の形に、それ以外はそのまま出す。"""
    f = cron.split()
    if len(f) == 5 and f[2:] == ["*", "*", "*"] and f[0].isdigit() and all(h.isdigit() for h in f[1].split(",")):
        return "・".join(f"{int(h):02d}:{int(f[0]):02d}" for h in f[1].split(","))
    return f"`{cron}`" if cron else "時刻なし"


def repos(ws: Path) -> list[Repo]:
    found = [load_repo(p.name, p) for p in sorted((ws / "src").iterdir()) if p.is_dir() and not p.name.startswith(".")]
    if (ws / "sb").is_dir():
        found.append(load_repo("sb", ws / "sb"))
    return found


# ---------------------------------------------------------------- 定時処理の時刻


def when(job: dict) -> str:
    parts = []
    cal = job.get("StartCalendarInterval")
    if cal:
        items = cal if isinstance(cal, list) else [cal]
        times = []
        for item in items:
            hm = f"{item.get('Hour', 0):02d}:{item.get('Minute', 0):02d}"
            if "Weekday" in item:
                hm = "日月火水木金土日"[item["Weekday"] % 7] + " " + hm
            times.append(hm)
        parts.append("・".join(times))
    interval = job.get("StartInterval")
    if interval:
        parts.append(f"{interval // 3600}時間ごと" if interval % 3600 == 0 else f"{interval // 60}分ごと")
    if job.get("KeepAlive"):
        parts.append("常駐")
    if job.get("WatchPaths"):
        parts.append("変更時")
    if not parts and job.get("RunAtLoad"):
        parts.append("起動時")
    return "・".join(parts) or "手動"


def short(label: str) -> str:
    return label.removeprefix("com.taro.")


# ---------------------------------------------------------------- 検査


def covered(target: str, writes: dict[str, list[str]]) -> list[str]:
    """target（data/…）を書く repo。target かその親を宣言した repo。"""
    return sorted({r for w, rs in writes.items() for r in rs if target == w or target.startswith(w + "/")})


def data_rows(ws: Path, all_repos: list[Repo]) -> tuple[list[tuple[str, list[str], list[str]]], list[str]]:
    """data の中を宣言に合わせて下り、書き手が決まる深さで1行にする。"""
    writes: dict[str, list[str]] = {}
    reads: dict[str, list[str]] = {}
    for repo in all_repos:
        for w in repo.writes:
            writes.setdefault(w, []).append(repo.name)
        for r in repo.reads:
            reads.setdefault(r, []).append(repo.name)
    rows, warnings = [], []

    def readers(rel: str) -> list[str]:
        return sorted({n for r, ns in reads.items() for n in ns if r == rel or r.startswith(rel + "/") or rel.startswith(r + "/")})

    def walk(path: Path):
        rel = path.relative_to(ws).as_posix()
        writers = covered(rel, writes)
        deeper = any(w.startswith(rel + "/") for w in writes)
        if writers or not deeper or not path.is_dir() or path.is_symlink():
            rows.append((rel, writers, readers(rel)))
            if not writers:
                warnings.append(f"data の書き手が無い: {rel}")
            elif len(writers) > 1:
                warnings.append(f"data の書き手が2つ以上: {rel}（{'・'.join(writers)}）")
            return
        for child in sorted(path.iterdir()):
            if not child.name.startswith("."):
                walk(child)

    root = ws / "data"
    if root.is_dir():
        for child in sorted(root.iterdir()):
            if not child.name.startswith(".") and child.name != "README.md":  # 自分が作る一覧は data ではない
                walk(child)
    for w, names in sorted(writes.items()):
        if not (ws / w).exists():
            warnings.append(f"README に書いた data の場所が無い: {w}（{'・'.join(names)}）")
    for r, names in sorted(reads.items()):
        if not (ws / r).exists():
            warnings.append(f"README に書いた data の場所が無い: {r}（{'・'.join(names)}）")
    return rows, warnings


def readme_warnings(ws: Path, all_repos: list[Repo]) -> list[str]:
    out = []
    for name in top_dirs(ws):
        p = ws / name / "README.md"
        if name in TOP_TEXT or name == "company":
            continue  # 自動で作る物・会社側の物
        if not p.is_file():
            out.append(f"README が無い: {name}/")
        elif first_line(p.read_text(encoding="utf-8")) is None:
            out.append(f"README の冒頭1行が無い: {name}/README.md")
    for repo in all_repos:
        where = "sb" if repo.name == "sb" else f"src/{repo.name}"
        if repo.readme is None:
            out.append(f"README が無い: {where}/")
            continue
        if repo.name == "sb":
            if repo.first is None:
                out.append(f"README の冒頭1行が無い: {where}/README.md")
            continue  # sb の README の欄は data・モデルだけを見る（使い方が主の手書き）
        if repo.first is None:
            out.append(f"README の冒頭1行が無い: {where}/README.md")
        missing = [f for f in FIELDS if f not in repo.fields]
        if missing:
            out.append(f"README の欄が無い: {where}/README.md（{'・'.join(missing)}）")
        empty = [f for f in FIELDS if f in repo.fields and not repo.fields[f]]
        if empty:
            out.append(f"README の欄が空（無いなら「なし」と書く）: {where}/README.md（{'・'.join(empty)}）")
    for repo in all_repos:
        for m in repo.models:
            if not (ws / "models" / m).exists():
                out.append(f"README に書いたモデルが無い: models/{m}（{repo.name}）")
        for job in repo.jobs:
            if job.get("_broken"):
                out.append(f"読めない plist: {repo.name}/launchd/{job['Label']}.plist")
    return out


def code_warnings(ws: Path, all_repos: list[Repo]) -> list[str]:
    """コードが他の repo を名指ししている所と、README で申告していない data のフォルダに触れている所。"""
    out = []
    for v in independence.violations(ws):
        name, other, where = v.split("\t")
        out.append(f"他の repo を名指ししている: {name} → src/{other}（{where}）")
    data = ws / "data"
    folders = sorted(p.name for p in data.iterdir() if p.is_dir() and not p.name.startswith(".")) if data.is_dir() else []
    if not folders:
        return out
    alt = "|".join(re.escape(f) for f in folders)
    # `data/<フォルダ>` と、組み立てた形（`"data" / "<フォルダ>"`・`"data", "<フォルダ>"`）
    pat = re.compile(r"(?<![\w.-])data/(" + alt + r")(?![\w.-])|[\"']data[\"']\s*[,/)]\s*[\"'](" + alt + r")[\"']")
    for repo in all_repos:
        declared = {d.split("/")[1] for d in repo.writes + repo.reads if d.count("/") >= 1}
        seen = set()
        for dp, ds, fs in os.walk(repo.path):
            ds[:] = sorted(d for d in ds if d not in independence.SKIP_DIRS)
            for f in sorted(fs):
                p = Path(dp) / f
                agent_job = f == "SKILL.md" and p.parent.parent.name == "scheduled"  # エージェントの定時処理の本文
                if (p.suffix not in independence.EXTS and not agent_job) or ".test." in f or f.startswith("test_") \
                        or p.is_symlink():
                    continue
                try:
                    text = p.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue
                for i, line in enumerate(text.splitlines(), 1):
                    for m in pat.finditer(line):
                        folder = m.group(1) or m.group(2)
                        if folder not in declared and folder not in seen:
                            seen.add(folder)
                            out.append(f"README で申告していない data に触れている: {repo.name} → data/{folder}"
                                       f"（{p.relative_to(ws)}:{i}）")
    return out


def top_dirs(ws: Path) -> list[str]:
    return sorted(p.name for p in ws.iterdir() if p.is_dir() and not p.name.startswith("."))


# ---------------------------------------------------------------- 書く中身


def table(head: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def doc(title: str, first: str, body: str) -> str:
    return f"# {title}\n\n{first}\n\n{HEADER_NOTE}\n\n{body.rstrip()}\n"


def names(xs: list[str]) -> str:
    return "・".join(f"`{x}`" for x in xs) if xs else "なし"


def build(ws: Path) -> tuple[dict[str, str], list[str]]:
    all_repos = repos(ws)
    src_repos = [r for r in all_repos if r.name != "sb"]
    out: dict[str, str] = {}

    rows = []
    for name in top_dirs(ws):
        if name == "company":
            text = COMPANY_TEXT
        elif name in TOP_TEXT:
            text = TOP_TEXT[name]
        else:
            p = ws / name / "README.md"
            text = (first_line(p.read_text(encoding="utf-8")) if p.is_file() else None) or "（README が無い）"
        rows.append([f"`{name}/`", text, f"[`{name}/README.md`]({name}/README.md)"])
    out["README.md"] = doc("Workspace", "山田太郎の作業・記憶・仕組みの置き場。この中だけで作業する。",
                           table(["置き場", "何か", "使うなら読む"], rows)
                           + "\n\nWorkspace の外に触れてよい場所は [`config/README.md`](config/README.md) を見る。")

    rows = []
    for r in src_repos:
        jobs = "<br>".join([f"`{short(j['Label'])}` {when(j)}" for j in r.jobs]
                            + [f"`{n}` {cron_when(c)}（エージェント）" for n, c in r.agent_jobs]) or "なし"
        rows.append([f"[`{r.name}`]({r.name}/README.md)", r.first or "（README の冒頭1行が無い）", jobs])
    out["src/README.md"] = doc("src", TOP_TEXT["src"],
                               "repo を使うなら、その repo の README.md を読む。\n\n"
                               + table(["repo", "何か", "定時処理（時刻。エージェントの定時処理は「（エージェント）」付き）"], rows))

    drows, dwarn = data_rows(ws, all_repos)
    out["data/README.md"] = doc("data", TOP_TEXT["data"],
                                "書く・読むの宣言は各 repo の README（「data に書く場所」「data から読む場所」）が正本。\n\n"
                                + table(["フォルダ", "書き手", "読み手"],
                                        [[f"`{rel}`", names(w), names(r)] for rel, w, r in drows]))

    users: dict[str, list[str]] = {}
    for r in all_repos:
        for m in r.models:
            users.setdefault(m, []).append(r.name)
    mdir = ws / "models"
    mnames = sorted(p.name for p in mdir.iterdir() if not p.name.startswith(".")) if mdir.is_dir() else []
    out["models/README.md"] = doc("models", TOP_TEXT["models"],
                                  "使い手の宣言は各 repo の README（「使うモデル」）が正本。\n\n"
                                  + table(["モデル", "使う repo"], [[f"`{m}`", names(sorted(users.get(m, [])))] for m in mnames]))

    rows = []
    for r in all_repos:
        for j in r.jobs:
            logs = sorted({Path(j[k]).name for k in ("StandardOutPath", "StandardErrorPath") if j.get(k)})
            rows.append([names(logs), f"`{j['Label']}`", f"`{r.name}`"])
    out["logs/README.md"] = doc("logs", TOP_TEXT["logs"],
                                "ログの置き場は各 repo の `launchd/*.plist` が決める。\n\n"
                                + table(["ログ", "書く定時処理", "repo"], sorted(rows)))
    return out, readme_warnings(ws, all_repos) + dwarn + code_warnings(ws, all_repos)


# ---------------------------------------------------------------- 書く・知らせる


def write_changed(files: dict[str, str], root: Path) -> list[str]:
    changed = []
    for rel, text in files.items():
        p = root / rel
        if p.is_file() and p.read_text(encoding="utf-8") == text:
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(p)
        changed.append(rel)
    return changed


def report(ws: Path, warnings: list[str]) -> None:
    """警告の中身が前回と変わったときだけ sb log schedule へ1回書き、1件以上ならタスクを1件作る。
    比べるときは行番号を外す（違反と関係のない行の増減で、同じ警告を出し直さない）。"""
    state = ws / "data" / "workspace-index" / "last_warnings.json"
    key = [re.sub(r":\d+）$", "）", w) for w in warnings]
    if state.is_file() and json.loads(state.read_text(encoding="utf-8")) == key:
        return
    sb = os.environ.get("SB_BIN") or str(ws / "sb" / "bin" / "sb")

    def run(*args: str) -> subprocess.CompletedProcess:
        proc = subprocess.run([sb, *args], capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"workspace-index: sb {args[0]} {args[1]} が失敗した: {proc.stderr.strip()}", file=sys.stderr)
        return proc

    listed = "\n".join(f"- {w}" for w in warnings)
    if run("log", "schedule", "--task", "workspace-index", "--text",
           f"警告 {len(warnings)} 件\n{listed}" if warnings else "警告なし", "--by", BY).returncode != 0:
        return
    if warnings:
        day = run("day", "--json")
        if day.returncode != 0:
            return
        date = json.loads(day.stdout)["date"]
        body = (f"workspace-index の定時の検査（{date}）で、決まりに合わない所が見つかった。\n\n{listed}\n\n"
                "直し方: 該当の repo の git の履歴（いつ・どの merge で入ったか）をたどり、戻すか、README の申告を直す。\n"
                "直ったかは workspace-index の README の「使い方」の check で警告0件を確かめる。")
        stamp = datetime.now().strftime("%H%M")  # 同じ日に警告が変わっても ID が重ならない（毎時1回しか動かない）
        if run("task", "new", "--id", f"{date.replace('-', '')}-workspace-index-warnings-{stamp}",
               "--title", f"Workspace の決まりに合わない所を直す（workspace-index の検査で{len(warnings)}件）",
               "--owner", "本人+エージェント", "--due", date, "--text", body, "--by", BY).returncode != 0:
            return
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps(key, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help") or argv[0] not in ("refresh", "check"):
        print(__doc__)
        return 0 if argv and argv[0] in ("-h", "--help") else 1
    rest = argv[1:]
    out_dir = None
    if rest[:1] == ["--out"] and len(rest) == 2 and argv[0] == "refresh":
        out_dir = Path(rest[1])
    elif rest:
        print(f"workspace-index: 知らない引数: {' '.join(rest)}（何もしていない）", file=sys.stderr)
        return 1
    ws = workspace()
    files, warnings = build(ws)
    for w in warnings:
        print(f"警告\t{w}")
    if argv[0] == "check":
        return 1 if warnings else 0
    changed = write_changed(files, out_dir or ws)
    for rel in changed:
        print(f"書いた\t{rel}")
    if out_dir is None:
        report(ws, warnings)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
