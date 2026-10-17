"""画面: NOW.md・40_tasks/タスク.base・README.md を作り直す。タスクのファイルは読むだけ。"""

from datetime import timedelta

from . import layers, task
from .logical_day import canonical_due, day_end_exclusive, event_day, now, today
from .util import table
from .write import Tx, new_doc

ACTIONABLE = ("open", "in_progress", "needs_review")


def _line(rel, m):
    link = f"[[{rel[:-3]}|{m.get('件名', m.get('ID'))}]]"
    parts = [f"期限 {m['期限']}" if m.get("期限") else "",
             f"開始 {m['開始']}" if m.get("開始") else "",
             m.get("担当", ""), m.get("見積", "")]
    return f"- {link} — " + " / ".join(p for p in parts if p) if any(parts) else f"- {link}"


def now_sections():
    t, current = today(), now()
    today_end, tomorrow_end = day_end_exclusive(t), day_end_exclusive(t + timedelta(days=1))
    s = {k: [] for k in ("今日の予定", "期限切れ", "今日まで", "明日まで", "本人の確認待ち", "待ち", "作業中")}
    for rel, m in task.all_tasks():
        state = m.get("状態")
        if m.get("区分") == "予定":
            if event_day(m.get("開始") or m.get("期限")) == t:
                s["今日の予定"].append((str(m.get("開始") or m.get("期限")), rel, m))
            continue
        due = canonical_due(m.get("期限"))
        if due and state in ACTIONABLE:
            key = "期限切れ" if due <= current else "今日まで" if due <= today_end else "明日まで" if due <= tomorrow_end else None
            if key:
                s[key].append((str(due), rel, m))
        if state == "needs_review":
            s["本人の確認待ち"].append((str(due or ""), rel, m))
        if state == "waiting" and m.get("次の確認") and str(m["次の確認"]) <= str(t):
            s["待ち"].append((str(m["次の確認"]), rel, m))
        if state == "in_progress":
            s["作業中"].append((str(due or ""), rel, m))
    return {k: "\n".join(_line(r, m) for _, r, m in sorted(v, key=lambda x: x[0])) or "- なし" for k, v in s.items()}


BASE = """filters:
  and:
    - file.inFolder("40_tasks/active")
    - 'note["種類"] == "task"'
views:
  - type: table
    name: 今日
    filters:
      and:
        - 'note["区分"] == "タスク"'
        - 'note["状態"] != "waiting"'
        - 'note["期限"]'
        - 'note["期限"].toString().slice(0, 10) <= today().format("YYYY-MM-DD")'
    groupBy:
      property: 案件
      direction: ASC
    order:
      - 件名
      - 状態
      - 期限
      - 担当
      - 見積
    sort:
      - property: 期限
        direction: ASC
  - type: table
    name: タスク
    filters:
      and:
        - 'note["区分"] == "タスク"'
    order:
      - 件名
      - 状態
      - 期限
      - 担当
      - 見積
      - 案件
    sort:
      - property: 期限
        direction: ASC
  - type: table
    name: 予定
    filters:
      and:
        - 'note["区分"] == "予定"'
    order:
      - 件名
      - 開始
      - 終了
      - 状態
      - 案件
    sort:
      - property: 開始
        direction: ASC
  - type: table
    name: 案件別
    groupBy:
      property: 案件
      direction: ASC
    order:
      - 件名
      - 区分
      - 状態
      - 期限
      - 担当
"""


def readme_values():
    d = layers.load_layers()
    rows = [[name, v["what"], v["unit"]] for name, v in d["layers"].items()]
    files = [[f"`{v['path']}`", v["kind"], "sb " + " / sb ".join(v["cmd"].split()), "読み取り専用" if v.get("readonly") else ""]
             for v in d["files"].values()]
    items = "\n".join([
        "- 層の中のファイル名（00_inbox と 60_distilled のソース・50_media の種類・20_identity のファイル）は決めていない。英小文字・数字・_・-・/ の名前なら何でも置ける。",
        "- 50_media で表の列を決めてある種類: " + "・".join(f"{k}{'（＋current）' if v.get('has_current') else ''}" for k, v in d["media"]["kinds"].items()) + "。ほかの種類の列は、受け取った項目の名前。",
        "- 90_logs の種類: " + "・".join(d["logs"]["kinds"]),
    ])
    return dict(層の表=table(["層", "何を置くか", "単位"], rows),
                置き場の表=table(["パス", "種類", "書くコマンド", ""], files), 項目=items)


def refresh(args):
    t = today()
    now_text = new_doc("now", args.by, 論理日=t, **now_sections())
    readme = new_doc("readme", args.by, **readme_values())
    with Tx("views", args.by, args.dry_run) as tx:
        for rel, text in (("NOW.md", now_text), ("40_tasks/タスク.base", BASE), ("README.md", readme)):
            old = tx.read(rel)
            if old is not None and _same_but_stamp(old, text):
                continue
            tx.put(rel, text)
        return {"paths": ["NOW.md", "40_tasks/タスク.base", "README.md"], "plan": tx.commit()}


def _same_but_stamp(old, new):
    """更新時刻だけの違いなら書かない。"""
    strip = lambda s: "\n".join(ln for ln in s.split("\n") if not ln.startswith("更新: "))
    return strip(old) == strip(new)

