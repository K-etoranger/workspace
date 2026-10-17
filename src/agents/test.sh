#!/bin/zsh
# agents の試験。一時フォルダだけを使い、~/.claude・~/.codex には書かない。
set -e
cd "${0:A:h}"
python3 -m pytest -q tests
