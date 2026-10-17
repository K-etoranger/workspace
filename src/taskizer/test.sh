#!/bin/sh
# 全部の試験。外部サービス・本物の SecondBrain には触れない（sb は偽物か、一時フォルダへ向けた開発中の sb）。
set -e
cd "$(dirname "$0")"
for f in src/*.mjs bin/*.mjs; do node --check "$f"; done
node --test tests/*.test.mjs
