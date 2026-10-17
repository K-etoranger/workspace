"""論理日（Asia/Tokyo 05:00 区切り）。"""

import os
import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from . import SbError

TZ = ZoneInfo("Asia/Tokyo")
BOUNDARY_HOUR = 5
END_OF_DAY_LABEL = "23:59"


def now():
    """現在時刻。SB_NOW（ISO 形式）があればそれを使う（試験用）。"""
    fixed = os.environ.get("SB_NOW")
    if fixed:
        value = datetime.fromisoformat(fixed)
        return (value if value.tzinfo else value.replace(tzinfo=TZ)).astimezone(TZ)
    return datetime.now(tz=TZ)


def in_tz(value=None):
    current = value or now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=TZ)
    return current.astimezone(TZ)


def logical_date(value=None):
    """05:00 未満は前日の論理日。"""
    return (in_tz(value) - timedelta(hours=BOUNDARY_HOUR)).date()


def today():
    return logical_date()


def day_start(day):
    return datetime.combine(day, time(BOUNDARY_HOUR), tzinfo=TZ)


def day_end_exclusive(day):
    return day_start(day + timedelta(days=1))


def canonical_due(value):
    """期限の比較用の時刻。日付だけ・23:59 は論理日の終わり（翌日 05:00）。それ以外の時刻はそのまま。"""
    text = str(value or "").strip()
    for pattern in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, pattern)
        except ValueError:
            continue
        if pattern == "%Y-%m-%d" or parsed.strftime("%H:%M") == END_OF_DAY_LABEL:
            return day_end_exclusive(parsed.date())
        return parsed.replace(tzinfo=TZ)
    return None


def event_day(value):
    """予定の日時 → 属する論理日。"""
    text = str(value or "").strip()
    for pattern in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, pattern)
        except ValueError:
            continue
        return parsed.date() if pattern == "%Y-%m-%d" else logical_date(parsed.replace(tzinfo=TZ))
    return None


def parse_date(text):
    try:
        return date.fromisoformat(text)
    except (TypeError, ValueError):
        raise SbError(1, f"日付は YYYY-MM-DD で: {text}")


def date_arg(text):
    """--date の値。省くと今日の論理日。"""
    return parse_date(text) if text else today()


def parse_iso(text):
    """タイムゾーン付きの ISO 日時（Z も可）→ datetime。タイムゾーンの無い日時は断る。"""
    s = str(text or "").strip()
    try:
        value = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        raise SbError(1, f"日時はタイムゾーン付きの ISO で: {s[:40]}")
    if value.tzinfo is None:
        raise SbError(1, f"日時にタイムゾーンが無い: {s[:40]}")
    return value


def day_of_time(text, at=None):
    """件の時刻 → 論理日。タイムゾーン付き ISO はそのまま。HH:MM(:SS) は at 以前で最も近いその時刻（Tokyo）。
    空は at の論理日。at が要るのに無い・タイムゾーンの無い ISO は SbError(1)。at は datetime。"""
    s = str(text or "").strip()
    base = in_tz(at) if at else None
    m = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", s)
    if not s or m:
        if base is None:
            raise SbError(1, f"時刻 {s or '（空）'} に日付が無い（--at か --date を付ける）")
        if not s:
            return logical_date(base)
        try:
            t = base.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=int(m.group(3) or 0), microsecond=0)
        except ValueError:
            raise SbError(1, f"時刻が読めない: {s}")
        return logical_date(t - timedelta(days=1) if t > base else t)
    return logical_date(parse_iso(s))


def item_day(text, date=None, at=None):
    """件を書く論理日。date（--date）があればその日。ただしタイムゾーン付き ISO の時刻が別の日なら断る。"""
    if date is None:
        return day_of_time(text, at)
    try:
        own = day_of_time(text)
    except SbError:
        return date  # HH:MM・空・読めない値は date に従う（読めない値は表を作るときに断る）
    if own != date:
        raise SbError(1, f"時刻 {text} の論理日 {own} が --date {date} と違う")
    return date


def day_cmd(args):
    """sb day: 論理日とその始まり・終わり。--stdin は1行1日時。"""
    if args.stdin:
        lines = [ln.strip() for ln in (args.body or "").split("\n") if ln.strip()]
        return {"days": [{"at": ln, "date": str(logical_date(parse_iso(ln)))} for ln in lines]}
    day = logical_date(parse_iso(args.at)) if args.at else date_arg(args.date)
    return {"date": str(day), "start": stamp(day_start(day)), "end": stamp(day_end_exclusive(day))}


def stamp(value=None):
    """頭書きの時刻 2026-09-29T17:40+09:00。"""
    s = in_tz(value).strftime("%Y-%m-%dT%H:%M%z")
    return s[:-2] + ":" + s[-2:]


def minute(value=None):
    return in_tz(value).strftime("%Y-%m-%d %H:%M")
