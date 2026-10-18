#!/bin/zsh
# agent-setup の試験。~/.claude・~/.codex・data には書かない。
set -e
cd "${0:A:h}"
python3 -m pytest -q tests
