// モデルの提案を決定的に検査し、sb のコマンド（引数の列）へ変える。ここは何も書かない。
// 検査は ref の許可一覧・全件確認・セル検査・伏せ字・期限の方針。書くのはタスク（予定を含む）と既存タスクへの経緯1行だけ。
import crypto from "node:crypto";
import { dueDecision } from "./duePolicy.mjs";
import { redactPii } from "./redact.mjs";

// URL や実行できる markup はセルへ入れない（伏せ字でなく、その ref を隔離する）。
const FORBIDDEN_TEXT = /(?:https?:\/\/|`{3}|<script)/iu;
// 仕組みの語は外部本文由来のタスクに出る正当な理由が無いので、出た時点で隔離。
const INFRA_TERM = /(?:automation|cron|crontab|launchd|LaunchAgent|launchctl|webhook|定時実行|自動実行|外部送信)/iu;
// 日常語は、エージェントへの命令の形を伴うときだけ隔離（事実の記述は通す）。
const SENSITIVE_TERM = /(?:購入|決済|送金|振込|返信を送|予約を確定|削除|設定変更|token|credential|Keychain|パスワード)/iu;
const AGENT_IMPERATIVE = /(?:してください|して下さい|してほしい|お願いします|せよ|しろ|すること|至急|直ちに|must\s|please\s)/iu;
const PRIVATE_KEY_BLOCK = /(?:-{0,5}\s*)?BEGIN (?:RSA|OPENSSH|PRIVATE)(?: PRIVATE)? KEY(?:\s*-{0,5})?.*?(?=(?:(?:-{0,5}\s*)?END (?:RSA|OPENSSH|PRIVATE)(?: PRIVATE)? KEY(?:\s*-{0,5})?|$))/giu;
const SECRET_ASSIGNMENT = /(?:password|passwd|pass|パスワード|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|authorization|bearer|cookie|otp|secret)\s*(?:[:：=]|\bis\b|は|[(（])\s*(?:"[^"]*"|'[^']*'|[^\s,;。、「」【】]+?)(?=(?:を|が|は|へ|と|で|から|について|です|でした|。|、|【|\s|$))/giu;
const REVERSE_PASSWORD_ASSIGNMENT = /[^\s,;。、「」【】]+?(?=\s*(?:が|は)\s*(?:ログイン)?パスワード)/giu;
const SLACK_TOKEN = /xox[a-z]-[A-Za-z0-9-]+/gu;
const CREDENTIAL_LIKE_RUN = /(?:eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}|[A-Za-z0-9_+=/-]{32,})/gu;

export class CellError extends Error {
  constructor(label, check) {
    super(`${check === "shape" ? "invalid" : "unsafe"}_${label}`);
    this.label = label;
    this.check = check;
  }
}

function operationalCommand(text) {
  return INFRA_TERM.test(text) || (SENSITIVE_TERM.test(text) && AGENT_IMPERATIVE.test(text));
}

function redactSensitive(text) {
  return redactPii(text)
    .replace(PRIVATE_KEY_BLOCK, "[秘密情報省略]")
    .replace(SECRET_ASSIGNMENT, "[秘密情報省略]")
    .replace(REVERSE_PASSWORD_ASSIGNMENT, "[秘密情報省略]")
    .replace(SLACK_TOKEN, "[秘密情報省略]")
    .replace(CREDENTIAL_LIKE_RUN, "[秘密情報省略]")
    .replace(/\[REDACTED_[A-Z_]+\]/gu, "[秘密情報省略]");
}

// executable = タスクの件名・本文（命令混入の検査もする）。説明・根拠の欄は秘密・URL の検査だけ。
export function cleanCell(value, label, max, { executable = false, stats } = {}) {
  const text = String(value || "").normalize("NFKC").replace(/\s+/gu, " ").trim();
  if (!text || /[|\r\n]/u.test(text)) throw new CellError(label, "shape");
  if (FORBIDDEN_TEXT.test(text)) throw new CellError(label, "FORBIDDEN_TEXT");
  const redacted = redactSensitive(text);
  if (!redacted || redacted.length > max) throw new CellError(label, "shape");
  if (executable && operationalCommand(redacted)) throw new CellError(label, "OPERATIONAL_COMMAND");
  if (stats && redacted !== text) stats.redactions += 1;
  return redacted;
}

const PRIORITY = { high: "高", medium: "中", low: "低" };
const OWNERS = new Set(["本人", "エージェント", "本人+エージェント"]);
const DATE = /^\d{4}-\d{2}-\d{2}$/u;
const DATETIME = /^\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2})?$/u;

export function normalizeTitle(value) {
  return String(value || "").normalize("NFKC").replace(/\s+/gu, "").toLowerCase();
}

export function taskId(item, index) {
  const hash = crypto.createHash("sha256").update(`${item.source}\0${item.id}\0${index}`).digest("hex").slice(0, 10);
  return `${item.date.replaceAll("-", "")}-${item.source.replaceAll("_", "-")}-${hash}`;
}

export function sourceLabel(item) {
  return `00_inbox/messages/${item.source}/${item.date}.md id:${item.id}`;
}

// 全件確認の検査。1つでも崩れていれば提案全体を使わない（checkpoint を進めない）。
export function validateReview(proposal, refs) {
  const reviewed = proposal?.reviewed_refs;
  const failed = proposal?.failed_refs;
  if (!Array.isArray(reviewed) || !Array.isArray(failed)) throw new Error("missing_review_sets");
  const all = [...reviewed, ...failed];
  if (new Set(all).size !== all.length) throw new Error("duplicate_or_overlapping_ref");
  if (all.some((ref) => !refs.has(ref))) throw new Error("ref_not_in_batch");
  if ([...refs.keys()].some((ref) => !all.includes(ref))) throw new Error("incomplete_review");
  return new Set(failed);
}

function taskArgs(m, item, index, ctx) {
  const { stats, now } = ctx;
  const state = m.state;
  if (state !== "open" && state !== "waiting") throw new CellError("task_state", "shape");
  if (!OWNERS.has(m.owner)) throw new CellError("task_owner", "shape");
  const type = m.type === "予定" ? "予定" : "タスク";
  const title = cleanCell(m.title, "task_title", 120, { executable: true, stats });
  const body = cleanCell(m.body, "task_body", 1000, { executable: true, stats });
  const d = (key, label, max) => cleanCell(m[key], label, max, { stats });
  const context = [
    `- 発生・通知日時: ${d("event_at", "task_event_at", 120)}`,
    `- 主体: ${d("source_actor", "task_source_actor", 160)}`,
    `- 対象・場所: ${d("source_target", "task_source_target", 240)}`,
    `- 内容の要点: ${d("content_summary", "task_content_summary", 500)}`,
    `- 未確認: ${d("unknown_details", "task_unknown_details", 300)}`,
  ];
  const args = ["task", "new", "--title", title, "--owner", m.owner, "--type", type,
    "--priority", PRIORITY[m.priority] || "中", "--source", sourceLabel(item), "--id", taskId(item, index), "--by", ctx.by];
  let policy = "schedule";
  if (type === "予定") {
    if (!DATETIME.test(String(m.start || ""))) throw new CellError("schedule_start", "shape");
    if (m.end && !DATETIME.test(String(m.end))) throw new CellError("schedule_end", "shape");
    if (state !== "open") throw new CellError("schedule_state", "shape");
    args.push("--start", m.start, ...(m.end ? ["--end", m.end] : []));
  } else {
    const dueReason = m.due_reason ? d("due_reason", "task_due_reason", 300) : "";
    const estimate = m.estimate ? cleanCell(m.estimate, "task_estimate", 60, { stats }) : "";
    if (state === "open" && !estimate) throw new CellError("task_estimate", "shape");
    if (["本人", "本人+エージェント"].includes(m.owner) && state === "open" && !/本人/u.test(estimate)) {
      throw new CellError("task_estimate", "shape");
    }
    let decision;
    try {
      decision = dueDecision({ state, owner: m.owner, due: m.due, dueBasis: m.due_basis, dueReason, estimate, now,
        text: [m.title, m.content_summary, m.text].filter(Boolean).join("\n") });
    } catch (error) {
      throw Object.assign(new CellError("task_due", "shape"), { message: error.message });
    }
    policy = decision.policy;
    if (decision.due) args.push("--due", decision.due);
    if (estimate) args.push("--estimate", estimate);
    if (m.due_basis === "ai_provisional") context.push(`- 期限: AI仮期限（本人の正式期限ではない） — ${dueReason || "理由未記録"}`);
    else if (dueReason) context.push(`- 期限の根拠: ${dueReason}`);
  }
  if (m.project && ctx.projects.has(m.project)) args.push("--project", m.project);
  const text = `${body}\n\n${context.join("\n")}`;
  args.push("--text", text);
  const followUp = [];
  if (state === "waiting") {
    if (!DATE.test(String(m.recheck || ""))) throw new CellError("task_recheck", "shape");
    followUp.push(["task", "wait", taskId(item, index), "--for", d("wait_for", "task_wait_for", 200), "--recheck", m.recheck, "--by", ctx.by]);
  }
  return { args, followUp, title, policy };
}

// 自分（by）が作った active のタスクだけを直す・閉じる。ほかのタスクは経緯を足すだけ。
// state: この回で変えた後の状態（ID → 状態）。同じ回の2つ目の直しが古い状態で判断しないように持ち回る。
function ownTaskActions(kind, m, item, ctx, state) {
  const id = m.task_id;
  const why = `${cleanCell(m.reason, `${kind}_reason`, 300, { executable: true, stats: ctx.stats })}（根拠: ${sourceLabel(item)}）`;
  if (kind === "close") {
    if (m.result === "done") return [["task", "done", id, "--text", why, "--by", ctx.by]];
    if (m.result === "cancelled") return [["task", "cancel", id, "--reason", why, "--by", ctx.by]];
    throw new CellError("close_result", "shape");
  }
  const out = [];
  const change = [];
  if (m.title) change.push("--title", cleanCell(m.title, "update_title", 120, { executable: true, stats: ctx.stats }));
  if (m.due) {
    if (!DATE.test(m.due)) throw new CellError("update_due", "shape");
    change.push("--due", m.due);
  }
  for (const key of ["start", "end"]) {
    if (!m[key]) continue;
    if (!DATETIME.test(m[key])) throw new CellError(`update_${key}`, "shape");
    change.push(`--${key}`, m[key]);
  }
  if (m.state === "waiting") {
    if (!DATE.test(String(m.recheck || ""))) throw new CellError("update_recheck", "shape");
    out.push(["task", "wait", id, "--for", cleanCell(m.wait_for, "update_wait_for", 200, { stats: ctx.stats }), "--recheck", m.recheck, "--by", ctx.by]);
  } else if (m.state === "open" && state.get(id) !== "open") {
    out.unshift(["task", "reopen", id, "--by", ctx.by]);
  }
  if (change.length) out.unshift(["task", "update", id, ...change, "--by", ctx.by]);
  out.push(["task", "note", id, "--text", why, "--by", ctx.by]);
  return out;
}

// 提案 → 実行する sb コマンドの一覧。refs: Map(ref → inbox の1件)。tasks: sb task list --all の結果。
// origins: 自分のタスクの元の {source, place}（context.mjs の ownTaskOrigins）。直す・閉じる根拠は、本人の発言か、元と同じ場所の連絡だけ。
export function planProposal(proposal, refs, { tasks, projects, now = new Date(), by = "taskizer", origins = new Map() }) {
  const failed = validateReview(proposal, refs);
  const order = [...refs.keys()];
  const firstFailed = order.findIndex((ref) => failed.has(ref));
  const stats = { redactions: 0 };
  const ctx = { stats, now, by, projects: new Set(projects) };
  const existingIds = new Set(tasks.map((t) => t.ID));
  const activeIds = new Set(tasks.filter((t) => !t.archived).map((t) => t.ID));
  const activeTitles = new Set(tasks.filter((t) => !t.archived).map((t) => normalizeTitle(t["件名"])));
  const own = new Map(tasks.filter((t) => !t.archived && t["作った物"] === by).map((t) => [t.ID, t]));
  const ownState = new Map([...own].map(([id, t]) => [id, t["状態"]]));
  const closedIds = new Set();
  const evidenceOk = (item, id) => {
    const origin = origins.get(id);
    return item["向き"] === "self" || Boolean(origin?.place && origin.source === item.source && origin.place === item["場所"]);
  };
  const byRef = new Map();
  for (const [kind, list] of [["task", proposal.tasks], ["note", proposal.notes], ["update", proposal.updates], ["close", proposal.closes]]) {
    for (const m of Array.isArray(list) ? list : []) {
      if (!refs.has(m?.ref)) throw new Error("mutation_ref_not_in_batch");
      if (failed.has(m.ref)) throw new Error("mutation_from_failed_ref");
      if (!byRef.has(m.ref)) byRef.set(m.ref, []);
      byRef.get(m.ref).push({ kind, m });
    }
  }
  const actions = [];
  const quarantined = [];
  const skipped = [];
  // 形の誤り（期限の方針・欄の欠け）は、その ref から先を今回は使わず次回もう一度モデルに見せる。
  // 安全の検査（URL・命令の混入）に落ちた ref だけは隔離して先へ進む（毎回同じ1件で止まらないように）。
  let stopAt = firstFailed < 0 ? order.length : firstFailed;
  const retry = [];
  for (let i = 0; i < stopAt; i += 1) {
    const ref = order[i];
    if (!byRef.has(ref)) continue;
    const item = refs.get(ref);
    const titles = new Set(activeTitles);
    try {
      const planned = [];
      const states = new Map();
      let index = 0;
      for (const { kind, m } of byRef.get(ref)) {
        if (kind === "update" || kind === "close") {
          // 自分が作っていない・もう閉じたタスクには何もしない（止めずに見送る）。
          if (!own.has(m.task_id) || closedIds.has(m.task_id) || states.get(m.task_id) === "closed") { skipped.push({ ref, id: m.task_id, reason: `${kind}_not_own_open_task` }); continue; }
          // 外の連絡だけで、別の場所から作ったタスクを動かさない（なりすまし・広告で閉じられないように）。
          if (!evidenceOk(item, m.task_id)) { skipped.push({ ref, id: m.task_id, reason: `${kind}_evidence_not_self_or_same_place` }); continue; }
          const current = new Map([...ownState, ...states]);
          for (const args of ownTaskActions(kind, m, item, ctx, current)) planned.push({ ref, kind, id: m.task_id, args });
          states.set(m.task_id, kind === "close" ? "closed" : m.state || current.get(m.task_id));
          continue;
        }
        if (kind === "note") {
          if (!activeIds.has(m.task_id)) throw new CellError("note_task_id", "shape");
          if (closedIds.has(m.task_id) || states.get(m.task_id) === "closed") { skipped.push({ ref, id: m.task_id, reason: "note_closed_task" }); continue; }
          const text = `${cleanCell(m.text, "note_text", 300, { executable: true, stats })}（出典: ${sourceLabel(item)}）`;
          planned.push({ ref, kind, args: ["task", "note", m.task_id, "--text", text, "--by", by] });
          continue;
        }
        const id = taskId(item, index);
        const built = taskArgs(m, item, index, ctx);
        index += 1;
        if (existingIds.has(id)) { skipped.push({ ref, id, reason: "already_created" }); continue; }
        if (titles.has(normalizeTitle(built.title))) { skipped.push({ ref, id, reason: "same_active_title" }); continue; }
        titles.add(normalizeTitle(built.title));
        planned.push({ ref, kind, id, args: built.args, followUp: built.followUp, policy: built.policy });
      }
      actions.push(...planned);
      for (const t of titles) activeTitles.add(t);
      // その ref が全部通ってから、変えた状態を確定する（隔離された ref の閉じた印を残さない）。
      for (const [id, s] of states) { if (s === "closed") closedIds.add(id); else ownState.set(id, s); }
    } catch (error) {
      if (!(error instanceof CellError)) throw error;
      if (error.check === "shape") {
        retry.push({ ref, id: item.id, reason: error.message });
        stopAt = i;
        break;
      }
      quarantined.push({ ref, id: item.id, reason: error.message });
    }
  }
  return {
    actions, quarantined, skipped, retry,
    ackRef: stopAt > 0 ? order[stopAt - 1] : null,
    redactions: stats.redactions, failedRefs: [...failed],
  };
}
