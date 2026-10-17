"""書き込み: ロック → 一時ファイル → 検証 → 置き換え。途中で止まっても元のファイルは壊れない。

1回の操作（例: タスク完了 = archive へ書く + active を消す + 次の回を作る）は Tx にまとめる。
全部の書き込みを検査してから置き換えを始める。
"""

import fcntl
import hashlib
import os
import time
from pathlib import Path

from . import SbError, frontmatter, guard, layers
from .paths import sb_data, vault_root

TMP_MARK = ".sb-tmp-"


def lock_path(key):
    safe = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return sb_data() / "locks" / f"{safe}.lock"


def acquire(key):
    """ファイルごとのロック。取れなければ SB_LOCK_WAIT 秒（既定 3）待ってから終了コード 2。"""
    path = lock_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
    deadline = time.monotonic() + float(os.environ.get("SB_LOCK_WAIT", "3"))
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            if time.monotonic() >= deadline:
                os.close(fd)
                raise SbError(2, f"他の書き込み中: {key}")
            time.sleep(0.05)


def release(fd):
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)


def atomic_write(path, text):
    """同じフォルダの一時ファイルに書き、fsync して置き換える。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}{TMP_MARK}{os.getpid()}-{os.urandom(3).hex()}")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        if tmp.read_text(encoding="utf-8") != text:
            raise SbError(5, f"一時ファイルの読み戻しが一致しない: {path}")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def required_headings(template):
    """テンプレートの固定の `## 見出し`（〈〉や {{}} を含まない物）。"""
    if not template:
        return []
    from .templates import load
    _, body = frontmatter.parse(load(template))
    return [h for h in frontmatter.headings(body) if "〈" not in h and "{{" not in h]


def validate(rel, text, spec):
    """頭書き（形式・種類）とテンプレートの見出しがそろっているか。md 以外は調べない。"""
    if not rel.endswith(".md"):
        return
    meta, body = frontmatter.parse(text)
    if meta.get("形式") is None:
        raise SbError(1, f"頭書きに 形式 が無い: {rel}")
    if meta.get("種類") != spec["kind"]:
        raise SbError(1, f"種類が {meta.get('種類')}（{spec['kind']} のはず）: {rel}")
    if not any(line.startswith("# ") for line in body.split("\n")):
        raise SbError(1, f"題名（# 行）が無い: {rel}")
    have = frontmatter.headings(body)
    for h in required_headings(spec.get("template")):
        if h not in have:
            raise SbError(1, f"見出し「## {h}」が無い: {rel}")


class Tx:
    """1回の操作。read/put/delete はその場でロックを取り、commit で検査してから一度に置き換える。"""

    def __init__(self, cmd, by="", dry_run=False, allow_readonly=(), header_fix=False):
        # header_fix: sb check --fix 用。層・読み取り専用・見出しは問わず、秘密と会社機密だけ調べる。
        self.cmd, self.by, self.dry_run, self.header_fix = cmd, by, dry_run, header_fix
        self.allow_readonly = set(allow_readonly)
        self.locks, self.ops, self.base = {}, {}, {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        for fd in self.locks.values():
            release(fd)
        self.locks.clear()

    def _lock(self, rel):
        # ロックは層の下の1段（例: 50_media/movies・40_tasks/active）ごと。1回の操作で何千ファイルを
        # 書いても開くロックは数個で済む（launchd の開けるファイル数の上限に当たらない）。
        key = "/".join(Path(rel).parts[:2])
        if key not in self.locks:
            self.locks[key] = acquire("vault:" + key)
        if rel not in self.base:
            p = vault_root() / rel
            self.base[rel] = p.read_text(encoding="utf-8") if p.exists() else None

    def read(self, rel):
        self._lock(rel)
        if rel in self.ops:
            return self.ops[rel]
        return self.base[rel]

    def exists(self, rel):
        return self.read(rel) is not None

    def put(self, rel, text):
        self._lock(rel)
        self.ops[rel] = text

    def delete(self, rel):
        self._lock(rel)
        self.ops[rel] = None

    def _check(self, rel, text):
        if self.header_fix:
            if text is not None:
                guard.check(rel, text, self.base.get(rel))
            return
        found = layers.match_file(rel)
        if not found:
            raise SbError(4, f"決まりに無い置き場には書けない: {rel}")
        name, spec = found
        if self.cmd not in spec["cmd"].split():
            raise SbError(4, f"sb {self.cmd} はこの層に書けない: {rel}")
        if spec.get("readonly") and rel not in self.allow_readonly:
            raise SbError(4, f"archive は読み取り専用: {rel}")
        if text is None:
            return
        validate(rel, text, spec)
        guard.check(rel, text, self.base.get(rel))

    def commit(self, before_apply=None):
        """全部を検査し、dry-run でなければ（before_apply を呼んでから）置き換える。

        [{"path", "action": write|delete|same}] を返す（dry-run では "text" も）。
        """
        plan = []
        for rel, text in self.ops.items():
            self._check(rel, text)
            if text is None:
                action = "delete" if self.base.get(rel) is not None else "same"
            else:
                action = "same" if text == self.base.get(rel) else "write"
            entry = {"path": rel, "action": action}
            if self.dry_run and action == "write":
                entry["text"] = text
            plan.append(entry)
        if not self.dry_run:
            if before_apply:
                before_apply()
            for e in plan:
                if e["action"] == "write":
                    atomic_write(vault_root() / e["path"], self.ops[e["path"]])
            for e in plan:
                if e["action"] == "delete":
                    p = vault_root() / e["path"]
                    p.unlink()
                    _prune(p.parent)
        return plan


def _prune(folder):
    """空になったフォルダを消す（vault の直下の層までは消さない）。"""
    root = vault_root()
    while folder != root and len(folder.relative_to(root).parts) > 2:
        try:
            folder.rmdir()
        except OSError:
            return
        folder = folder.parent


def write_data(path, text):
    """data/sb の内部ファイル（読み取り位置など）。ロックは呼ぶ側。"""
    atomic_write(path, text)


def touch(meta, by):
    """頭書きの 更新・書いた物 を今にする。"""
    from .logical_day import stamp
    meta["更新"] = stamp()
    if by:
        meta["書いた物"] = by
    return meta


def new_doc(template, by, **values):
    from .logical_day import stamp
    from .templates import render
    from . import frontmatter
    text = render(template, 更新=stamp(), 書いた物=by, **values)
    meta, body = frontmatter.parse(text)
    return frontmatter.dump(meta, body) if meta else text  # 値を YAML として読める形に揃える
