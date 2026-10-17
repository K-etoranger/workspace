"""SecondBrain と company/ の md を、検索で返す単位（塊）に切る。元の文のまま切り、塊ごとに場所・日付・話し手を持たせる。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from memory_search import workspace as paths

MAX_CHARS = 1000  # 1塊の上限（日本語で約800トークン）
OVERLAP = 100  # 長い段落を切るときの重なり
PACK_CHARS = 600  # 短い段落・箇条をこの長さまでまとめる
NO_PACK_LAYERS = {"20_identity"}  # 確定事実は箇条1行ずつ
NO_DATE_LAYERS = {"20_identity"}  # 今の本人だけを置く層。更新の日はその事実の日ではないので付けない
FTS_ONLY_LAYERS = {"50_media"}  # 表の行は言葉で引けば足りるので埋め込まない
HEADER_LAYERS = {"30_projects", "40_tasks"}  # 頭書きに中身（件名・状態・期限・出典・待ち など）を持つ層
MECHANICAL_KEYS = {"形式", "種類", "ID", "連続取消", "作成", "更新", "書いた物", "関連repo", "関連data"}  # 頭書きのうち、仕組みの記録の欄

DATE_RE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
SECRET_RE = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret|cookie|authorization)"
    r"\s*[:=]\s*['\"]?[A-Za-z0-9_./+\-=]{20,}"
    r"|\bsk-[A-Za-z0-9_-]{20,}|\bxox[abprs]-[A-Za-z0-9-]{10,}|\beyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{10,}"
)
# 機械が入れた発言（作業の通知・引き継ぎの添付・コマンドの注記・hook の返事）。本人が貼った文やブラウザの情報つきの発言は外さない
MACHINE_TURN_RE = re.compile(r"<(?:task-notification|agent-continuity|local-command-caveat|system-reminder)\b|Stop hook feedback:")
NOISE_RE = re.compile(r"^\s*(?:<!--.*-->|\[Image: .*\]|\[Request interrupted .*\])\s*$")
SCHEDULED_MARKS = ("<scheduled-task", "This is an automated run of a scheduled task", "<automation_id>")  # Claude の定時処理・Codex の automation
# 検索の試験の例として話題（園芸・読書など）を並べた作業の会話。エージェントの返事が出来事の記録より上に来るので、本人の発言だけを残す。会話の見出し「## 時刻 id」の id
WORK_SESSIONS = {
    "0000abcd",  # 例: conversations/claude/2026-10-04.md の会話
}


@dataclass(frozen=True)
class Chunk:
    path: str  # Workspace からの相対
    line_start: int  # 1 始まり・両端を含む
    line_end: int
    layer: str  # 10_daily・00_inbox/conversations など
    date: str  # その話の日（YYYY-MM-DD、会話・連絡は時刻つき）。分からなければ空
    speaker: str  # 会話は 山田・Claude・Codex、連絡は相手（スレッド）。ほかは空
    status: str  # current か archive
    title: str
    heading: str  # 見出しの道筋
    text: str
    embed: bool

    def context(self) -> str:
        """埋め込む文と全文検索に入れる文の頭に付ける「いつ・どこの・何の話か」。"""
        where = " > ".join(x for x in (self.layer, self.title, self.heading, self.speaker) if x)
        return f"[{self.date}] {where}" if self.date else where


# ---------------------------------------------------------------- 対象


SKIP_DIRS = {"node_modules", "site-packages", "__pycache__"}  # ほかに「.」で始まる物も入れない


def target_files() -> list[Path]:
    ws = paths.workspace_root()
    found = []
    for root in paths.INDEX_ROOTS:
        for path in (ws / root).rglob("*.md"):
            parts = path.relative_to(ws).parts
            if not any(part.startswith(".") or part in SKIP_DIRS for part in parts) and path.is_file():
                found.append(path)
    return sorted(found)


def layer_of(parts: tuple[str, ...]) -> str:
    """Workspace からの相対の parts から層の名前。SecondBrain の 00_inbox は2段（00_inbox/conversations など）。"""
    if parts[0] != "SecondBrain":
        return parts[0]
    return "/".join(parts[1:3]) if parts[1] == "00_inbox" else parts[1]


# ---------------------------------------------------------------- md の読み方


def split_header(lines: list[str]) -> tuple[dict[str, str], int]:
    """頭書き（--- で囲んだ `名前: 値`）と、本文が始まる行の添字。"""
    if not lines or lines[0].strip() != "---":
        return {}, 0
    header = {}
    for index, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            return header, index + 1
        key, sep, value = line.partition(":")
        if sep and key.strip() and not key.startswith((" ", "\t", "-")):
            header[key.strip()] = value.strip()
    return {}, 0


def date_of(header: dict[str, str], path: Path) -> str:
    for value in (header.get("論理日", ""), path.stem, header.get("作成", ""), header.get("更新", "")):
        match = DATE_RE.search(value)
        if match:
            return match.group(0)
    return ""


Block = list[tuple[int, str]]  # (行の添字 0 始まり, 行)


def joined(block: Block) -> str:
    return "\n".join(line.rstrip() for _, line in block)


def blocks(lines: list[str], start: int, end: int, *, bullets: bool) -> list[Block]:
    """lines[start:end] を段落（bullets なら一番外側の箇条も）ごとの行の並びにする。空行と機械の注記は落とす。"""
    out: list[Block] = []
    buf: Block = []

    def flush() -> None:
        kept = [(i, l) for i, l in buf if l.strip() and not NOISE_RE.match(l)]
        if kept:
            out.append(kept)
        buf.clear()

    for index in range(start, end):
        line = lines[index]
        if not line.strip():
            flush()
            continue
        if bullets and re.match(r"^[-*] |^\d+\. ", line):
            flush()
        buf.append((index, line))
    flush()
    return out


def split_long(block: Block) -> list[tuple[int, int, str]]:
    """MAX_CHARS を超える段落を、行の境目で切る。前の塊の最後の行が短ければ次の塊の頭にも入れる。
    1行だけで MAX_CHARS を超える行は、その行を OVERLAP 字重ねながら字で切る（行番号はその行）。"""
    out: list[tuple[int, int, str]] = []
    cur: Block = []
    for index, line in block:
        if len(line) > MAX_CHARS:
            if cur:
                out.append((cur[0][0], cur[-1][0], joined(cur)))
                cur = []
            step = MAX_CHARS - OVERLAP
            out.extend((index, index, line[i : i + MAX_CHARS]) for i in range(0, len(line) - OVERLAP, step))
            continue
        if cur and len(joined(cur)) + 1 + len(line) > MAX_CHARS:
            out.append((cur[0][0], cur[-1][0], joined(cur)))
            cur = [cur[-1]] if len(cur[-1][1]) <= OVERLAP * 2 else []
        cur.append((index, line))
    if cur:
        out.append((cur[0][0], cur[-1][0], joined(cur)))
    return out


def pieces(blocks_: list[Block], pack: int) -> list[tuple[int, int, str]]:
    """短い段落を pack 字までまとめ、MAX_CHARS を超える段落は split_long で切る。(始, 終, 文)、行は 0 始まり。"""
    out: list[tuple[int, int, str]] = []
    fresh = False  # 直前の塊がまとめてよい物か（長い段落を切った塊にはまとめない）
    for block in blocks_:
        text = joined(block)
        if len(text) > MAX_CHARS:
            out.extend(split_long(block))
            fresh = False
        elif out and fresh and pack and len(out[-1][2]) + len(text) + 1 <= pack:
            prev = out[-1]
            out[-1] = (prev[0], block[-1][0], prev[2] + "\n" + text)
        else:
            out.append((block[0][0], block[-1][0], text))
            fresh = True
    return out


def sections(lines: list[str], start: int) -> list[tuple[int, int, list[str]]]:
    """見出しで区切った (始, 終, 見出しの道筋)。終は含まない。コードの囲み（同じ記号で同じ長さ以上の行が閉じる）の中の # は見出しにしない。"""
    out = []
    stack: list[tuple[int, str]] = []
    begin = start
    fence: str = ""
    for index in range(start, len(lines)):
        line = lines[index]
        mark = FENCE_RE.match(line)
        if mark:
            if not fence:
                fence = mark.group(1)
            elif mark.group(1)[0] == fence[0] and len(mark.group(1)) >= len(fence) and not line[mark.end():].strip():
                fence = ""
            continue
        match = None if fence else HEADING_RE.match(line)
        if match:
            out.append((begin, index, [h for _, h in stack]))
            level = len(match.group(1))
            stack = [(lv, h) for lv, h in stack if lv < level] + [(level, match.group(2))]
            begin = index + 1
    out.append((begin, len(lines), [h for _, h in stack]))
    return out


def dump_sections(lines: list[str], start: int) -> list[tuple[int, int, str, str]]:
    """会話・連絡の記録の区切り (始, 終, 「## 」の見出し, 「### 」の見出し)。
    記録は本文の行頭の # を \\# に逃がしてあるので、行頭が「## 」「### 」の行だけで区切り、囲みは見ない。"""
    out = []
    h2, h3, begin = "", "", start
    for index in range(start, len(lines)):
        line = lines[index]
        if line.startswith(("## ", "### ")):
            out.append((begin, index, h2, h3))
            if line.startswith("## "):
                h2, h3 = line[3:].strip(), ""
            else:
                h3 = line[4:].strip()
            begin = index + 1
    out.append((begin, len(lines), h2, h3))
    return out


# ---------------------------------------------------------------- 層ごとの切り方


def chunk_file(path: Path, scheduled: dict[str, bool] | None = None) -> tuple[list[Chunk], int]:
    """(塊, 秘密の形を含んだので捨てた塊の数)。scheduled は会話の id → 定時処理か。
    ファイルを日の順に切るときに同じ dict を渡すと、日をまたいで続く会話も最初の発言で決める。"""
    parts = path.relative_to(paths.workspace_root()).parts
    layer = layer_of(parts)
    lines = [l.rstrip("\r") for l in path.read_text(encoding="utf-8", errors="replace").split("\n")]  # 行は改行だけで数える（U+2028 などで切らない）
    header, body = split_header(lines)
    rel = "/".join(parts)
    date = "" if layer in NO_DATE_LAYERS else date_of(header, path)
    status = "archive" if parts[0] == "SecondBrain" and len(parts) > 3 and parts[2] == "archive" else "current"
    title = header.get("件名") or next((l[2:].strip() for l in lines[body:] if l.startswith("# ")), path.stem)
    if "状態" in header:
        title = f"{title}（{header['状態']}）"

    if layer == "00_inbox/conversations":
        raw = conversation_pieces(lines, body, date, {} if scheduled is None else scheduled)
    elif layer == "00_inbox/messages":
        raw = message_pieces(lines, body, date)
    else:
        pack = 0 if layer in NO_PACK_LAYERS else PACK_CHARS
        raw = []
        for start, end, heads in sections(lines, body):
            heading = " / ".join(h for h in heads if h != title.split("（")[0])
            for s, e, text in pieces(blocks(lines, start, end, bullets=True), pack):
                raw.append((s, e, text, heading, "", date))

    if layer in HEADER_LAYERS and body:
        raw = header_pieces(lines, body, date) + raw

    chunks, dropped = [], 0
    for s, e, text, heading, speaker, when in raw:
        if SECRET_RE.search(text):
            dropped += 1
            continue
        chunks.append(Chunk(rel, s + 1, e + 1, layer, when, speaker, status, title, heading, text,
                            embed=layer not in FTS_ONLY_LAYERS))
    return chunks, dropped


def header_pieces(lines: list[str], body: int, date: str) -> list[tuple]:
    """頭書きのうち中身のある欄（値の空でない、仕組みの記録でない欄）を、1つの塊にする。"""
    kept = []
    for index in range(1, body - 1):
        key, sep, value = lines[index].partition(":")
        if sep and key.strip() and key.strip() not in MECHANICAL_KEYS and value.strip() and not key.startswith((" ", "\t", "-")):
            kept.append((index, lines[index]))
    return [(s, e, text, "頭書き", "", date) for s, e, text in pieces([kept], 0)] if kept else []


def conversation_pieces(lines: list[str], body: int, date: str, scheduled: dict[str, bool]) -> list[tuple]:
    """会話: 「## 時刻 id」がひと続きの会話、「### 話し手」が発言。同じ id の会話は見出しが分かれていても1つとして扱う。
    最初の発言に定時処理の目印がある見出し、定時処理の会話の続きと WORK_SESSIONS の会話のエージェントの返事、
    機械が入れた発言（通知・hook の返事など）は外す。"""
    out = []
    current, marked = None, False
    for start, end, session, speaker in dump_sections(lines, body):
        turn = blocks(lines, start, end, bullets=False)
        if not speaker or not turn:
            continue
        text = "\n".join(line for block in turn for _, line in block)
        sid = (session.split() or [""])[-1]
        if session != current:  # 見出しの最初の発言に目印があれば、その見出しの間は外す（会話の途中に挟まった定時処理）
            current, marked = session, any(mark in text for mark in SCHEDULED_MARKS)
            scheduled.setdefault(sid, marked)  # 会話の id の最初の発言に目印があれば、その会話の続きもエージェントの返事を外す
        agent_only = scheduled[sid] or sid in WORK_SESSIONS  # 本人の発言だけを残す会話
        if marked or (agent_only and speaker != "山田") or MACHINE_TURN_RE.match(text.lstrip()):
            continue
        when = f"{date} {session.split()[0]}" if session[:1].isdigit() else date
        for s, e, piece in pieces(turn, MAX_CHARS):
            out.append((s, e, piece, "", speaker, when))
    return out


def message_pieces(lines: list[str], body: int, date: str) -> list[tuple]:
    """連絡: 「## 時刻 相手 — 送り手 → 宛先」が1通。続いている同じ相手の通を MAX_CHARS までまとめる。"""
    out = []
    for start, end, heading, _ in dump_sections(lines, body):
        if not heading[:1].isdigit():
            continue
        time, _, rest = heading.partition(" ")
        thread = rest.split(" — ")[0].strip()
        found = blocks(lines, start, end, bullets=False)
        if not found:
            continue
        block = [(start - 1, f"{time} {rest}")] + [x for b in found for x in b]
        text = joined(block)
        prev = out[-1] if out else None
        if prev and prev[4] == thread and prev[6] and len(prev[2]) + len(text) + 1 <= MAX_CHARS:
            out[-1] = (prev[0], block[-1][0], prev[2] + "\n" + text, "", thread, prev[5], True)
        else:
            for s, e, t in pieces([block], 0):
                out.append((s, e, t, "", thread, f"{date} {time}", len(text) <= MAX_CHARS))
    return [p[:6] for p in out]
