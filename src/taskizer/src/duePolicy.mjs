// 期限の決め方の検査。
// モデルが文脈（所要・時刻・予定・睡眠や体調の本人発言）から選んだ日を上書きせず、範囲と根拠だけを確かめる。
import { addDays, sbDay } from "./day.mjs";

export const DUE_BASES = new Set(["ai_provisional", "external_formal", "user_confirmed", "not_applicable"]);

function upperBound(text, unit) {
  const range = text.match(new RegExp(`(\\d+(?:\\.\\d+)?)\\s*(?:[-~～〜]|から)\\s*(\\d+(?:\\.\\d+)?)${unit}`, "u"));
  if (range) return Number(range[2]);
  const single = text.match(new RegExp(`(\\d+(?:\\.\\d+)?)${unit}`, "u"));
  return single ? Number(single[1]) : 0;
}

// 「本人15分」「本人1〜2時間 / エージェント30分」の本人分の上限（分）。無ければ null。
export function userEffortMinutes(estimate) {
  const raw = String(estimate || "").normalize("NFKC").match(/本人([^/／+＋]*?)(?:エージェント|[/／+＋]|$)/u)?.[1];
  if (!raw) return null;
  const segment = raw.replace(/(?:約|以内|程度|ぐらい|くらい|\s)/gu, "");
  const minutes = Math.ceil(upperBound(segment, "時間") * 60 + upperBound(segment, "分"));
  return minutes > 0 ? minutes : null;
}

// 会社でしか確かめられない入力に頼る本人タスクは、
// 本人の出勤日に置くので「今日か翌日」の範囲の検査をしない。
const WORKDAY_CONSTRAINT = /会社PC|出勤日|会社で(?:しか|だけ)|会社に(?:行|出)/u;

export function dueDecision({ state, owner, due, dueBasis, dueReason, estimate, text = "", now = new Date() }) {
  if (!DUE_BASES.has(dueBasis)) throw new Error("invalid_due_basis");
  if (state === "waiting") {
    if (dueBasis !== "not_applicable" || due) throw new Error("waiting_task_has_due");
    return { due: "", policy: "not_applicable" };
  }
  if (!/^\d{4}-\d{2}-\d{2}$/u.test(String(due || ""))) throw new Error("invalid_runnable_task_due");
  if (dueBasis === "not_applicable") throw new Error("runnable_task_due_basis_not_applicable");
  if (dueBasis !== "ai_provisional") return { due, policy: dueBasis };
  if (owner === "エージェント") return { due, policy: "agent_go_unconfirmed" };
  if (WORKDAY_CONSTRAINT.test(`${text}\n${dueReason || ""}`)) return { due, policy: "workday_constraint" };
  // 本人・本人+エージェントの AI 仮期限は、今の論理日か次の論理日だけ。
  const minutes = userEffortMinutes(estimate);
  if (!minutes) throw new Error("user_effort_estimate_unparseable");
  if (!String(dueReason || "").trim()) throw new Error("model_due_reason_missing");
  const { date: today, end } = sbDay(now);
  if (due !== today && due !== addDays(today, 1)) throw new Error("model_due_outside_current_or_next_logical_day");
  const remaining = Math.max(0, Math.floor((new Date(end).getTime() - now.getTime()) / 60_000));
  return { due, policy: due === today ? "model_same_logical_day" : "model_deferred_contextual", estimateMinutes: minutes, remainingMinutes: remaining };
}
