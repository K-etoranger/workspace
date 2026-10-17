"""00_inbox: 連絡と会話の本文。1件=1見出し、同じ id は書かない。

読み手ごとの読み取り位置のために、受け付けた順番を data/sb/inbox/<ソース>.jsonl に持つ
（md より先に書くので、途中で止まっても「md にあるのに一覧に出ない」は起きない）。
"""

import json
import re

from . import SbError, frontmatter, guard, layers
from .logical_day import date_arg, item_day, parse_date, parse_iso
from .paths import find_named, sb_data, vault_root
from .util import hhmm, json_lines
from .write import Tx, acquire, atomic_write, new_doc, release, touch

ID_COMMENT = re.compile(r"^<!-- id: (.*?)(?: / 元データ: (.*?))? -->$")
MSG_HEAD = re.compile(r"^(\S+) (.*) — (.*?) → (self|other)$")


DIRS = ("messages", "conversations")
CONV_KEYS = ("本人", "返答", "会話ID")


def _dir(source, items=()):
    """ソースの置き場（messages か conversations）。既にあればそこ、無ければ件の形（本人・返答・会話ID があれば会話）から。"""
    layers.check_name(source, "ソース名")
    have = [d for d in DIRS if (vault_root() / "00_inbox" / d / source).is_dir()]
    if len(have) > 1:
        raise SbError(1, f"ソース {source} が messages と conversations の両方にある")
    if have:
        return have[0]
    return "conversations" if any(k in it for it in items for k in CONV_KEYS) else "messages"


def rel_path(kind, source, day):
    return f"00_inbox/{kind}/{source}/{day}.md"


def _esc(text):
    out = []
    for line in str(text).replace("\r\n", "\n").split("\n"):
        out.append("\\" + line if line.startswith(("#", "<!--", "\\")) else line)
    return "\n".join(out).strip("\n")


def _unesc(lines):
    return "\n".join(ln[1:] if ln.startswith("\\") else ln for ln in lines).strip("\n")


def _check_id(item):
    iid = str(item.get("id", "")).strip()
    if not iid or "\n" in iid or "-->" in iid or " / " in iid:
        raise SbError(1, f"id が無いか使えない文字を含む: {iid[:40]!r}")
    return iid


def _block(kind, source, item):
    iid = _check_id(item)
    if kind == "conversations":
        allowed = {"id", "時刻", "会話ID", "本人", "返答"}
        bad = set(item) - allowed
        if bad:
            raise SbError(1, f"会話の項目に無い名前: {', '.join(sorted(bad))}")
        conv = str(item.get("会話ID") or iid.split(":")[0])
        return "\n".join([f"## {hhmm(item.get('時刻'))} {conv[:8]}", f"<!-- id: {iid} -->",
                          "### 山田", _esc(item.get("本人", "")), f"### {source.capitalize()}", _esc(item.get("返答", ""))])
    allowed = {"id", "時刻", "相手", "場所", "向き", "本文", "元データ"}
    bad = set(item) - allowed
    if bad:
        raise SbError(1, f"項目に無い名前: {', '.join(sorted(bad))}")
    if item.get("向き") not in ("self", "other"):
        raise SbError(1, f"向き は self か other: {iid}")
    place = " ".join(str(item.get("場所", "")).split()) or "-"
    who = " ".join(str(item.get("相手", "")).split()) or "-"
    comment = f"<!-- id: {iid}" + (f" / 元データ: {item['元データ']}" if item.get("元データ") else "") + " -->"
    return "\n".join([f"## {hhmm(item.get('時刻'))} {place} — {who} → {item['向き']}", comment, _esc(item.get("本文", ""))])


def parse_items(kind, text):
    """md → 件の一覧（dict）。kind = messages か conversations。"""
    _, body = frontmatter.parse(text)
    conv = kind == "conversations"
    items, cur = [], None
    for line in body.split("\n"):
        if line.startswith("## "):
            cur = {"見出し": line[3:], "lines": []}
            items.append(cur)
        elif cur is not None:
            cur["lines"].append(line)
    out = []
    for it in items:
        lines = it["lines"]
        m = ID_COMMENT.match(lines[0]) if lines else None
        if not m:
            continue
        rec = {"id": m.group(1)}
        if conv:
            t, _, cid = it["見出し"].partition(" ")
            rec.update({"時刻": t, "会話ID": cid})
            parts, key = {"本人": [], "返答": []}, None
            for ln in lines[1:]:
                if ln == "### 山田":
                    key = "本人"
                elif ln.startswith("### ") and key == "本人":
                    key = "返答"
                elif key:
                    parts[key].append(ln)
            rec.update({k: _unesc(v) for k, v in parts.items()})
        else:
            h = MSG_HEAD.match(it["見出し"])
            if h:
                rec.update({"時刻": h.group(1), "場所": h.group(2), "相手": h.group(3), "向き": h.group(4)})
            if m.group(2):
                rec["元データ"] = m.group(2)
            rec["本文"] = _unesc(lines[1:])
        out.append(rec)
    return out


def _index_path(source):
    return sb_data() / "inbox" / f"{source}.jsonl"


def _indexed_sources():
    base = sb_data() / "inbox"
    return sorted(p.relative_to(base).with_suffix("").as_posix() for p in base.rglob("*.jsonl")) if base.is_dir() else []


def _read_index(source):
    p = _index_path(source)
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").split("\n") if ln.strip()]


def add(args):
    """件ごとに論理日を決めて（--date が無ければ時刻と --at から）日ごとのファイルへ書く。1件でも日が決まらなければ何も書かない。"""
    items = json_lines(args.body)
    kind = _dir(args.source, items)
    fixed = parse_date(args.date) if args.date else None
    at = parse_iso(args.at) if args.at else None
    by_day, masked = {}, []
    for it in items:
        iid = _check_id(it)
        block, hits = guard.mask(_block(kind, args.source, it))
        if hits:
            masked.append({"id": iid, "伏せた": hits})
        by_day.setdefault(item_day(it.get("時刻"), fixed, at), []).append((iid, block))
    total = sum(len(v) for v in by_day.values())
    paths, days, added = [], {}, []
    with Tx("inbox", args.by, args.dry_run) as tx:
        for day in sorted(by_day):
            rel = rel_path(kind, args.source, day)
            paths.append(rel)
            text = tx.read(rel)
            if text is None:
                tmpl = "conversation" if kind == "conversations" else "inbox"
                text = new_doc(tmpl, args.by, ソース=args.source, 論理日=day, 題名=f"{args.source} {day}")
            meta, body = frontmatter.parse(text)
            have = {it["id"] for it in parse_items(kind, text)}
            n = 0
            for iid, block in by_day[day]:
                if iid in have:
                    continue
                have.add(iid)
                added.append((iid, day))
                n += 1
                body = body.rstrip("\n") + "\n\n" + block + "\n"
            days[str(day)] = n
            if n:
                meta["会話数" if "会話数" in meta else "件数"] = len(have)
                touch(meta, args.by)
                tx.put(rel, frontmatter.dump(meta, body))
        plan = tx.commit(before_apply=lambda: _append_index(args.source, added)) if added else []
    result = {"paths": paths, "days": days, "added": len(added), "skipped": total - len(added), "masked": masked, "plan": plan}
    if len(paths) == 1:
        result["path"] = paths[0]
    return result


def _append_index(source, pairs):
    """pairs = [(id, 論理日)]。"""
    fd = acquire("data:inbox:" + source)
    try:
        rows = _read_index(source)
        known = {r["id"] for r in rows}
        seq = rows[-1]["seq"] if rows else 0
        for iid, day in pairs:
            if iid not in known:
                known.add(iid)
                seq += 1
                rows.append({"seq": seq, "id": iid, "date": str(day)})
        atomic_write(_index_path(source), "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    finally:
        release(fd)


def _checkpoint_path(reader):
    if not re.fullmatch(r"[A-Za-z0-9_.\-]+", reader or ""):
        raise SbError(1, f"読み手名は英数字・_-. だけ: {reader}")
    return sb_data() / "checkpoints" / f"{reader}.json"


def _checkpoint(reader):
    p = _checkpoint_path(reader)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def list_items(args):
    kind = _dir(args.source)
    pos = _checkpoint(args.since).get(args.source, 0) if args.since else 0
    cache, out = {}, []
    for row in _read_index(args.source):
        if row["seq"] <= pos:
            continue
        if row["date"] not in cache:
            p = vault_root() / rel_path(kind, args.source, row["date"])
            cache[row["date"]] = {it["id"]: it for it in parse_items(kind, p.read_text(encoding="utf-8"))} if p.exists() else {}
        item = cache[row["date"]].get(row["id"])
        if item:
            out.append({"source": args.source, "date": row["date"], "seq": row["seq"], **item})
    return {"items": out}


def ack(args):
    path = _checkpoint_path(args.reader)
    srcs = [layers.check_name(args.source, "ソース名")] if args.source else _indexed_sources()
    found = [(s, r["seq"]) for s in srcs for r in _read_index(s) if r["id"] == args.until]
    if not found:
        raise SbError(3, f"その id は inbox に無い: {args.until}")
    if len(found) > 1:
        raise SbError(1, "その id は複数のソースにある。--source で指定してください")
    source, seq = found[0]
    fd = acquire("data:checkpoint:" + args.reader)
    try:
        cp = _checkpoint(args.reader)
        moved = seq > cp.get(source, 0)
        if moved and not args.dry_run:
            cp[source] = seq
            atomic_write(path, json.dumps(cp, ensure_ascii=False, indent=1) + "\n")
    finally:
        release(fd)
    return {"reader": args.reader, "source": source, "seq": seq, "moved": moved}


def show(args):
    day = date_arg(args.date)
    if not args.source:
        out = {}
        for kind in DIRS:
            for name, rel, text in find_named(f"00_inbox/{kind}", f"{day}.md"):
                out[name] = {"dir": kind, "path": rel, "items": parse_items(kind, text)}
        return {"date": str(day), "sources": out}
    rel = rel_path(_dir(args.source), args.source, day)
    p = vault_root() / rel
    if not p.exists():
        raise SbError(3, f"無い: {rel}")
    text = p.read_text(encoding="utf-8")
    return {"path": rel, "text": text, "items": parse_items(_dir(args.source), text)}
