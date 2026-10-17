"""sb <対象> <動作> [オプション]。終了コード: 0 成功 / 1 形の誤り / 2 ロック / 3 対象なし / 4 書き込み拒否 / 5 内部の誤り。"""

import argparse
import json
import sys
from pathlib import Path

from . import FORMAT, VERSION, SbError
from .paths import workspace_root

class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SbError(1, f"{self.prog}: {message}")


def _common():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--json", action="store_true", help="結果を JSON で出す")
    p.add_argument("--dry-run", action="store_true", help="書かずに、書く予定の内容と検証結果だけを出す")
    return p


def _writer():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--by", required=True, help="書いた物。repo の処理は <repo名>/<処理>（importer/talk・sb/tidy）、人・エージェントが直接書くときは 本人・claude・codex")
    return p


def _text():
    p = argparse.ArgumentParser(add_help=False)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--text", help="本文")
    g.add_argument("--stdin", action="store_true", help="本文を標準入力から読む")
    g.add_argument("--file", dest="input_file", help="本文のファイル（Workspace 内だけ）")
    return p


def build_parser():
    C, W, T = _common(), _writer(), _text()
    root = Parser(prog="sb", description="SecondBrain の唯一の書き込み口。")
    sub = root.add_subparsers(dest="target", metavar="<対象>")
    sub.required = True

    def group(name, help_):
        g = sub.add_parser(name, help=help_)
        s = g.add_subparsers(dest="action", metavar="<動作>")
        s.required = True
        return s

    def cmd(s, name, func, help_, write=False, text=False):
        parents = [C] + ([W] if write else []) + ([T] if text else [])
        p = s.add_parser(name, help=help_, parents=parents)
        p.set_defaults(func=func)
        return p

    from . import check, daily, distill, identity, inbox, log, logical_day, media, project, task, views

    s = group("inbox", "00_inbox（連絡と会話）")
    p = cmd(s, "add", inbox.add, "JSON 行をその日のファイルへ追記（同じ id は書かない）", True, True)
    p.add_argument("--source", required=True)
    p.add_argument("--date", help="全件をこの論理日に書く（省くと件ごとの時刻から決める）")
    p.add_argument("--at", help="日付の無い件（HH:MM・空）の基準にする取得時刻（タイムゾーン付き ISO）")
    p = cmd(s, "list", inbox.list_items, "読み取り位置より後の件を JSON で出す")
    p.add_argument("--source", required=True)
    p.add_argument("--since", help="読み手名（その読み取り位置より後）")
    p = cmd(s, "ack", inbox.ack, "読み手の読み取り位置を進める")
    p.add_argument("--reader", required=True)
    p.add_argument("--until", required=True, help="ここまで読んだ id")
    p.add_argument("--source", help="同じ id が複数のソースにあるときだけ")
    p.add_argument("--by", help="（任意）")
    p = cmd(s, "show", inbox.show, "その日のファイルを出す（--source を省くと、その日の全ソース）")
    p.add_argument("--source")
    p.add_argument("--date")

    s = group("media", "50_media（見た・聴いた・いいねした履歴）")
    p = cmd(s, "add", media.add, "その日の履歴へ追記（JSON 行）", True, True)
    p.add_argument("--kind", required=True)
    p.add_argument("--date", help="全件をこの論理日に書く（省くと件ごとの時刻から決める）")
    p.add_argument("--at", help="日付の無い件（HH:MM・空）の基準にする取得時刻（タイムゾーン付き ISO）")
    p = cmd(s, "current", media.current, "current.md を置き換える（JSON 行）", True, True)
    p.add_argument("--kind", required=True)
    p.add_argument("--total", type=int, help="総数（省くと行数）")
    p = cmd(s, "show", media.show, "出す（--kind を省くと全種類）")
    p.add_argument("--kind")
    p.add_argument("--date")

    s = group("task", "40_tasks（タスクと予定）")
    p = cmd(s, "new", task.new, "新しいタスク", True, True)
    p.add_argument("--title", required=True)
    p.add_argument("--owner", required=True, choices=task.OWNERS)
    p.add_argument("--type", choices=task.TYPES)
    p.add_argument("--due")
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--priority", choices=task.PRIORITIES)
    p.add_argument("--estimate")
    p.add_argument("--project")
    p.add_argument("--repeat")
    p.add_argument("--source")
    p.add_argument("--id")
    p = cmd(s, "update", task.update, "項目を変える", True)
    p.add_argument("id")
    for opt in ("title", "due", "start", "end", "priority", "estimate", "project", "owner", "repeat"):
        p.add_argument(f"--{opt}")
    p = cmd(s, "note", task.note, "経緯へ1行追記", True, True)
    p.add_argument("id")
    p = cmd(s, "start", task.start, "in_progress にする", True)
    p.add_argument("id")
    p = cmd(s, "wait", task.wait, "waiting にし、次に確認する日を持たせる", True)
    p.add_argument("id")
    p.add_argument("--for", dest="for_", required=True)
    p.add_argument("--recheck", required=True)
    p = cmd(s, "review", task.review, "needs_review にする", True, True)
    p.add_argument("id")
    p = cmd(s, "done", task.done, "done にして archive へ", True, True)
    p.add_argument("id")
    p = cmd(s, "cancel", task.cancel, "cancelled にして archive へ", True)
    p.add_argument("id")
    p.add_argument("--reason", required=True)
    p = cmd(s, "reopen", task.reopen, "open に戻す（archive の物は active へ戻す）", True)
    p.add_argument("id")
    p = cmd(s, "show", task.show, "出す")
    p.add_argument("id")
    p = cmd(s, "list", task.list_tasks, "一覧")
    p.add_argument("--state", choices=task.STATES)
    p.add_argument("--owner")
    p.add_argument("--due-before")
    p.add_argument("--project")
    p.add_argument("--type", choices=task.TYPES)
    p.add_argument("--all", action="store_true", help="archive も含める")
    p = cmd(s, "tidy", task.tidy, "日時を過ぎた予定を archive へ", True)
    p.add_argument("--before")

    s = group("project", "30_projects（案件）")
    p = cmd(s, "new", project.new, "案件を作る", True)
    p.add_argument("name")
    p.add_argument("--purpose", required=True)
    p.add_argument("--repo", action="append")
    p.add_argument("--data", action="append")
    p = cmd(s, "status", project.status, "節を置き換える（既定は「今の状態」。--section で「決まっていること」「目的」「経緯」）", True, True)
    p.add_argument("name")
    p.add_argument("--section", choices=["今の状態", "決まっていること", "目的", "経緯"], default="今の状態")
    p = cmd(s, "meta", project.meta, "頭書きの 開始・関連repo・関連data を置き換える（渡した物だけ）", True)
    p.add_argument("name")
    p.add_argument("--start")
    p.add_argument("--repo", action="append")
    p.add_argument("--data", action="append")
    p = cmd(s, "log", project.log, "「経緯」へ1行追記", True, True)
    p.add_argument("name")
    p = cmd(s, "attach", project.attach, "資料/ へ md を置く", True)
    p.add_argument("name")
    p.add_argument("--file", required=True)
    p.add_argument("--name", dest="as_name")
    p = cmd(s, "close", project.close, "終えて archive へ", True, True)
    p.add_argument("name")
    p.add_argument("--result", required=True, choices=("完了", "中止"))
    p = cmd(s, "reopen", project.reopen, "archive から active へ戻す", True)
    p.add_argument("name")
    p = cmd(s, "show", project.show, "メモと紐づくタスクを出す")
    p.add_argument("name")
    p = cmd(s, "list", project.list_projects, "一覧")
    p.add_argument("--all", action="store_true")

    s = group("identity", "20_identity（今の本人）")
    p = cmd(s, "set", identity.set_section, "節を置き換え、10_daily に足した行・消した行を残す", True, True)
    p.add_argument("file")
    p.add_argument("--section", required=True)
    p.add_argument("--why")
    p = cmd(s, "show", identity.show, "出す（ファイルを省くと全ファイル）")
    p.add_argument("file", nargs="?")

    s = group("distill", "60_distilled（ソースごとの蒸留）")
    p = cmd(s, "write", distill.write, "その日のファイルを節ごとに置き換える", True, True)
    p.add_argument("--source", required=True)
    p.add_argument("--date")
    p.add_argument("--read-count", type=int)
    p.add_argument("--adopted", type=int)
    p = cmd(s, "show", distill.show, "出す（--source を省くと、その日の全ソース）")
    p.add_argument("--source")
    p.add_argument("--date")

    s = group("daily", "10_daily（その日の要約と本人像の変化）")
    p = cmd(s, "write", daily.write, "節を置き換える", True, True)
    p.add_argument("--date")
    p.add_argument("--section", required=True)
    p = cmd(s, "show", daily.show, "出す")
    p.add_argument("--date")

    s = group("log", "90_logs（仕組みの記録）")
    p = cmd(s, "audit", log.audit, "監査結果を作る（同じ日付は上書きしない）", True, True)
    p.add_argument("--name", required=True)
    p.add_argument("--date")
    p = cmd(s, "schedule", log.schedule, "定時処理の実行メモへ追記", True, True)
    p.add_argument("--task", required=True)
    p = cmd(s, "handoff", log.handoff, "引き継ぎログへ1行追記", True, True)
    p.add_argument("--agent", required=True)

    s = group("views", "画面（NOW.md・タスク.base・README.md）")
    cmd(s, "refresh", views.refresh, "作り直す（タスクのファイルは書き換えない）", True)

    p = sub.add_parser("check", help="全ファイルの形を調べ 90_logs/check に書く", parents=[C, W])
    p.set_defaults(func=check.run)
    p.add_argument("--fix", action="store_true", help="頭書きの補完だけ直す")
    p.add_argument("--date")

    p = sub.add_parser("day", help="論理日（Asia/Tokyo 05:00 区切り）を出す（読み取りだけ）", parents=[C])
    p.set_defaults(func=logical_day.day_cmd)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--at", help="この日時（タイムゾーン付き ISO）の論理日")
    g.add_argument("--date", help="この論理日の始まりと終わり")
    g.add_argument("--stdin", action="store_true", help="ISO 日時を1行ずつ受けて、それぞれの論理日を出す")

    p = sub.add_parser("version", help="版と形式", parents=[C])
    p.set_defaults(func=lambda a: {"version": VERSION, "形式": FORMAT})

    return root


def _read_body(args):
    if getattr(args, "text", None) is not None:
        return args.text
    if getattr(args, "stdin", False):
        return sys.stdin.read()
    path = getattr(args, "input_file", None)
    if path:
        p = Path(path).expanduser().resolve()
        if workspace_root().resolve() not in p.parents:
            raise SbError(4, f"Workspace の外のファイルは読まない: {p}")
        if not p.is_file():
            raise SbError(3, f"ファイルが無い: {p}")
        return p.read_text(encoding="utf-8")
    return None


def _human(result, dry_run):
    if "text" in result:
        print(result["text"], end="" if result["text"].endswith("\n") else "\n")
        for t in result.get("tasks", []):
            print(f"  task {t['ID']}  {t['状態']}  {t.get('期限') or '-'}  {t['件名']}")
        return
    if "items" in result:
        for item in result["items"]:
            print(json.dumps(item, ensure_ascii=False))
        return
    if "tasks" in result:
        for t in result["tasks"]:
            mark = " [archive]" if t.get("archived") else ""
            print(f"{t.get('ID')}  {t.get('状態')}  {t.get('期限') or '-'}  {t.get('件名')}{mark}")
        return
    if "projects" in result:
        for p in result["projects"]:
            mark = f" [{p['状態']}]" if p["where"] == "archive" else ""
            print(f"{p['name']}{mark}")
        return
    if "problems" in result:
        for p in result["problems"]:
            print(f"{p['path']}: {p['problem']}（{p['fixed']}）")
        print(f"調べた md: {result['checked']} / 崩れ: {len(result['problems'])} / 残り: {result['remaining']}")
    for e in result.get("plan", []):
        print(f"{'(dry-run) ' if dry_run else ''}{e['action']}: {e['path']}")
        if dry_run and "text" in e:
            print(e["text"])
    shown = {k: v for k, v in result.items() if k not in ("plan", "problems", "_exit")}
    if "version" in result:
        print(f"sb {result['version']}（形式 {result['形式']}）")
    elif not result.get("plan") and "problems" not in result:
        print(json.dumps(shown, ensure_ascii=False, default=str))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    try:
        args = build_parser().parse_args(argv)
        args.body = _read_body(args)
        if not hasattr(args, "dry_run"):
            args.dry_run = False
        result = args.func(args)
        code = result.pop("_exit", 0) if isinstance(result, dict) else 0
        if args.json:
            print(json.dumps({"ok": True, **result}, ensure_ascii=False, default=str))
        else:
            _human(result, args.dry_run)
        return code
    except SbError as e:
        if as_json:
            print(json.dumps({"ok": False, "code": e.code, "error": str(e)}, ensure_ascii=False))
        else:
            print(f"sb: {e}", file=sys.stderr)
        return e.code
    except SystemExit as e:  # --help
        return int(e.code or 0)
    except Exception as e:  # noqa: BLE001
        msg = f"内部の誤り: {type(e).__name__}: {e}"
        if as_json:
            print(json.dumps({"ok": False, "code": 5, "error": msg}, ensure_ascii=False))
        else:
            print(f"sb: {msg}", file=sys.stderr)
        return 5
