// 期限の決め方の検査の試験。
import assert from "node:assert/strict";
import test from "node:test";
import { dueDecision, userEffortMinutes } from "../src/duePolicy.mjs";

const NOW = new Date("2026-09-29T20:00:00+09:00");
const base = { state: "open", owner: "本人", due: "2026-09-29", dueBasis: "ai_provisional", dueReason: "短いので当日", estimate: "本人15分", now: NOW };

test("本人分の見積の上限（分）を読む", () => {
  assert.equal(userEffortMinutes("本人15分"), 15);
  assert.equal(userEffortMinutes("本人1〜2時間"), 120);
  assert.equal(userEffortMinutes("本人約1時間30分+エージェント3時間"), 90);
  assert.equal(userEffortMinutes("エージェント30分"), null);
  assert.equal(userEffortMinutes(""), null);
});

test("モデルが選んだ今日・次の論理日をそのまま使う", () => {
  assert.equal(dueDecision(base).policy, "model_same_logical_day");
  assert.equal(dueDecision({ ...base, due: "2026-09-30", dueReason: "もう寝ると本人発言があり翌日" }).policy, "model_deferred_contextual");
});

test("05:00 の境目で有効な2日が決まる", () => {
  const early = new Date("2026-09-30T03:00:00+09:00");
  assert.equal(dueDecision({ ...base, due: "2026-09-29", now: early }).policy, "model_same_logical_day");
  assert.equal(dueDecision({ ...base, due: "2026-09-30", now: early }).policy, "model_deferred_contextual");
  assert.throws(() => dueDecision({ ...base, due: "2026-10-01", now: early }), /outside_current_or_next/);
});

test("論理日と残り時間は sb day に尋ねる（04:59 はまだ前の日、05:00 から次の日）", () => {
  const at459 = dueDecision({ ...base, due: "2026-09-29", now: new Date("2026-09-30T04:59:00+09:00") });
  assert.equal(at459.policy, "model_same_logical_day");
  assert.equal(at459.remainingMinutes, 1);
  const at500 = new Date("2026-09-30T05:00:00+09:00");
  assert.equal(dueDecision({ ...base, due: "2026-09-30", now: at500 }).policy, "model_same_logical_day");
  assert.throws(() => dueDecision({ ...base, due: "2026-09-29", now: at500 }), /outside_current_or_next/);
});

test("今日・次の論理日の外の AI 仮期限は断る", () => {
  assert.throws(() => dueDecision({ ...base, due: "2026-10-05" }), /model_due_outside_current_or_next_logical_day/);
});

test("正式な期限と本人の確定日は遠くても残す", () => {
  assert.equal(dueDecision({ ...base, due: "2026-10-20", dueBasis: "external_formal" }).due, "2026-10-20");
  assert.equal(dueDecision({ ...base, due: "2026-10-20", dueBasis: "user_confirmed" }).policy, "user_confirmed");
});

test("本人の AI 仮期限は見積と理由が無ければ断る", () => {
  assert.throws(() => dueDecision({ ...base, estimate: "" }), /user_effort_estimate_unparseable/);
  assert.throws(() => dueDecision({ ...base, dueReason: " " }), /model_due_reason_missing/);
});

test("エージェント担当の AI 仮期限は日付を変えない", () => {
  assert.equal(dueDecision({ ...base, owner: "エージェント", estimate: "エージェント3時間", due: "2026-10-03" }).policy, "agent_go_unconfirmed");
});

test("待ちは期限を持たない", () => {
  assert.equal(dueDecision({ ...base, state: "waiting", due: "", dueBasis: "not_applicable" }).due, "");
  assert.throws(() => dueDecision({ ...base, state: "waiting", due: "2026-09-30", dueBasis: "not_applicable" }), /waiting_task_has_due/);
  assert.throws(() => dueDecision({ ...base, dueBasis: "not_applicable" }), /runnable_task_due_basis_not_applicable/);
  assert.throws(() => dueDecision({ ...base, due: "" }), /invalid_runnable_task_due/);
});

test("会社でしか確かめられない本人タスクは出勤日に置けるので、今日・翌日の範囲外でも通す", () => {
  const now = new Date("2026-09-30T10:00:00+09:00");
  const base = { state: "open", owner: "本人", dueBasis: "ai_provisional", dueReason: "次の出勤日に確認", estimate: "本人15分", now };
  assert.equal(dueDecision({ ...base, due: "2026-10-05", text: "会社PCで書類を確認" }).policy, "workday_constraint");
  assert.throws(() => dueDecision({ ...base, due: "2026-10-05", dueReason: "余裕があるので", text: "買い物" }),
    /model_due_outside_current_or_next_logical_day/);
});
