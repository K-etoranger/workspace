"""書き込む前の検査: 秘密の形の文字列と、会社機密ゲート。

会社機密は config/company_confidential.json の
path_prefixes・path_globs・content_markers・local_only_source_paths を使い、1件の文章を読み取りだけで判定する。
目印の値そのものは出力しない。policy が読めなければ書き込みを断る（fail-closed）。
"""

import fnmatch
import json
import re

from . import SbError
from .paths import config_root, workspace_root

# 伏せ字・置き場の名前だけなら秘密ではない
_REFERENCE = re.compile(r"(?i)redacted|伏せ字|\*{3,}|keychain|キーチェーン|secure|暗号化ストア|<[^>]*>|〈[^〉]*〉")

SECRET_PATTERNS = [
    # パスワードは短くても秘密。ほかの鍵名は、値がトークンの形（16字以上・数字を含む）のときだけ
    ("パスワード", re.compile(r"(?i)\b(?:password|passwd|passcode)[\"']?\s*[:=]\s*[\"']?(?P<v>[^\s\"',]{6,})")),
    ("パスワード", re.compile(r"(?:ログイン)?(?:パスワード|パスコード|暗証番号)\s*(?:[:：=]|は|が)\s*[「『\"']?(?P<v>(?=[!-~]*\d)[!-~]{4,})")),  # 数字を含む値だけ（「パスワードは前と同じ」のような説明文を伏せない）
    ("鍵名=値", re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|session[_-]?token|private[_-]?key|client[_-]?secret|secret|authorization|cookie)[\"']?\s*[:=]\s*[\"']?(?P<v>(?=[A-Za-z0-9._~+/=-]*\d)[A-Za-z0-9._~+/=-]{16,})")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+")),
    ("sk- のAPIキー", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}")),
    ("GitHub トークン", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
    ("Slack トークン", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("AWS キー", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Google API キー", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}")),
    ("秘密鍵", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("Bearer トークン", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{20,}")),
    ("一回きりのコード", re.compile(r"\b\d{4,8}\b(?=\s*(?:が|は)?\s*(?:認証|確認|ワンタイム|OTP|検証)(?:コード|パスワード))|(?i:(?:認証|確認|ワンタイム|検証)(?:コード|パスワード)|OTP|verification code)\s*[:：は]?\s*\d{4,8}\b")),
]


def find_secret(text):
    """最初に見つかった秘密の型の名前と行番号。無ければ None。値は返さない。"""
    for n, line in enumerate(text.split("\n"), 1):
        for name, pattern in SECRET_PATTERNS:
            for m in pattern.finditer(line):
                value = m.groupdict().get("v")
                if value is not None and _REFERENCE.search(value):
                    continue
                return name, n
    return None


# ---- 会社機密ゲート ----

def policy_path():
    return config_root() / "company_confidential.json"


def load_policy():
    path = policy_path()
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raise SbError(4, f"会社機密ゲートの設定が読めないので書き込みを断る: {path}")
    for key in ("enforcement", "path_prefixes", "path_globs", "content_markers", "local_only_source_paths"):
        if key not in policy:
            raise SbError(4, f"会社機密ゲートの設定に {key} が無いので書き込みを断る")
    if policy["enforcement"] != "fail_closed" or not policy["content_markers"]:
        raise SbError(4, "会社機密ゲートの設定が fail_closed でない・目印が空なので書き込みを断る")
    if str(workspace_root() / "company") not in policy["local_only_source_paths"]:
        raise SbError(4, "会社機密ゲートの設定に company/ が無いので書き込みを断る")
    return policy


def _markers(policy):
    markers = [m.replace("\\\\", "\\") for m in policy["content_markers"]]
    markers += [str(v) for v in policy["local_only_source_paths"]]
    return [m for m in dict.fromkeys(markers) if m]


def _path_blocked(rel, policy):
    for prefix in policy["path_prefixes"]:
        if rel == prefix.rstrip("/") or rel.startswith(prefix):
            return True
    for pattern in policy["path_globs"]:
        stem = pattern.split("**")[0]
        if fnmatch.fnmatch(rel, pattern) or ("**" in pattern and stem and rel.startswith(stem)):
            return True
    return False


def mask(text, mark="〈伏せた〉"):
    """秘密の形に当たった値の部分だけを mark に置き換える。(置き換えた文字列, [型の名前…]) を返す。

    inbox add・media add と移行が使う。1件のせいで書き込み全体を断らず、秘密の値だけを残さない。
    最後の check はそのまま効く（ここで伏せ切れない物が残れば断る）。
    """
    hits = []
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        for _ in range(50):  # 1行に複数あっても止まるように上限を置く
            for name, pattern in SECRET_PATTERNS:
                m = next((m for m in pattern.finditer(ln)
                          if not (m.groupdict().get("v") and _REFERENCE.search(m.group("v")))), None)
                if m:
                    a, b = m.span("v") if m.groupdict().get("v") else m.span()
                    ln = ln[:a] + mark + ln[b:]
                    hits.append(name)
                    break
            else:
                break
        lines[i] = ln
    return "\n".join(lines), hits


def check(rel, new_text, old_text=None):
    """書き込みを調べる。新しく入る行だけを見る（手で書かれた既存の行で追記全体を止めない）。"""
    policy = load_policy()
    if _path_blocked(rel, policy):
        raise SbError(4, f"会社機密ゲート: この置き場には書けない: {rel}")
    old = set((old_text or "").split("\n"))
    added = "\n".join(line for line in new_text.split("\n") if line not in old)
    hit = find_secret(added)
    if hit:
        raise SbError(4, f"秘密の形の文字列（{hit[0]}）があるので書き込みを断る。秘密はキーチェーンか暗号化ストアへ")
    # 会社の言葉を含む行は vault には書ける（会社機密ゲートが禁じる置き場には書かない）
