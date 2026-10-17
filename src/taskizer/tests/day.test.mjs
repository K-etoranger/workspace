import assert from "node:assert/strict";
import test from "node:test";
import { fakeSb } from "./helpers.mjs";

const fake = fakeSb();
const { sbDay, addDays } = await import("../src/day.mjs");

test("sbDay は sb day --at を呼ぶだけ（偽 sb から本物の sb へ）", () => {
  assert.deepEqual(sbDay(new Date("2026-09-30T03:00:00+09:00")),
    { date: "2026-09-29", start: "2026-09-29T05:00+09:00", end: "2026-09-30T05:00+09:00" });
  const call = fake.calls().at(-1);
  assert.deepEqual(call.slice(0, 2), ["day", "--at"]);
  fake.cleanup();
});

test("addDays は暦の日付だけを動かす（月・年の境目）", () => {
  assert.equal(addDays("2026-09-30", 1), "2026-10-01");
  assert.equal(addDays("2026-01-01", -1), "2025-12-31");
});
