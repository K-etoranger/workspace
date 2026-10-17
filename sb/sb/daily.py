"""10_daily/YYYY/YYYY-MM-DD.md: その日の要約と出来事、本人像の変化。"""

from . import SbError, frontmatter
from .logical_day import date_arg
from .paths import vault_root
from .write import Tx, new_doc, touch

SECTIONS = ("今日の要約", "本人像の変化", "出来事", "使えた記録")


def rel_path(day):
    return f"10_daily/{day:%Y}/{day}.md"


def _load(tx, day, by):
    text = tx.read(rel_path(day)) or new_doc("daily", by, 論理日=day)
    return frontmatter.parse(text)


def put_section(tx, day, section, content, by):
    meta, body = _load(tx, day, by)
    tx.put(rel_path(day), frontmatter.dump(touch(meta, by), frontmatter.replace_section(body, section, content)))


def append_change(tx, day, line, by):
    """「本人像の変化」へ行を足す（sb identity set から呼ぶ。line は改行で複数行でもよい）。"""
    meta, body = _load(tx, day, by)
    tx.put(rel_path(day), frontmatter.dump(touch(meta, by), frontmatter.append_to_section(body, "本人像の変化", line)))


def write(args):
    if args.section not in SECTIONS:
        raise SbError(1, f"節は {'・'.join(SECTIONS)} のどれか: {args.section}")
    day = date_arg(args.date)
    with Tx("daily", args.by, args.dry_run) as tx:
        put_section(tx, day, args.section, args.body or "", args.by)
        return {"path": rel_path(day), "plan": tx.commit()}


def show(args):
    rel = rel_path(date_arg(args.date))
    p = vault_root() / rel
    if not p.exists():
        raise SbError(3, f"無い: {rel}")
    return {"path": rel, "text": p.read_text(encoding="utf-8")}
