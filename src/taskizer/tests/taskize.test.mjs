// 偽 sb で1回の定時実行を通す（未処理0件まで回す・失敗は位置を進めない）。
import assert from "node:assert/strict";
import test from "node:test";
import { fakeSb, task } from "./helpers.mjs";

const inbox = [1, 2, 3].map((n) => ({ source: "talk", date: "2026-09-29", seq: n, id: `L${n}`, 時刻: `09:0${n}`, 相手: "佐藤", 場所: "読書会", 向き: n === 2 ? "self" : "other", 本文: `本文${n}` }));
const env = fakeSb({ "inbox.json": inbox, "tasks.json": [], "projects.json": [], "show.json": { "talk:2026-09-29": [{ id: "L0", 時刻: "08:00", 相手: "佐藤", 場所: "読書会", 向き: "other", 本文: "前の話" }] } });
const { runOnce, chunkItems } = await import("../src/taskize.mjs");
const NOW = new Date("2026-09-29T10:00:00+09:00");
const ok = (refs, tasks = [], extra = {}) => ({ status: "ok", reviewed_refs: refs, failed_refs: [], tasks, notes: [], summary_lines: [], error_code: "", ...extra });
const only = { talk: 30 };
test.after(() => env.cleanup());

test("新着を1回のモデル呼び出しで確認し、タスクを作って最後の id まで ack する", () => {
  const prompts = [];
  const result = runOnce({ now: NOW, sources: only, runModel: (prompt) => { prompts.push(prompt); return { proposal: ok(["r1", "r2", "r3"], [task()]), exitCode: 0 }; } });
  assert.equal(result.status, "ok");
  assert.equal(result.sources.talk.created.length, 1);
  assert.equal(result.sources.talk.reviewed, 3);
  assert.equal(prompts.length, 1);
  assert.match(prompts[0], /"ref":"r2".*"向き":"self"/u);
  assert.match(prompts[0], /前の話/u); // 同じ場所の直近本文
  const calls = env.calls();
  assert.ok(calls.some((c) => c[0] === "task" && c[1] === "new" && c.includes("taskizer/task-checks")));
  assert.deepEqual(calls.find((c) => c[1] === "ack"), ["inbox", "ack", "--reader", "taskizer", "--source", "talk", "--until", "L3"]);
  assert.ok(calls.some((c) => c[0] === "log" && c[1] === "schedule"));
  assert.equal(env.read("checkpoint.json").talk, 3);
});

test("新着が無ければモデルを呼ばない", () => {
  let called = false;
  const result = runOnce({ now: NOW, sources: only, runModel: () => { called = true; return { proposal: {}, exitCode: 0 }; } });
  assert.equal(called, false);
  assert.equal(result.status, "ok");
});

test("モデルの失敗・崩れた提案では位置を進めず warn", () => {
  env.reset("checkpoint.json", {});
  for (const runModel of [() => ({ proposal: {}, exitCode: 1 }), () => ({ proposal: ok(["r1"]), exitCode: 0 })]) {
    const result = runOnce({ now: NOW, sources: only, runModel });
    assert.equal(result.status, "warn");
    assert.equal(env.read("checkpoint.json").talk, undefined);
  }
});

test("sb が秘密で断った件は隔離して先へ進み、ロックでは止める", () => {
  env.reset("checkpoint.json", {});
  env.reset("tasks.json", []);
  const refused = runOnce({ now: NOW, sources: only, runModel: () => ({ proposal: ok(["r1", "r2", "r3"], [task({ body: "REFUSE を含む本文" })]), exitCode: 0 }) });
  assert.equal(refused.status, "warn");
  assert.equal(refused.sources.talk.quarantined, 1);
  assert.equal(env.read("checkpoint.json").talk, 3);
  assert.equal(env.read("../" + env.dir.split("/").pop() + "/state/taskizer_state.json").quarantined.at(-1).id, "L1");

  env.reset("checkpoint.json", {});
  env.reset("tasks.json", []);
  process.env.FAKE_SB_LOCKED = "1";
  try {
    const locked = runOnce({ now: NOW, sources: only, runModel: () => ({ proposal: ok(["r1", "r2", "r3"], [task()]), exitCode: 0 }) });
    assert.equal(locked.status, "warn");
    assert.match(locked.sources.talk.error, /^sb_2/u);
    assert.equal(env.read("checkpoint.json").talk, undefined);
  } finally {
    delete process.env.FAKE_SB_LOCKED;
  }
});

test("件数の上限ごとに分けて、未処理が0になるまで回す", () => {
  env.reset("checkpoint.json", {});
  let calls = 0;
  const result = runOnce({ now: NOW, sources: { talk: 2 }, runModel: (prompt) => {
    calls += 1;
    const n = (prompt.match(/"ref":"r\d+"/gu) || []).length;
    return { proposal: ok(Array.from({ length: n }, (_, i) => `r${i + 1}`)), exitCode: 0 };
  } });
  assert.equal(calls, 2);
  assert.equal(result.sources.talk.reviewed, 3);
  assert.equal(chunkItems(inbox, 30, 10).length, 1); // 文字数の上限でも切る（最低1件）
});
