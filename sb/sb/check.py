"""sb check: vault の全ファイルの形を調べ、90_logs/check/<日付>.md に書く。--fix は頭書きの補完だけ。"""

from . import SbError, frontmatter, layers
from .logical_day import date_arg
from .paths import vault_root
from .util import table
from .write import Tx, new_doc, required_headings, touch

SKIP_DIRS = {".git", ".obsidian", ".trash"}
HEADER_ONLY = {"頭書きが無い", "頭書きに 形式 が無い", "頭書きに 種類 が無い", "頭書きの書き方が古い"}
OLD_FORM = "頭書きの書き方が古い"


def _files():
    root = vault_root()
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if p.is_dir() or any(part in SKIP_DIRS or part.startswith(".") for part in rel.parts):
            continue  # 隠しファイル（書きかけの一時ファイルを含む）は見ない
        yield rel.as_posix(), p


def inspect(rel, text, spec):
    """(崩れの一覧, 直せる頭書き or None)。"""
    problems = []
    try:
        meta, body = frontmatter.parse(text)
    except SbError as e:
        return [f"頭書きが読めない: {e}"], None
    fixed = None
    if not meta:
        problems.append("頭書きが無い")
    else:
        if meta.get("形式") is None:
            problems.append("頭書きに 形式 が無い")
        if not meta.get("種類"):
            problems.append("頭書きに 種類 が無い")
        elif meta["種類"] != spec["kind"]:
            problems.append(f"種類が {meta['種類']}（{spec['kind']} のはず）")
    if meta.get("形式") is None or not meta.get("種類"):
        rest = {k: v for k, v in meta.items() if k not in ("形式", "種類")}
        fixed = {"形式": 1, "種類": meta.get("種類") or spec["kind"], **rest}
    elif meta and frontmatter.dump(meta, body) != text:
        problems.append(OLD_FORM)  # 中身は同じで、今の書き方（YAML として読める形）と違う
        fixed = meta
    if not any(ln.startswith("# ") for ln in body.split("\n")):
        problems.append("題名（# 行）が無い")
    have = frontmatter.headings(body)
    missing = [h for h in required_headings(spec.get("template")) if h not in have]
    if missing:
        problems.append("見出しが無い: " + "・".join(missing))
    return problems, (fixed, body) if fixed else None


def run(args):
    day = date_arg(args.date)
    log_rel = f"90_logs/check/{day}.md"
    rows, checked = [], 0
    for rel, path in _files():
        found = layers.match_file(rel)
        if not found:
            rows.append([rel, "置き場所が決まりにない" if rel.endswith(".md") else "md 以外のファイル", "いいえ"])
            continue
        if not rel.endswith(".md") or rel == log_rel:
            continue
        checked += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        problems, fix = inspect(rel, text, found[1])
        if not problems:
            continue
        done = "いいえ"
        if args.fix and fix:
            meta, body = fix
            try:
                with Tx("check", args.by, args.dry_run, header_fix=True) as tx:
                    tx.read(rel)
                    # 書き方だけの直しは 更新・書いた物 を変えない
                    tx.put(rel, frontmatter.dump(meta if problems == [OLD_FORM] else touch(meta, args.by), body))
                    tx.commit()
                done = ("書き方を直した" if problems == [OLD_FORM] else "頭書きを補完") + ("（dry-run）" if args.dry_run else "")
            except SbError as e:
                done = f"直せない（{e.code}）"
        rows.append([rel, "／".join(problems), done])
    remaining = [r for r in rows if not (r[2].startswith(("頭書きを補完", "書き方を直した")) and all(p in HEADER_ONLY for p in r[1].split("／")))]
    text = new_doc("log-check", args.by, 論理日=day, 件数=len(rows))
    meta, body = frontmatter.parse(text)
    body = frontmatter.replace_section(body, "崩れの一覧", table(["パス", "何が崩れているか", "直したか"], rows) if rows else "崩れなし")
    with Tx("check", args.by, args.dry_run) as tx:
        tx.read(log_rel)
        tx.put(log_rel, frontmatter.dump(meta, body))
        plan = tx.commit()
    return {"path": log_rel, "checked": checked, "problems": [dict(zip(("path", "problem", "fixed"), r)) for r in rows],
            "remaining": len(remaining), "plan": plan, "_exit": 1 if remaining else 0}
