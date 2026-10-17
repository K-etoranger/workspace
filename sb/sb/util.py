"""入力の読み方と、md の表の小さな道具。"""

import json
import re
from datetime import datetime

from . import SbError
from .logical_day import in_tz


def json_lines(text):
    """標準入力の JSON 行（1行1件、各行は object）。"""
    items = []
    for n, line in enumerate((text or "").split("\n"), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as e:
            raise SbError(1, f"{n}行目が JSON でない: {e.msg}")
        if not isinstance(item, dict):
            raise SbError(1, f"{n}行目が JSON の object でない")
        # 片方だけのサロゲート（途中で切れた絵文字など）は書けないので「\ufffd」に置き換える
        items.append({k: "" if v is None else (v.encode("utf-8", "replace").decode("utf-8") if isinstance(v, str) else v)
                      for k, v in item.items()})
    return items


def hhmm(value):
    """'HH:MM'・'HH:MM:SS' か ISO の日時 → 'HH:MM'（Asia/Tokyo）。"""
    text = str(value or "").strip()
    if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", text):
        return text[:-3].zfill(5) if text.count(":") == 2 else text.zfill(5)
    try:
        return in_tz(datetime.fromisoformat(text.replace("Z", "+00:00"))).strftime("%H:%M")
    except ValueError:
        raise SbError(1, f"時刻は HH:MM か ISO の日時で: {text[:30]}")


def day_hhmm(value):
    """一覧（current）の時刻: ISO の日時 → 'YYYY-MM-DD HH:MM'（Asia/Tokyo）。'HH:MM'・'YYYY-MM-DD' だけの値はそのまま。"""
    text = str(value or "").strip()
    if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", text):
        return hhmm(text)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):  # 日付だけなら時刻を作らない
        return text
    try:
        return in_tz(datetime.fromisoformat(text.replace("Z", "+00:00"))).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        raise SbError(1, f"時刻は HH:MM か ISO の日時で: {text[:30]}")


def cell(value):
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def table_row(values):
    return "| " + " | ".join(cell(v) for v in values) + " |"


def table(columns, rows):
    head = [table_row(columns), "|" + "---|" * len(columns)]
    return "\n".join(head + [table_row(r) for r in rows])


def table_rows(body):
    """本文の表の行（見出しと区切りを除く）の文字列。"""
    lines = [ln for ln in body.split("\n") if ln.startswith("|")]
    return lines[2:]


def slug_ascii(text):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", str(text).lower())).strip("-")
