#!/bin/zsh
# agents の試験。配置先は一時フォルダへ向け、~/.claude・~/.codex には書かない。
set -e
cd "${0:A:h}"
python3 -m pytest -q tests
