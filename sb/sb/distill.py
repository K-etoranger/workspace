"""60_distilled/<ソース>/YYYY-MM-DD.md: ソースごとの蒸留。テンプレートの節ごとに置き換える。"""

from . import SbError, frontmatter, layers
from .logical_day import date_arg
from .paths import find_named, vault_root
from .write import Tx, new_doc, required_headings, touch


def rel_path(source, day):
    return f"60_distilled/{layers.check_name(source, 'ソース名')}/{day}.md"


def write(args):
    day = date_arg(args.date)
    rel = rel_path(args.source, day)
    parts = frontmatter.split_sections(args.body or "")
    names = required_headings("distilled")
    bad = [k for k in parts if k not in names]
    if bad:
        raise SbError(1, f"蒸留の節に無い名前: {'・'.join(bad)}（節: {'・'.join(names)}）")
    text = new_doc("distilled", args.by, ソース=args.source, 論理日=day, 題名=f"{args.source} の蒸留 {day}",
                   読んだ件数=args.read_count or 0, 採用=args.adopted or 0)
    meta, body = frontmatter.parse(text)
    for name, content in parts.items():
        body = frontmatter.replace_section(body, name, content)
    with Tx("distill", args.by, args.dry_run) as tx:
        tx.read(rel)
        tx.put(rel, frontmatter.dump(meta, body))
        return {"path": rel, "plan": tx.commit()}


def show(args):
    if not args.source:
        day = date_arg(args.date)
        found = find_named("60_distilled", f"{day}.md")
        return {"date": str(day), "sources": {n: {"path": rel, "text": text} for n, rel, text in found}}
    rel = rel_path(args.source, date_arg(args.date))
    p = vault_root() / rel
    if not p.exists():
        raise SbError(3, f"無い: {rel}")
    return {"path": rel, "text": p.read_text(encoding="utf-8")}
