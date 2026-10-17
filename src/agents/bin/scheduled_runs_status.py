#!/usr/bin/env python3
"""定時実行の状態を1画面で確認する共有tool。

Claude scheduled task（`~/.claude/scheduled-tasks/`）とCodex automation（`~/.codex/automations/`）を
横断して、どちらが今どの定時実行を持っているかを表示する。
同じ処理が両側で有効になっていないか（＝正本の二重mutation）を毎回検出することが主目的。

読み取りだけを行い、何も変更しない。CodexからもClaudeからも同じ経路で実行できる共有資産として
`Workspace/src/agents/bin/` に置く。

使い方:
    python3 "$HOME/Workspace/src/agents/bin/scheduled_runs_status.py"
    python3 .../scheduled_runs_status.py --json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

HOME = Path.home()
CLAUDE_TASK_DIR = HOME / ".claude" / "scheduled-tasks"
CLAUDE_STORE_GLOB = str(
    HOME / "Library" / "Application Support" / "Claude" / "claude-code-sessions" / "*" / "*" / "scheduled-tasks.json"
)
CODEX_AUTOMATION_DIR = HOME / ".codex" / "automations"

# 「このClaude taskはどのCodex automationの後継か」はSKILL.md本文に書いてあるので、
# 固定リストを持たずそこから読む。新しい移植を足しても勝手に追従する。
ORIGIN_RE = re.compile(r"Codex automation [`'\"]?([a-z0-9][a-z0-9._-]{1,60})[`'\"]?")


def read_json(path: str | Path) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def cron_next(expression: str, start: datetime) -> datetime | None:
    """5フィールドcronの次回発火をローカル時刻で返す。見つからなければNone。"""
    fields = expression.split()
    if len(fields) != 5:
        return None

    def expand(spec: str, low: int, high: int) -> set[int]:
        allowed: set[int] = set()
        for part in spec.split(","):
            step = 1
            if "/" in part:
                part, _, raw_step = part.partition("/")
                if not raw_step.isdigit():
                    return set()
                step = int(raw_step)
            if part in ("*", ""):
                begin, end = low, high
            elif "-" in part:
                begin_raw, _, end_raw = part.partition("-")
                if not (begin_raw.isdigit() and end_raw.isdigit()):
                    return set()
                begin, end = int(begin_raw), int(end_raw)
            elif part.isdigit():
                begin = end = int(part)
            else:
                return set()
            allowed.update(value for value in range(begin, end + 1, step) if low <= value <= high)
        return allowed

    minutes = expand(fields[0], 0, 59)
    hours = expand(fields[1], 0, 23)
    days = expand(fields[2], 1, 31)
    months = expand(fields[3], 1, 12)
    weekdays = {value % 7 for value in expand(fields[4], 0, 7)}
    if not all([minutes, hours, days, months, weekdays]):
        return None

    dom_restricted = fields[2] != "*"
    dow_restricted = fields[4] != "*"
    moment = (start + timedelta(minutes=1)).replace(second=0, microsecond=0)
    limit = moment + timedelta(days=400)
    while moment < limit:
        if moment.month not in months:
            moment = (moment.replace(day=1) + timedelta(days=32)).replace(day=1, hour=0, minute=0)
            continue
        weekday = (moment.weekday() + 1) % 7  # cronは日曜=0
        if dom_restricted and dow_restricted:
            day_ok = moment.day in days or weekday in weekdays
        else:
            day_ok = (not dom_restricted or moment.day in days) and (not dow_restricted or weekday in weekdays)
        if not day_ok:
            moment = (moment + timedelta(days=1)).replace(hour=0, minute=0)
            continue
        if moment.hour not in hours:
            moment = (moment + timedelta(hours=1)).replace(minute=0)
            continue
        if moment.minute in minutes:
            return moment
        moment += timedelta(minutes=1)
    return None


def format_fire_at(value: object) -> str:
    """one-shotの発火時刻を人が読める現地時刻へ。epoch ms / epoch秒 / ISO文字列を受ける。"""
    if isinstance(value, (int, float)):
        seconds = float(value) / 1000.0 if float(value) > 1e11 else float(value)
        return datetime.fromtimestamp(seconds).strftime("%Y-%m-%d %H:%M")
    text = str(value).strip()
    if text.isdigit():
        return format_fire_at(int(text))
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone()
    return parsed.strftime("%Y-%m-%d %H:%M")


def claude_tasks() -> list[dict]:
    stores = sorted(glob.glob(CLAUDE_STORE_GLOB), key=os.path.getmtime, reverse=True)
    entries: dict[str, dict] = {}
    for store in stores:
        for row in read_json(store).get("scheduledTasks", []):
            entries.setdefault(str(row.get("id") or ""), {"row": row, "store": store})

    now = datetime.now()
    result = []
    for task_id, found in sorted(entries.items()):
        row = found["row"]
        skill = Path(row.get("filePath") or (CLAUDE_TASK_DIR / task_id / "SKILL.md"))
        body = skill.read_text(encoding="utf-8", errors="replace") if skill.exists() else ""
        origins = ORIGIN_RE.findall(body)
        cron = row.get("cronExpression")
        fire_at = row.get("fireAt")
        if cron:
            upcoming = cron_next(cron, now)
            schedule, next_run = cron, upcoming.strftime("%Y-%m-%d %H:%M") if upcoming else "計算不可"
        elif fire_at:
            # storeはepoch ms、APIはISO文字列を返すことがあるのでどちらも人が読める形へ揃える。
            readable = format_fire_at(fire_at)
            schedule, next_run = "一回限り", readable
        else:
            schedule, next_run = "手動のみ", "—"
        result.append(
            {
                "id": task_id,
                "enabled": bool(row.get("enabled", False)),
                "schedule": schedule,
                "next_run": next_run,
                "skill_exists": skill.exists(),
                "origin_codex_automation": origins[0] if origins else None,
                "store": found["store"],
            }
        )
    return result


def codex_automations() -> list[dict]:
    result = []
    for toml_path in sorted(CODEX_AUTOMATION_DIR.glob("*/automation.toml")):
        try:
            text = toml_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        def field(key: str) -> str:
            match = re.search(rf'^{key} = "([^"]*)"$', text, re.MULTILINE)
            return match.group(1) if match else ""

        result.append(
            {
                "id": toml_path.parent.name,
                "status": field("status") or "不明",
                "rrule": field("rrule"),
                "name": field("name"),
                "path": str(toml_path),
            }
        )
    return result


def build_report() -> dict:
    tasks = claude_tasks()
    automations = codex_automations()
    by_origin = {task["origin_codex_automation"]: task for task in tasks if task["origin_codex_automation"]}

    conflicts = []
    for automation in automations:
        if automation["status"] != "ACTIVE":
            continue
        successor = by_origin.get(automation["id"])
        if successor and successor["enabled"]:
            conflicts.append(
                {
                    "codex_automation": automation["id"],
                    "claude_task": successor["id"],
                    "risk": "同じ処理が両側で有効。正本を二重mutationする。",
                }
            )

    orphans = [
        task["id"]
        for task in tasks
        if task["enabled"] and not task["skill_exists"]
    ]
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "claude_scheduled_tasks": tasks,
        "codex_automations": automations,
        "conflicts": conflicts,
        "missing_skill_files": orphans,
    }


def render(report: dict) -> str:
    lines = [f"定時実行の状態  ({report['generated_at']})", ""]

    lines.append("■ Claude scheduled task（今これが動かしている）")
    if not report["claude_scheduled_tasks"]:
        lines.append("  （0件）")
    for task in report["claude_scheduled_tasks"]:
        mark = "有効" if task["enabled"] else "停止"
        origin = f"  ← Codex `{task['origin_codex_automation']}`" if task["origin_codex_automation"] else ""
        lines.append(f"  [{mark}] {task['id']}")
        lines.append(f"         {task['schedule']}   次回 {task['next_run']}{origin}")
        if not task["skill_exists"]:
            lines.append("         ⚠ SKILL.md が見つからない")
    lines.append("")

    lines.append("■ Codex automation（PAUSEDのままなら正常）")
    if not report["codex_automations"]:
        lines.append("  （0件）")
    for automation in report["codex_automations"]:
        flag = "⚠ ACTIVE" if automation["status"] == "ACTIVE" else automation["status"]
        lines.append(f"  [{flag}] {automation['id']}  {automation['rrule']}")
    lines.append("")

    if report["conflicts"]:
        lines.append("■ ⚠ 二重実行の危険")
        for conflict in report["conflicts"]:
            lines.append(
                f"  Codex `{conflict['codex_automation']}` と Claude `{conflict['claude_task']}` が両方有効。"
            )
            lines.append(f"  → {conflict['risk']}")
        lines.append("  対処: どちらか一方だけを有効にする。")
    else:
        lines.append("■ 二重実行の危険: なし（Codex側ACTIVEで後継Claude taskも有効、という組み合わせは0件）")

    if report["missing_skill_files"]:
        lines.append("")
        lines.append("■ ⚠ SKILL.md 欠落: " + ", ".join(report["missing_skill_files"]))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Claude/Codexの定時実行の状態をまとめて表示する（読み取りのみ）")
    parser.add_argument("--json", action="store_true", help="機械可読なJSONで出力する")
    args = parser.parse_args()

    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render(report))
    return 2 if report["conflicts"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
