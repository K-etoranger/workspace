"""layers.toml を読む。tomllib が無い版（3.10 以前）では、1行1項目の単純な部分集合だけを読む自前の解析を使う。"""

import re
from functools import lru_cache

from . import SbError
from .paths import REPO_ROOT

LAYERS_FILE = REPO_ROOT / "layers.toml"
TASK_ID_RE = r"[0-9]{8}-[a-z0-9]+(?:-[a-z0-9]+)*"


# ---- 自前の小さな TOML 解析（テーブル見出し・key = value・インライン表・配列・文字列/整数/真偽） ----

_KEY = r'(?:"(?:[^"\\]|\\.)*"|[A-Za-z0-9_\-]+)'


def _split_key(text):
    return [k[1:-1] if k.startswith('"') else k for k in re.findall(_KEY, text)]


def _value(s, i):
    """s[i:] から値を1つ読み、(値, 次の位置) を返す。"""
    while s[i] == " ":
        i += 1
    c = s[i]
    if c == '"':
        m = re.compile(r'"((?:[^"\\]|\\.)*)"').match(s, i)
        return m.group(1).replace('\\"', '"').replace("\\\\", "\\"), m.end()
    if c == "[":
        items, i = [], i + 1
        while True:
            while s[i] in " ,":
                i += 1
            if s[i] == "]":
                return items, i + 1
            v, i = _value(s, i)
            items.append(v)
    if c == "{":
        table, i = {}, i + 1
        while True:
            while s[i] in " ,":
                i += 1
            if s[i] == "}":
                return table, i + 1
            m = re.compile(r"(" + _KEY + r")\s*=\s*").match(s, i)
            v, i = _value(s, m.end())
            table[_split_key(m.group(1))[0]] = v
    m = re.compile(r"true|false|-?\d+").match(s, i)
    if not m:
        raise ValueError(f"読めない値: {s[i:i + 20]!r}")
    t = m.group(0)
    return (t == "true") if t in ("true", "false") else int(t), m.end()


def parse_toml(text):
    root, cur = {}, None
    cur = root
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            if line.startswith("["):
                cur = root
                for k in _split_key(line[1:line.rindex("]")]):
                    cur = cur.setdefault(k, {})
                continue
            m = re.match(r"(" + _KEY + r")\s*=\s*", line)
            v, end = _value(line, m.end())
            rest = line[end:].strip()
            if rest and not rest.startswith("#"):
                raise ValueError("行末に余分な文字")
            cur[_split_key(m.group(1))[0]] = v
        except (AttributeError, IndexError, ValueError) as e:
            raise SbError(5, f"layers.toml {n}行目が読めない: {e}")
    return root


@lru_cache(maxsize=1)
def load_layers():
    text = LAYERS_FILE.read_text(encoding="utf-8")
    try:
        import tomllib  # Python 3.11+
        return tomllib.loads(text)
    except ImportError:
        return parse_toml(text)


# ---- 呼ぶ側の便利関数 ----

# 層の中の名前（ソース・種類・20_identity のファイル）。sb は名前を決めず、この形なら何でも受け付ける。
NAME_RE = r"[a-z0-9_\-]+(?:/[a-z0-9_\-]+)*"


def check_name(name, what):
    if not re.fullmatch(NAME_RE, name or ""):
        raise SbError(1, f"{what}は英小文字・数字・_・-・/ だけ: {name}")
    return name


def kinds():
    """50_media の列を決めてある種類 → 形（daily・has_current・columns）。"""
    return load_layers()["media"]["kinds"]


def kind_spec(name):
    """種類の形。列を決めていない種類は、日別と current を持ち、列は受け取った JSON のキー。"""
    return kinds().get(check_name(name, "種類"), {"label": name, "daily": True, "has_current": True})


def log_kinds():
    return list(load_layers()["logs"]["kinds"])


def files():
    return load_layers()["files"]


# ---- パスの照合 ----

def _token_regex(token):
    simple = {
        "date": r"\d{4}-\d{2}-\d{2}",
        "year": r"\d{4}",
        "month": r"\d{2}",
        "id": TASK_ID_RE,
        "project": r"[^/.][^/]*",
        "name": r"[^/.][^/]*",
    }
    if token in simple:
        return simple[token]
    return NAME_RE  # inbox_messages・inbox_conversations・identity・media_daily・media_current・distill


@lru_cache(maxsize=None)
def _file_regex(pattern):
    out, pos = "", 0
    for m in re.finditer(r"\{(\w+)\}", pattern):
        out += re.escape(pattern[pos:m.start()]) + "(" + _token_regex(m.group(1)) + ")"
        pos = m.end()
    return re.compile(out + re.escape(pattern[pos:]) + r"\Z")


def _form_ok(name, m):
    """列を決めてある種類は、その形（日別・current）を持つときだけ。"""
    flag = {"media_daily": "daily", "media_current": "has_current"}.get(name)
    spec = kinds().get(m.group(1)) if flag else None
    return spec is None or bool(spec.get(flag))


def match_file(rel):
    """vault からの相対パス（/区切り）→ (名前, 設定) か None。"""
    for name, spec in files().items():
        m = _file_regex(spec["path"]).match(rel)
        if m and _form_ok(name, m):
            return name, spec
    return None
