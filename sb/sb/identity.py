"""20_identity: 今の本人（最新だけ）。節を置き換え、同じ日の 10_daily に「何を・なぜ」を残す。"""

from . import SbError, daily, frontmatter, layers
from .logical_day import today
from .paths import find_named, vault_root
from .write import Tx, new_doc, touch


def rel_path(name):
    return f"20_identity/{layers.check_name(name, 'ファイル名')}.md"


def _lines(text):
    """比べる単位の行: 前後の空白を除き、空行は捨て、行頭の箇条書き `- ` を外す。"""
    out = []
    for ln in (text or "").split("\n"):
        ln = ln.strip()
        ln = ln[2:].strip() if ln.startswith("- ") else ln
        if ln:
            out.append(ln)
    return list(dict.fromkeys(out))


def _diff(file, section, before, after, why):
    """10_daily「本人像の変化」へ書く行: 消した→足した（それぞれ元の順）。差が無ければ空。"""
    old, new = _lines(before), _lines(after)
    name = file if section == "今の状態" else f"{file}（{section}）"
    out = [f"- {name}: 消した「{ln}」" for ln in old if ln not in new]
    out += [f"- {name}: 足した「{ln}」" for ln in new if ln not in old]
    return out + ([f"- {file}: 理由: {why}"] if out and why else [])


def set_section(args):
    rel = rel_path(args.file)
    why = " ".join((args.why or "").split())
    section = (args.section or "").strip()
    if not section or "〈" in section:
        raise SbError(1, "--section が空")
    with Tx("identity", args.by, args.dry_run) as tx:
        text = tx.read(rel) or new_doc("identity", args.by, ファイル=args.file, 題名=args.file)
        meta, body = frontmatter.parse(text)
        allowed = set(frontmatter.headings(body)) | {"今の状態", "根拠の出どころ"}
        if section not in allowed:
            raise SbError(1, f"節「{section}」が無い（あるのは: {'・'.join(sorted(allowed))}）")
        new_body = frontmatter.replace_section(body, section, args.body or "")
        lines = _diff(args.file, section, frontmatter.get_section(body, section),
                      frontmatter.get_section(new_body, section), why)
        if new_body == body:  # 中身が同じなら何も書かない
            return {"path": rel, "daily": None, "changes": [], "plan": []}
        tx.put(rel, frontmatter.dump(touch(meta, args.by), new_body))
        if lines:  # 並べ替えだけなど、足した・消した行が無ければ 10_daily には書かない
            daily.append_change(tx, today(), "\n".join(lines), args.by)
        return {"path": rel, "daily": daily.rel_path(today()) if lines else None, "changes": lines, "plan": tx.commit()}


def show(args):
    if not args.file:
        return {"files": {n: {"path": rel, "text": text} for n, rel, text in find_named("20_identity")}}
    rel = rel_path(args.file)
    p = vault_root() / rel
    if not p.exists():
        raise SbError(3, f"無い: {rel}")
    return {"path": rel, "text": p.read_text(encoding="utf-8")}
