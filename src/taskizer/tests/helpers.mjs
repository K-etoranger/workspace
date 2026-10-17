import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

// 偽 sb と一時の状態フォルダを用意する（config.mjs は読み込み時に環境変数を読むので、import より前に呼ぶ）。
export function fakeSb(files = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "taskizer-test-"));
  for (const [name, value] of Object.entries(files)) fs.writeFileSync(path.join(dir, name), JSON.stringify(value));
  process.env.FAKE_SB_DIR = dir;
  process.env.SB_BIN = path.join(ROOT, "tests", "fake-sb.mjs");
  process.env.TASKIZER_STATE_DIR = path.join(dir, "state");
  return {
    dir,
    calls: () => (fs.existsSync(path.join(dir, "calls.jsonl")) ? fs.readFileSync(path.join(dir, "calls.jsonl"), "utf8").trim().split("\n").map((l) => JSON.parse(l)) : []),
    read: (name) => JSON.parse(fs.readFileSync(path.join(dir, name), "utf8")),
    reset: (name, value) => fs.writeFileSync(path.join(dir, name), JSON.stringify(value)),
    cleanup: () => fs.rmSync(dir, { recursive: true, force: true }),
  };
}

export function task(overrides = {}) {
  return {
    ref: "r1", type: "タスク", title: "資料の送付可否を判断する", owner: "本人", state: "open",
    due: "2026-09-29", due_basis: "ai_provisional", due_reason: "所要5分で今日の予定と衝突しないため当日",
    start: "", end: "", priority: "medium", estimate: "本人5分", project: "", wait_for: "", recheck: "",
    body: "佐藤さんから依頼された資料の送付可否を判断する", event_at: "2026-09-29 09:05 JST", source_actor: "佐藤",
    source_target: "トーク 読書会", content_summary: "明日までに資料を送ってほしいという依頼", unknown_details: "資料の範囲は未確認",
    ...overrides,
  };
}
