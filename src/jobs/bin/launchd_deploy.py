#!/usr/bin/env python3
"""全repoの定時処理（src/*/launchd/*.plist）を ~/Library/LaunchAgents へ一括で置く。

  launchd_deploy.py            確認だけ（既定）。入れる・置き換える・控えへ移す予定と、読み込み直しのコマンドを出す
  launchd_deploy.py --apply    実際に置き、置いた物がバイト単位で原本と同じかを確かめる

- 原本は <WORKSPACE>/src/*/launchd/com.taro.*.plist と <WORKSPACE>/sb/launchd/com.taro.*.plist。
- LaunchAgents にある com.taro.* で、どの原本にも無い物は控え（既定 ~/Documents/_archive_<日付>/LaunchAgents/）へ移す。
- 同じ Label が2つの repo にあれば何もしないで止める。
- launchctl は呼ばない。読み込み直し（bootout / bootstrap）のコマンドを表示するので、手順書どおりに本人かエージェントが実行する。
環境変数: WORKSPACE・LAUNCH_AGENTS・LAUNCHD_ARCHIVE（試験用）。
"""
from __future__ import annotations

import filecmp
import os
import plistlib
import shutil
import sys
from datetime import date
from pathlib import Path

PREFIX = "com.taro."


def roots():
    ws = Path(os.environ.get("WORKSPACE", "/Users/taro/Workspace"))
    agents = Path(os.environ.get("LAUNCH_AGENTS", Path.home() / "Library/LaunchAgents"))
    archive = Path(os.environ.get("LAUNCHD_ARCHIVE",
                                  Path.home() / "Documents" / f"_archive_{date.today().isoformat()}" / "LaunchAgents"))
    return ws, agents, archive


def sources(ws: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    dup = []
    for plist in sorted([*ws.glob("src/*/launchd/*.plist"), *ws.glob("sb/launchd/*.plist")]):
        with plist.open("rb") as fh:
            label = plistlib.load(fh).get("Label", "")
        if not label.startswith(PREFIX) or plist.stem != label:
            raise SystemExit(f"Label とファイル名が合わない: {plist}")
        if label in found:
            dup.append(f"{label}: {found[label]} / {plist}")
        found[label] = plist
    if dup:
        raise SystemExit("同じ Label が複数の repo にある:\n" + "\n".join(dup))
    return found


def main(argv: list[str]) -> int:
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    unknown = [a for a in argv if a != "--apply"]
    if unknown:
        print(f"launchd_deploy: 知らない引数: {' '.join(unknown)}（何もしていない）", file=sys.stderr)
        return 1
    apply = "--apply" in argv
    ws, agents, archive = roots()
    src = sources(ws)
    installed = {p.stem: p for p in agents.glob(f"{PREFIX}*.plist")} if agents.is_dir() else {}
    install = [l for l in src if l not in installed]
    replace = [l for l in src if l in installed and not filecmp.cmp(src[l], installed[l], shallow=False)]
    retire = sorted(l for l in installed if l not in src)
    uid = os.getuid()
    for l in install:
        print(f"install\t{l}\t{src[l]}")
    for l in replace:
        print(f"replace\t{l}\t{src[l]}")
    for l in retire:
        print(f"archive\t{l}\t{installed[l]} -> {archive}")
    if apply:
        agents.mkdir(parents=True, exist_ok=True)
        for l in install + replace:
            shutil.copyfile(src[l], agents / f"{l}.plist")
        if retire:
            archive.mkdir(parents=True, exist_ok=True)
            for l in retire:
                shutil.move(str(installed[l]), str(archive / installed[l].name))
        bad = [l for l in src if not filecmp.cmp(src[l], agents / f"{l}.plist", shallow=False)]
        if bad:
            print("MISMATCH\t" + " ".join(bad))
            return 1
    for l in retire:
        print(f"# launchctl bootout gui/{uid}/{l}")
    for l in install + replace:
        print(f"# launchctl bootout gui/{uid}/{l} 2>/dev/null; launchctl bootstrap gui/{uid} {agents / (l + '.plist')}")
    changes = len(install) + len(replace) + len(retire)
    print(f"# sources={len(src)} install={len(install)} replace={len(replace)} archive={len(retire)} "
          f"{'APPLIED (byte-equal)' if apply else 'check'}")
    return 0 if apply or not changes else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
