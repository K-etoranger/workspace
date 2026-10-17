"""30_projects: active/<案件>/メモ.md（＋資料/）。archive は読み取り専用で、close/reopen だけが出し入れする。"""

import os
import re
from pathlib import Path

from . import SbError, frontmatter, task
from .logical_day import parse_date, today
from .paths import vault_root, workspace_root
from .write import Tx, acquire, new_doc, release, touch

ROOT = "30_projects"


def check_name(name):
    if not name or "/" in name or name.startswith(".") or name != name.strip() or "\n" in name:
        raise SbError(1, f"案件名に / ・先頭の . ・前後の空白は使えない: {name!r}")
    return name


def memo_rel(name, where="active"):
    return f"{ROOT}/{where}/{name}/メモ.md"


def locate(name):
    check_name(name)
    for where in ("active", "archive"):
        if (vault_root() / memo_rel(name, where)).is_file():
            return where
    return None


def _need_active(name):
    where = locate(name)
    if where is None:
        raise SbError(3, f"案件が無い: {name}")
    if where == "archive":
        raise SbError(4, f"archive の案件は読み取り専用。sb project reopen {name} で戻す")


def _edit(args, fn):
    _need_active(args.name)
    rel = memo_rel(args.name)
    with Tx("project", args.by, args.dry_run) as tx:
        meta, body = frontmatter.parse(tx.read(rel))
        body = fn(meta, body)
        tx.put(rel, frontmatter.dump(touch(meta, args.by), body))
        return {"name": args.name, "path": rel, "plan": tx.commit()}


def _paths(values):
    for v in values or []:
        if "," in v or not v.strip():
            raise SbError(1, f"パスに , は使えない: {v}")
    return "[" + ", ".join(values or []) + "]"


def new(args):
    check_name(args.name)
    if locate(args.name):
        raise SbError(1, f"その案件はもうある: {args.name}")
    purpose = (args.purpose or "").strip()
    if not purpose:
        raise SbError(1, "--purpose が空")
    frontmatter.check_section_text(purpose)
    rel = memo_rel(args.name)
    text = new_doc("project", args.by, 案件=args.name, 開始=str(today()), 目的=purpose,
                   関連repo=_paths(args.repo), 関連data=_paths(args.data))
    with Tx("project", args.by, args.dry_run) as tx:
        tx.read(rel)
        tx.put(rel, text)
        return {"name": args.name, "path": rel, "plan": tx.commit()}


def status(args):
    section = getattr(args, "section", "今の状態")
    if not (args.body or "").strip():
        raise SbError(1, f"{section}が空")
    return _edit(args, lambda meta, body: frontmatter.replace_section(body, section, args.body))


def meta(args):
    if args.start is None and args.repo is None and args.data is None:
        raise SbError(1, "--start・--repo・--data のどれかが要る")
    start = str(parse_date(args.start)) if args.start else None

    def fn(meta, body):
        if start:
            meta["開始"] = start
        if args.repo is not None:
            _paths(args.repo)
            meta["関連repo"] = list(args.repo)
        if args.data is not None:
            _paths(args.data)
            meta["関連data"] = list(args.data)
        return body
    return _edit(args, fn)


def log(args):
    text = " ".join((args.body or "").split())
    if not text:
        raise SbError(1, "--text が空")
    return _edit(args, lambda meta, body: frontmatter.append_to_section(body, "経緯", f"- {today()} {text}"))


def attach(args):
    _need_active(args.name)
    src = Path(args.file).expanduser().resolve()
    if workspace_root().resolve() not in src.parents:
        raise SbError(4, f"Workspace の外のファイルは置けない: {src}")
    if src.suffix != ".md" or not src.is_file():
        raise SbError(1, "資料/ に置けるのは md のファイルだけ（他は data/ に置き、メモからパスで参照）")
    name = args.as_name or src.stem
    if not re.fullmatch(r"[^/\\.][^/\\]*", name) or name.endswith(".md"):
        raise SbError(1, f"資料の名前に / や先頭の . は使えない（.md は付けない）: {name}")
    meta, body = frontmatter.parse(src.read_text(encoding="utf-8"))
    meta = {"形式": 1, "種類": "project", "案件": args.name, "資料": True, **{k: v for k, v in meta.items() if k not in ("形式", "種類", "案件", "資料")}}
    if not any(ln.startswith("# ") for ln in body.split("\n")):
        body = f"# {name}\n\n" + body
    rel = f"{ROOT}/active/{args.name}/資料/{name}.md"
    with Tx("project", args.by, args.dry_run) as tx:
        tx.read(rel)
        tx.put(rel, frontmatter.dump(touch(meta, args.by), body))
        return {"name": args.name, "path": rel, "plan": tx.commit()}


def close(args):
    _need_active(args.name)
    if args.result not in ("完了", "中止"):
        raise SbError(1, "--result は 完了 か 中止")
    text = (args.body or "").strip()
    if not text:
        raise SbError(1, "--text（結び）が空")
    frontmatter.check_section_text(text)
    busy = [m["ID"] for _, m in task.all_tasks() if m.get("案件") == args.name]
    if busy:
        raise SbError(1, f"進行中のタスクが紐づいている（先に片付ける）: {', '.join(busy)}")
    src = vault_root() / ROOT / "active" / args.name
    dst = vault_root() / ROOT / "archive" / args.name
    if dst.exists():
        raise SbError(1, f"archive に同じ名前がある: {args.name}")
    fd = acquire("project:" + args.name)
    try:
        def fn(meta, body):
            meta.update(状態=args.result, 終了=str(today()))
            current = frontmatter.get_section(body, "今の状態") or ""
            body = frontmatter.replace_section(body, "今の状態", f"**{args.result}（{today()}）**: {text}\n\n{current}")
            return frontmatter.append_to_section(body, "経緯", f"- {today()} {args.result}: {' '.join(text.split())}")
        result = _edit(args, fn)
        if not args.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.rename(src, dst)
    finally:
        release(fd)
    result["path"] = memo_rel(args.name, "archive")
    return result


def reopen(args):
    where = locate(args.name)
    if where is None:
        raise SbError(3, f"案件が無い: {args.name}")
    if where == "active":
        raise SbError(1, f"まだ active にある: {args.name}")
    src = vault_root() / ROOT / "archive" / args.name
    dst = vault_root() / ROOT / "active" / args.name
    if dst.exists():
        raise SbError(1, f"active に同じ名前がある: {args.name}")
    fd = acquire("project:" + args.name)
    try:
        if not args.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.rename(src, dst)
        if args.dry_run:
            return {"name": args.name, "path": memo_rel(args.name), "plan": [{"path": memo_rel(args.name), "action": "move"}]}
        try:
            def fn(meta, body):
                meta.update(状態="進行中", 終了="")
                return frontmatter.append_to_section(body, "経緯", f"- {today()} 再開")
            return _edit(args, fn)
        except SbError:
            os.rename(dst, src)  # メモが書けなければ archive へ戻す
            raise
    finally:
        release(fd)


def show(args):
    where = locate(args.name)
    if where is None:
        raise SbError(3, f"案件が無い: {args.name}")
    rel = memo_rel(args.name, where)
    tasks = [{"ID": m.get("ID"), "件名": m.get("件名"), "状態": m.get("状態"), "期限": m.get("期限"), "path": r}
             for r, m in task.all_tasks(include_archive=True) if m.get("案件") == args.name]
    return {"name": args.name, "where": where, "path": rel,
            "text": (vault_root() / rel).read_text(encoding="utf-8"), "tasks": tasks}


def list_projects(args):
    out = []
    for where in ("active", "archive") if args.all else ("active",):
        for memo in sorted((vault_root() / ROOT / where).glob("*/メモ.md")):
            try:
                meta, _ = frontmatter.parse(memo.read_text(encoding="utf-8"))
            except SbError:
                meta = {}
            out.append({"name": memo.parent.name, "where": where, "状態": meta.get("状態", ""),
                        "path": memo.relative_to(vault_root()).as_posix()})
    return {"projects": out}
