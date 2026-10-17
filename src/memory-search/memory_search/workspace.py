"""置き場。環境変数 WORKSPACE で Workspace を差し替えられる。"""

from __future__ import annotations

import os
from pathlib import Path

# 索引に入れる置き場（Workspace からの相対）。SecondBrain の 90_logs と直下の README・NOW は入れない。
INDEX_ROOTS = (
    "SecondBrain/00_inbox", "SecondBrain/10_daily", "SecondBrain/20_identity", "SecondBrain/30_projects",
    "SecondBrain/40_tasks", "SecondBrain/50_media", "SecondBrain/60_distilled", "company",
)


def workspace_root() -> Path:
    return Path(os.environ.get("WORKSPACE") or "/Users/taro/Workspace")


def index_dir() -> Path:
    return workspace_root() / "data" / "memory-search" / "index"
