// 本物の sb（開発中は build/sb/bin/sb、TASKIZER_TEST_SB で差し替え）を一時の SecondBrain に向けて通す。
// SB_WORKSPACE は本物のまま（会社機密ゲートの設定が本物の company/ のパスを持つため）。
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { ROOT, task } from "./helpers.mjs";

const SB = process.env.TASKIZER_TEST_SB || path.join(os.homedir(), "Workspace", "sb", "bin", "sb");
const POLICY = path.join(os.homedir(), "Workspace", "config", "company_confidential.json");
const skip = !fs.existsSync(SB) || !fs.existsSync(POLICY);
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "taskizer-sb-"));
for (const d of ["v", "d", "c"]) fs.mkdirSync(path.join(tmp, d));
if (!skip) fs.copyFileSync(POLICY, path.join(tmp, "c", "company_confidential.json"));
Object.assign(process.env, {
  SB_BIN: SB, SB_VAULT: path.join(tmp, "v"), SB_DATA: path.join(tmp, "d"), SB_CONFIG: path.join(tmp, "c"),
  SB_NOW: "2026-09-29T10:00+09:00", TASKIZER_STATE_DIR: path.join(tmp, "state"),
});
test.after(() => fs.rmSync(tmp, { recursive: true, force: true }));
const sb = (args, input) => spawnSync(SB, args, { encoding: "utf8", input });

test("inbox の新着から本物の sb でタスク・予定・待ちを作り、読み取り位置を進める", { skip }, async () => {
  const { runOnce } = await import("../src/taskize.mjs");
  const lines = [
    { id: "L1", 時刻: "2026-09-29T09:05+09:00", 相手: "佐藤", 場所: "読書会", 向き: "other", 本文: "明日までに資料を送ってほしい", 元データ: "data/importer/raw/talk/a.json" },
    { id: "L2", 時刻: "2026-09-29T09:06+09:00", 相手: "佐藤", 場所: "読書会", 向き: "self", 本文: "10/3 18時の朗読会行きます", 元データ: "data/importer/raw/talk/a.json" },
  ].map((x) => JSON.stringify(x)).join("\n");
  assert.equal(sb(["inbox", "add", "--source", "talk", "--stdin", "--by", "importer/talk"], lines).status, 0);
  const proposal = { status: "ok", reviewed_refs: ["r1", "r2"], failed_refs: [], notes: [], summary_lines: [], error_code: "", tasks: [
    task(),
    task({ ref: "r2", type: "予定", title: "朗読会", start: "2026-10-03 18:00", due: "", due_basis: "not_applicable", estimate: "" }),
    task({ ref: "r2", title: "朗読会の持ち物を相手に確認", state: "waiting", due: "", due_basis: "not_applicable", due_reason: "", estimate: "", wait_for: "相手の返事", recheck: "2026-10-01" }),
  ] };
  const result = runOnce({ now: new Date("2026-09-29T10:00+09:00"), sources: { talk: 30 }, runModel: () => ({ proposal, exitCode: 0 }) });
  assert.equal(result.status, "ok", JSON.stringify(result));
  const tasks = JSON.parse(sb(["task", "list", "--json"]).stdout).tasks;
  assert.equal(tasks.length, 3);
  const byTitle = Object.fromEntries(tasks.map((t) => [t["件名"], t]));
  assert.equal(byTitle["資料の送付可否を判断する"]["期限"], "2026-09-29 23:59");
  assert.equal(byTitle["資料の送付可否を判断する"]["見積"], "本人5分");
  assert.equal(byTitle["資料の送付可否を判断する"]["書いた物"], "taskizer/task-checks");
  assert.equal(byTitle["朗読会"]["区分"], "予定");
  assert.equal(byTitle["朗読会の持ち物を相手に確認"]["状態"], "waiting");
  assert.equal(byTitle["朗読会の持ち物を相手に確認"]["次の確認"], "2026-10-01");
  assert.deepEqual(JSON.parse(sb(["inbox", "list", "--source", "talk", "--since", "taskizer", "--json"]).stdout).items, []);
  assert.ok(fs.existsSync(path.join(tmp, "v", "90_logs", "schedule", "taskizer.md")));

  // もう一度同じ件が来ても（位置を戻しても）同じタスクは作らない。
  fs.rmSync(path.join(tmp, "d", "sb", "checkpoints"), { recursive: true, force: true });
  const again = runOnce({ now: new Date("2026-09-29T12:05+09:00"), sources: { talk: 30 }, runModel: () => ({ proposal, exitCode: 0 }) });
  assert.equal(again.sources.talk.created.length, 0);
  assert.equal(JSON.parse(sb(["task", "list", "--json"]).stdout).tasks.length, 3);
});

test("自分が作ったタスクを、本人の返事を根拠に本物の sb で閉じる。本人が作ったタスクは閉じない", { skip }, async () => {
  const { runOnce } = await import("../src/taskize.mjs");
  assert.equal(sb(["task", "new", "--title", "本人が作った件", "--owner", "本人", "--due", "2026-09-30", "--id", "20260929-mine", "--by", "claude"]).status, 0);
  const own = JSON.parse(sb(["task", "list", "--json"]).stdout).tasks.find((t) => t["件名"] === "資料の送付可否を判断する");
  assert.equal(own["作った物"], "taskizer/task-checks");
  const line = JSON.stringify({ id: "L3", 時刻: "2026-09-29T11:00+09:00", 相手: "佐藤", 場所: "読書会", 向き: "self", 本文: "資料送りました", 元データ: "data/importer/raw/talk/a.json" });
  assert.equal(sb(["inbox", "add", "--source", "talk", "--stdin", "--by", "importer/talk"], line).status, 0);
  const proposal = { status: "ok", reviewed_refs: ["r1"], failed_refs: [], tasks: [], notes: [], updates: [], summary_lines: [], error_code: "", closes: [
    { ref: "r1", task_id: own.ID, result: "done", reason: "本人が資料を送ったと伝えた" },
    { ref: "r1", task_id: "20260929-mine", result: "done", reason: "x" },
  ] };
  const result = runOnce({ now: new Date("2026-09-29T12:10+09:00"), sources: { talk: 30 }, runModel: () => ({ proposal, exitCode: 0 }) });
  assert.equal(result.status, "ok", JSON.stringify(result));
  assert.deepEqual(result.sources.talk.closed, [own.ID]);
  const after = JSON.parse(sb(["task", "list", "--all", "--json"]).stdout).tasks;
  assert.equal(after.find((t) => t.ID === own.ID)["状態"], "done");
  assert.equal(after.find((t) => t.ID === "20260929-mine")["状態"], "open");
});
