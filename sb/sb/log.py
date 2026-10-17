"""90_logs: audits（作成のみ）・schedule（追記）・handoff（1行追記）。"""

import re

from . import SbError, frontmatter
from .logical_day import date_arg, minute
from .write import Tx, new_doc, touch

NAME_RE = r"[A-Za-z0-9][A-Za-z0-9_.\-]*"


def _name(value, label):
    if not re.fullmatch(NAME_RE, value or ""):
        raise SbError(1, f"{label}は英数字・_-. だけ: {value}")
    return value


def audit(args):
    day = date_arg(args.date)
    name = _name(args.name, "監査名")
    rel = f"90_logs/audits/{name}/{day}.md"
    with Tx("log", args.by, args.dry_run) as tx:
        if tx.exists(rel):
            raise SbError(1, f"同じ日の監査結果はもうある（上書きしない）: {rel}")
        tx.put(rel, new_doc("log-audit", args.by, 監査名=name, 論理日=day, 本文=(args.body or "").strip()))
        return {"path": rel, "plan": tx.commit()}


def schedule(args):
    name = _name(args.task, "定時処理名")
    rel = f"90_logs/schedule/{name}.md"
    text = (args.body or "").strip()
    if not text:
        raise SbError(1, "--text が空")
    frontmatter.check_section_text(text)
    with Tx("log", args.by, args.dry_run) as tx:
        meta, body = frontmatter.parse(tx.read(rel) or new_doc("log-schedule", args.by, 定時処理=name))
        body = body.rstrip("\n") + f"\n\n## {minute()}\n{text}\n"
        tx.put(rel, frontmatter.dump(touch(meta, args.by), body))
        return {"path": rel, "plan": tx.commit()}


def handoff(args):
    if args.agent not in ("claude", "codex"):
        raise SbError(1, "--agent は claude か codex")
    text = " ".join((args.body or "").split())
    if not text:
        raise SbError(1, "--text が空")
    rel = "90_logs/handoff.md"
    with Tx("log", args.by, args.dry_run) as tx:
        meta, body = frontmatter.parse(tx.read(rel) or new_doc("handoff", args.by))
        body = body.rstrip("\n") + f"\n- {minute()} [{args.agent}] {text}\n"
        tx.put(rel, frontmatter.dump(touch(meta, args.by), body))
        return {"path": rel, "plan": tx.commit()}
