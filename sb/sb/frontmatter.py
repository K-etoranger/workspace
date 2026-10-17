"""頭書き（YAML の厳しい部分集合: `key: value` と `key: [a, b]`）と、本文の `## 節` の操作。"""

import re

from . import SbError


class FrontmatterError(SbError):
    def __init__(self, message):
        super().__init__(1, message)


def _unquote(text):
    if len(text) >= 2 and text[0] == text[-1] == '"':
        return re.sub(r"\\(.)", r"\1", text[1:-1])
    return None


def _scalar(text):
    q = _unquote(text)
    if q is not None:
        return q
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if text in ("true", "false"):
        return text == "true"
    return text


def parse(text):
    """(頭書き dict, 本文) を返す。頭書きが無ければ ({}, text)。"""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 3)
    if end < 0:
        if text.endswith("\n---"):
            end = len(text) - 4
        else:
            raise FrontmatterError("頭書きの終わり（---）が無い")
    meta = {}
    for line in text[4:end].split("\n"):
        if not line.strip():
            continue
        m = re.fullmatch(r"([^\s:][^:]*):(?: (.*))?", line)
        if not m:
            raise FrontmatterError(f"頭書きの行が読めない: {line[:40]}")
        value = (m.group(2) or "").strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            meta[m.group(1)] = [_scalar(v.strip()) for v in inner.split(",")] if inner else []
        else:
            meta[m.group(1)] = _scalar(value)
    return meta, text[end + 5:]


_SPECIAL_START = set("-?:,[]{}#&*!|>'\"%@`")


def _quote(text, in_list=False):
    """YAML として読めなくなる値だけを "…" で囲む（sb の読み方は _scalar が外す）。"""
    if text == "":
        return text
    risky = (": " in text or " #" in text or text.endswith(":") or text[0] in _SPECIAL_START
             or text != text.strip() or "\t" in text or (in_list and any(c in text for c in ",[]{}")))
    if not risky:
        return text
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _fmt(value, in_list=False):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        for v in value:
            if "," in str(v) or "\n" in str(v):
                raise FrontmatterError(f"配列の値に , や改行は使えない: {v}")
        return "[" + ", ".join(_fmt(v, True) for v in value) + "]"
    if isinstance(value, int):
        return str(value)
    text = "" if value is None else str(value)
    if "\n" in text:
        raise FrontmatterError("頭書きの値に改行は使えない")
    return _quote(text, in_list)


def dump(meta, body):
    lines = ["---"]
    for k, v in meta.items():
        s = _fmt(v)
        lines.append(f"{k}: {s}" if s != "" else f"{k}:")
    lines.append("---")
    return "\n".join(lines) + "\n" + body


# ---- 本文の節 ----

def headings(body, level=2):
    prefix = "#" * level + " "
    return [line[len(prefix):].strip() for line in body.split("\n") if line.startswith(prefix)]


def _section_span(lines, name):
    start = None
    for i, line in enumerate(lines):
        if start is None and line.startswith("## ") and line[3:].strip() == name:
            start = i
        elif start is not None and (line.startswith("## ") or line.startswith("# ")):
            return start, i
    return (start, len(lines)) if start is not None else None


def get_section(body, name):
    lines = body.split("\n")
    span = _section_span(lines, name)
    if span is None:
        return None
    return "\n".join(lines[span[0] + 1:span[1]]).strip("\n")


def check_section_text(text):
    """節の中身に節や題名の見出しが混ざっていないか。"""
    for line in text.split("\n"):
        if re.match(r"#{1,2} ", line):
            raise SbError(1, f"節の中身に「#」「##」の見出しは入れられない（### 以下を使う）: {line[:40]}")


def replace_section(body, name, content):
    """節の中身を置き換える。無ければ末尾に足す。"""
    check_section_text(content)
    lines = body.rstrip("\n").split("\n")
    span = _section_span(lines, name)
    new = [f"## {name}"] + (content.strip("\n").split("\n") if content.strip() else []) + [""]
    if span is None:
        return "\n".join(lines + [""] + new).rstrip("\n") + "\n"
    return ("\n".join(lines[:span[0]] + new + lines[span[1]:])).rstrip("\n") + "\n"


def append_to_section(body, name, text):
    """節の末尾に行を足す（テンプレートの〈…〉の見本行は消す）。"""
    check_section_text(text)
    current = get_section(body, name)
    kept = [] if current is None else [ln for ln in current.split("\n") if ln.strip() and "〈" not in ln]
    return replace_section(body, name, "\n".join(kept + [text]))


def split_sections(text):
    """`## 名前` で区切られた入力を {名前: 中身} にする。最初の見出しより前に文字があれば誤り。"""
    out, name, buf = {}, None, []
    for line in text.split("\n"):
        if line.startswith("## "):
            if name is not None:
                out[name] = "\n".join(buf).strip("\n")
            name, buf = line[3:].strip(), []
        elif name is None:
            if line.strip():
                raise SbError(1, "入力は「## 節の名前」で始めてください")
        else:
            buf.append(line)
    if name is not None:
        out[name] = "\n".join(buf).strip("\n")
    return out
