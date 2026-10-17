"""50_media: 見た・聴いた・いいねした履歴（日別の表）と現在値（current.md）。"""

from . import SbError, frontmatter, guard, layers
from .logical_day import date_arg, item_day, parse_date, parse_iso, today
from .paths import find_named, vault_root
from .util import day_hhmm, hhmm, json_lines, table, table_row, table_rows
from .write import Tx, new_doc, touch


def _kind(name):
    return layers.kind_spec(name)


def _keys(items):
    """列を決めていない種類の列: 受け取った JSON のキー（出てきた順）。"""
    return list(dict.fromkeys(k for it in items for k in it))


def _header(body):
    lines = [ln for ln in body.split("\n") if ln.startswith("|")]
    return [c.strip() for c in lines[0].strip("|").split(" | ")] if lines else None


def _row(spec, item, columns, fmt=hhmm):
    bad = set(item) - set(columns)
    if bad:
        raise SbError(1, f"列に無い項目: {', '.join(sorted(bad))}（列: {', '.join(columns)}）")
    return [fmt(item[c]) if c == "時刻" and item.get(c) else item.get(c, "") for c in columns]


def add(args):
    """日別の種類は件ごとに論理日を決めて（--date が無ければ時刻と --at から）日ごとのファイルへ書く。"""
    spec = _kind(args.kind)
    items = json_lines(args.body)
    if not spec.get("daily"):
        raise SbError(1, f"{args.kind} は日別の履歴を持たない（sb media current を使う）")
    fixed = parse_date(args.date) if args.date else None
    at = parse_iso(args.at) if args.at else None
    by_day, masked = {}, []
    for n, it in enumerate(items, 1):
        by_day.setdefault(item_day(it.get("時刻"), fixed, at), []).append((n, it))
    paths, days = [], {}
    with Tx("media", args.by, args.dry_run) as tx:
        for day in sorted(by_day):
            rel = f"50_media/{args.kind}/{day}.md"
            paths.append(rel)
            text = tx.read(rel)
            cols = spec.get("columns") or (text and _header(frontmatter.parse(text)[1])) or _keys(items)
            text = text or new_doc("media-daily", args.by, メディア=args.kind, 論理日=day,
                                   題名=f"{spec['label']} {day}", 表=table(cols, []))
            meta, body = frontmatter.parse(text)
            rows = table_rows(body)
            new = []
            for n, it in by_day[day]:
                row, hits = guard.mask(table_row(_row(spec, it, cols)))
                if hits:
                    masked.append({"line": n, "伏せた": hits})
                new.append(row)
            added = [r for r in dict.fromkeys(new) if r not in rows]
            days[str(day)] = len(added)
            if added:
                meta["件数"] = len(rows) + len(added)
                tx.put(rel, frontmatter.dump(touch(meta, args.by), _replace_table(body, cols, rows + added)))
        total = sum(days.values())
        result = {"paths": paths, "days": days, "added": total, "masked": masked, "plan": tx.commit() if total else []}
    if len(paths) == 1:
        result["path"] = paths[0]
    return result


def _replace_table(body, cols, rows):
    """本文の最初の表を置き換える（無ければ末尾に足す）。"""
    lines = body.rstrip("\n").split("\n")
    idx = [i for i, ln in enumerate(lines) if ln.startswith("|")]
    new = table(cols, []).split("\n") + rows
    if not idx:
        return "\n".join(lines + [""] + new) + "\n"
    start = idx[0]
    end = start
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    return "\n".join(lines[:start] + new + lines[end:]) + "\n"


def current(args):
    spec = _kind(args.kind)
    if not spec.get("has_current"):
        raise SbError(1, f"{args.kind} は現在値（current.md）を持たない")
    items = json_lines(args.body)
    cols = spec.get("current_columns") or spec.get("columns") or _keys(items)
    rows = [_row(spec, it, cols, day_hhmm) for it in items]  # 一覧は日付も残す
    total = args.total if args.total is not None else len(rows)
    rel = f"50_media/{args.kind}/current.md"
    text = new_doc("media-current", args.by, メディア=args.kind, 総数=total,
                   題名=f"{spec['label']} 現在の一覧", 表=table(cols, rows))
    with Tx("media", args.by, args.dry_run) as tx:
        tx.read(rel)
        tx.put(rel, text)
        return {"path": rel, "rows": len(rows), "total": total, "plan": tx.commit()}


def show(args):
    if not args.kind:
        day = date_arg(args.date) if args.date else None
        found = find_named("50_media", f"{day}.md" if day else "current.md")
        return {"date": str(day) if day else None, "kinds": {n: {"path": rel, "text": text} for n, rel, text in found}}
    spec = _kind(args.kind)
    if args.date or not spec.get("has_current"):
        rel = f"50_media/{args.kind}/{date_arg(args.date) if args.date else today()}.md"
    else:
        rel = f"50_media/{args.kind}/current.md"
    p = vault_root() / rel
    if not p.exists():
        raise SbError(3, f"無い: {rel}")
    return {"path": rel, "text": p.read_text(encoding="utf-8")}
