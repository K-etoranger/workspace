"""Workspace の置き場。環境変数 SB_WORKSPACE / SB_VAULT / SB_DATA / SB_CONFIG で個別に差し替えられる。"""

import os
from pathlib import Path

_DEFAULT_WORKSPACE = "/Users/taro/Workspace"
REPO_ROOT = Path(__file__).resolve().parent.parent


def _env(name):
    value = os.environ.get(name)
    return Path(value) if value else None


def workspace_root() -> Path:
    return _env("SB_WORKSPACE") or Path(_DEFAULT_WORKSPACE)


def vault_root() -> Path:
    return _env("SB_VAULT") or workspace_root() / "SecondBrain"


def data_root() -> Path:
    return _env("SB_DATA") or workspace_root() / "data"


def config_root() -> Path:
    return _env("SB_CONFIG") or workspace_root() / "config"


def sb_data() -> Path:
    """sb 自身の内部データ（ロック・読み取り位置）。"""
    return data_root() / "sb"


def find_named(folder, filename="*.md"):
    """vault の folder の下で filename に合う md → [(folder からの名前, vault からの相対パス, 本文)]。

    名前は、filename が "*.md" ならファイル名（拡張子なし）まで、それ以外はその親フォルダまで。隠しファイルは見ない。
    """
    root, base = vault_root(), vault_root() / folder
    out = []
    for p in sorted(base.rglob(filename)) if base.is_dir() else []:
        rel = p.relative_to(base)
        if not p.is_file() or any(part.startswith(".") for part in rel.parts):
            continue
        name = rel.with_suffix("").as_posix() if filename == "*.md" else rel.parent.as_posix()
        if name == ".":
            continue
        out.append((name, p.relative_to(root).as_posix(), p.read_text(encoding="utf-8")))
    return out
