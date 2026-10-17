"""40_tasks: 1タスク=1ファイル。進行中は active/、done・cancelled は archive/YYYY/MM/。"""

import hashlib
import re
from datetime import date, datetime, timedelta

from . import SbError, frontmatter
from .layers import TASK_ID_RE
from .logical_day import canonical_due, event_day, minute, parse_date, today
from .paths import vault_root
from .util import slug_ascii
from .write import Tx, new_doc, touch

STATES = ("open", "in_progress", "waiting", "needs_review", "done", "cancelled")
OWNERS = ("本人", "エージェント", "本人+エージェント")
TYPES = ("タスク", "予定")
PRIORITIES = ("高", "中", "低")
WEEKDAYS = "月火水木金土日"
REPEAT_RE = re.compile(r"毎日|毎週([月火水木金土日])|毎月([1-9]|[12][0-9]|3[01])日")
CANCEL_LIMIT = 3
ACTIVE = "40_tasks/active"
ARCHIVE = "40_tasks/archive"


# ---- 探す・読む ----

def check_id(tid):
    if not re.fullmatch(TASK_ID_RE, tid or ""):
        raise SbError(1, f"タスクIDは YYYYMMDD-英小文字・数字・ハイフン: {tid}")
    return tid


def active_rel(tid):
    return f"{ACTIVE}/{tid}.md"


def find(tid):
    """(相対パス, archive か) か None。"""
    check_id(tid)
    if (vault_root() / active_rel(tid)).exists():
        return active_rel(tid), False
    hits = sorted((vault_root() / ARCHIVE).glob(f"*/*/{tid}.md"))
    if hits:
        return hits[-1].relative_to(vault_root()).as_posix(), True
    return None


def all_tasks(include_archive=False):
    """[(相対パス, 頭書き)]。読めないファイル・読む途中で消えたファイルは飛ばす（sb check が見つける）。"""
    root = vault_root()
    paths = sorted((root / ACTIVE).glob("*.md"))
    if include_archive:
        paths += sorted((root / ARCHIVE).glob("*/*/*.md"))
    out = []
    for p in paths:
        try:
            meta, _ = frontmatter.parse(p.read_text(encoding="utf-8"))
        except (SbError, FileNotFoundError):
            continue
        if meta.get("種類") == "task":
            out.append((p.relative_to(root).as_posix(), meta))
    return out


# ---- 値の検査 ----

def _due(text):
    """期限・日時: 日付だけなら 23:59 を付ける。空はそのまま。"""
    text = (text or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        parse_date(text)
        return text + " 23:59"
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M").strftime("%Y-%m-%d %H:%M")
    except ValueError:
        raise SbError(1, f"日時は YYYY-MM-DD か YYYY-MM-DD HH:MM で: {text}")


def _at(text):
    """予定の開始・終了（日付だけでも可、23:59 は付けない）。"""
    text = (text or "").strip()
    if not text or re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) and parse_date(text):
        return text
    return _due(text)


def _repeat(text):
    if text and not REPEAT_RE.fullmatch(text):
        raise SbError(1, f"繰り返しは 毎日・毎週<曜>・毎月<N>日 のどれか: {text}")
    return text or ""


def _choice(value, choices, label):
    if value and value not in choices:
        raise SbError(1, f"{label}は {'・'.join(choices)} のどれか: {value}")
    return value or ""


def check_project(name):
    if name and not (vault_root() / "30_projects" / "active" / name / "メモ.md").is_file():
        raise SbError(3, f"案件が 30_projects/active に無い: {name}")
    return name or ""


def _history(body, text):
    return frontmatter.append_to_section(body, "経緯", f"- {minute()} {text}")


# ---- 作る ----

def _auto_id(title, day):
    slug = slug_ascii(title)[:40].strip("-") or "t" + hashlib.sha1(title.encode("utf-8")).hexdigest()[:6]
    base = f"{day:%Y%m%d}-{slug}"
    tid, n = base, 2
    while find(tid):
        tid, n = f"{base}-{n}", n + 1
    return tid


def new(args):
    title = " ".join((args.title or "").split())
    if not title:
        raise SbError(1, "件名が空")
    kind = _choice(args.type or "タスク", TYPES, "区分")
    fields = dict(
        区分=kind, 件名=title, 担当=_choice(args.owner, OWNERS, "担当"),
        期限=_due(args.due), 開始=_at(args.start), 終了=_at(args.end),
        優先度=_choice(args.priority, PRIORITIES, "優先度"), 見積=args.estimate or "",
        案件=check_project(args.project), 繰り返し=_repeat(args.repeat), 連続取消=0,
        出典=" ".join((args.source or "").split()), 作った物=args.by,
    )
    if kind == "予定" and not (fields["開始"] or fields["期限"]):
        raise SbError(1, "予定には --start か --due が要る")
    if args.id:
        tid = check_id(args.id)
        if find(tid):
            raise SbError(1, f"そのIDはもうある: {tid}")
    else:
        tid = _auto_id(title, today())
    frontmatter.check_section_text(args.body or "")
    text = new_doc("task", args.by, ID=tid, 内容=(args.body or "").strip(), 作成行=f"{minute()} 作成", **fields)
    rel = active_rel(tid)
    with Tx("task", args.by, args.dry_run) as tx:
        if tx.exists(rel):
            raise SbError(1, f"そのIDはもうある: {tid}")
        tx.put(rel, text)
        return {"id": tid, "path": rel, "plan": tx.commit()}


# ---- 変える ----

def _edit(args, fn):
    """active のタスクを読み、fn(meta, body) → body で変えて書く。"""
    found = find(args.id)
    if not found:
        raise SbError(3, f"タスクが無い: {args.id}")
    rel, archived = found
    if archived:
        raise SbError(4, f"終わったタスク（archive）は変えられない。sb task reopen {args.id} で戻す")
    with Tx("task", args.by, args.dry_run) as tx:
        meta, body = frontmatter.parse(tx.read(rel))
        body = fn(meta, body)
        tx.put(rel, frontmatter.dump(touch(meta, args.by), body))
        return {"id": args.id, "path": rel, "state": meta.get("状態"), "plan": tx.commit()}


def update(args):
    changes = {}
    if args.title is not None:
        changes["件名"] = " ".join(args.title.split())
        if not changes["件名"]:
            raise SbError(1, "件名が空")
    if args.due is not None:
        changes["期限"] = _due(args.due)
    if args.start is not None:
        changes["開始"] = _at(args.start)
    if args.end is not None:
        changes["終了"] = _at(args.end)
    if args.priority is not None:
        changes["優先度"] = _choice(args.priority, PRIORITIES, "優先度")
    if args.estimate is not None:
        changes["見積"] = args.estimate
    if args.project is not None:
        changes["案件"] = check_project(args.project)
    if args.owner is not None:
        changes["担当"] = _choice(args.owner, OWNERS, "担当")
    if args.repeat is not None:
        changes["繰り返し"] = _repeat(args.repeat)
    if not changes:
        raise SbError(1, "変える項目がない")

    def fn(meta, body):
        meta.update(changes)
        if "件名" in changes:
            body = re.sub(r"(?m)^# .*$", "# " + changes["件名"], body, count=1)
        return _history(body, "変更: " + "、".join(f"{k}={v}" for k, v in changes.items()))
    return _edit(args, fn)


def note(args):
    text = " ".join((args.body or "").split())
    if not text:
        raise SbError(1, "--text が空")
    return _edit(args, lambda meta, body: _history(body, text))


def _set_state(state, line, **extra):
    def fn(meta, body):
        meta["状態"] = state
        meta["待ち"] = extra.get("待ち", "")
        meta["次の確認"] = extra.get("次の確認", "")
        return _history(body, line)
    return fn


def start(args):
    return _edit(args, _set_state("in_progress", "着手"))


def wait(args):
    recheck = str(parse_date(args.recheck))
    what = " ".join((args.for_ or "").split())
    if not what:
        raise SbError(1, "--for が空")
    return _edit(args, _set_state("waiting", f"待ち: {what}（次の確認 {recheck}）", 待ち=what, 次の確認=recheck))


def review(args):
    text = " ".join((args.body or "").split())
    if not text:
        raise SbError(1, "--text が空（本人に確認してほしいこと）")
    return _edit(args, _set_state("needs_review", f"確認依頼: {text}"))


# ---- 終える・戻す ----

def _shift(value, days):
    if not value:
        return value
    d = parse_date(value[:10])
    return str(d + timedelta(days=days)) + value[10:]


def next_date(rule, base):
    if rule == "毎日":
        return base + timedelta(days=1)
    m = REPEAT_RE.fullmatch(rule)
    if m.group(1):
        wd = WEEKDAYS.index(m.group(1))
        return base + timedelta(days=(wd - base.weekday() - 1) % 7 + 1)
    day = int(m.group(2))
    y, mo = (base.year + 1, 1) if base.month == 12 else (base.year, base.month + 1)
    for d in range(day, 27, -1):
        try:
            return date(y, mo, d)
        except ValueError:
            continue
    return date(y, mo, day)


def _finish(args, state, line):
    found = find(args.id)
    if not found:
        raise SbError(3, f"タスクが無い: {args.id}")
    rel, archived = found
    if archived:
        raise SbError(4, f"もう終わっている（archive）: {args.id}")
    t = today()
    arel = f"{ARCHIVE}/{t:%Y}/{t:%m}/{args.id}.md"
    with Tx("task", args.by, args.dry_run, allow_readonly=[arel]) as tx:
        meta, body = frontmatter.parse(tx.read(rel))
        streak = int(meta.get("連続取消") or 0)
        rule = meta.get("繰り返し") or ""
        limit = int(meta.get("連続取消上限") or CANCEL_LIMIT)
        if state == "cancelled" and rule and streak >= limit:
            raise SbError(1, f"{limit}回続けて取り消したので、この回は取り消せない。終えたら sb task done {args.id}")
        meta["状態"] = state
        body = _history(body, line)
        tx.put(arel, frontmatter.dump(touch(meta, args.by), body))
        tx.delete(rel)
        result = {"id": args.id, "path": arel, "state": state}
        if rule:
            result["next"] = _next_instance(tx, args, args.id, meta, body, state, streak)
        result["plan"] = tx.commit()
        return result


def _next_instance(tx, args, tid, meta, body, state, streak, not_before=None):
    anchor = meta.get("期限") or meta.get("開始")
    base = parse_date(anchor[:10]) if anchor else today()
    nd = next_date(meta["繰り返し"], base)
    while not_before and nd < not_before:  # 止まっていた間の回は作らない
        nd = next_date(meta["繰り返し"], nd)
    days = (nd - base).days
    nid = re.sub(r"^\d{8}", f"{nd:%Y%m%d}", tid)
    if find(nid) or tx.exists(active_rel(nid)):
        return {"id": nid, "created": False, "reason": "次の回はもうある"}
    nmeta = dict(meta)
    nmeta.update(ID=nid, 状態="open", 期限=_shift(meta.get("期限", ""), days), 開始=_shift(meta.get("開始", ""), days),
                 終了=_shift(meta.get("終了", ""), days), 連続取消={"done": 0, "cancelled": streak + 1}.get(state, streak),
                 待ち="", 次の確認="", 作成=touch({}, "")["更新"])
    word = {"done": "完了", "cancelled": "取消"}.get(state, "日時が過ぎたので片付け")
    nbody = frontmatter.replace_section(body, "経緯", f"- {minute()} 作成（繰り返し: 前回 {tid} を{word}）")
    tx.put(active_rel(nid), frontmatter.dump(touch(nmeta, args.by), nbody))
    return {"id": nid, "created": True, "path": active_rel(nid), "連続取消": nmeta["連続取消"]}


def done(args):
    text = " ".join((args.body or "").split())
    return _finish(args, "done", "完了" + (f": {text}" if text else ""))


def cancel(args):
    reason = " ".join((args.reason or "").split())
    if not reason:
        raise SbError(1, "--reason が空")
    return _finish(args, "cancelled", f"取消: {reason}")


def reopen(args):
    found = find(args.id)
    if not found:
        raise SbError(3, f"タスクが無い: {args.id}")
    rel, archived = found
    if not archived:  # active の作業中・待ち・確認待ちを open に戻す
        with Tx("task", args.by, args.dry_run) as tx:
            meta, body = frontmatter.parse(tx.read(rel))
            if meta.get("状態") == "open":
                raise SbError(1, f"もう open: {args.id}")
            meta.update(状態="open", 待ち="", 次の確認="")
            tx.put(rel, frontmatter.dump(touch(meta, args.by), _history(body, "open に戻す")))
            return {"id": args.id, "path": rel, "state": "open", "plan": tx.commit()}
    with Tx("task", args.by, args.dry_run, allow_readonly=[rel]) as tx:
        meta, body = frontmatter.parse(tx.read(rel))
        meta.update(状態="open", 待ち="", 次の確認="")
        tx.put(active_rel(args.id), frontmatter.dump(touch(meta, args.by), _history(body, "再開")))
        tx.delete(rel)
        return {"id": args.id, "path": active_rel(args.id), "state": "open", "plan": tx.commit()}


def tidy(args):
    """日時を過ぎた予定を archive/<予定の年>/<月>/ へ移す（中身は書き換えない）。

    繰り返しの予定は、次の回（今日以降の最初の回）を active に作る。連続取消は増やさない。
    """
    before = parse_date(args.before) if args.before else today()
    moves = []
    for rel, meta in all_tasks():
        if meta.get("区分") != "予定":
            continue
        day = event_day(meta.get("終了") or meta.get("開始") or meta.get("期限"))
        if day and day < before:
            moves.append((rel, f"{ARCHIVE}/{day:%Y}/{day:%m}/{meta['ID']}.md"))
    with Tx("task", args.by, args.dry_run, allow_readonly=[a for _, a in moves]) as tx:
        created = []
        for rel, arel in moves:
            text = tx.read(rel)
            tx.put(arel, text)
            tx.delete(rel)
            meta, body = frontmatter.parse(text)
            if meta.get("繰り返し"):
                created.append(_next_instance(tx, args, meta["ID"], meta, body, "tidy",
                                              int(meta.get("連続取消") or 0), not_before=before))
        return {"moved": [m[0] for m in moves], "next": created, "plan": tx.commit()}


# ---- 出す ----

def show(args):
    found = find(args.id)
    if not found:
        raise SbError(3, f"タスクが無い: {args.id}")
    rel, archived = found
    return {"path": rel, "archived": archived, "text": (vault_root() / rel).read_text(encoding="utf-8")}


def list_tasks(args):
    out = []
    due_before = canonical_due(args.due_before) if args.due_before else None
    if args.due_before and due_before is None:
        raise SbError(1, f"--due-before は YYYY-MM-DD か YYYY-MM-DD HH:MM で: {args.due_before}")
    for rel, meta in all_tasks(args.all):
        if args.state and meta.get("状態") != args.state:
            continue
        if args.owner and meta.get("担当") != args.owner:
            continue
        if args.project and meta.get("案件") != args.project:
            continue
        if args.type and meta.get("区分") != args.type:
            continue
        if due_before:
            d = canonical_due(meta.get("期限"))
            if not d or d > due_before:
                continue
        out.append({"path": rel, "archived": rel.startswith(ARCHIVE), **meta})
    return {"tasks": out}
