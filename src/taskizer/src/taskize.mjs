// 1回の定時実行: ソースごとに 00_inbox の新着を読み、モデルの提案を検査して sb task new し、読み取り位置を進める。
import fs from "node:fs";
import path from "node:path";
import { BY, CHUNK_CHAR_BUDGET, MAX_CHUNKS_PER_SOURCE, READER, SOURCES, STATE_PATH } from "./config.mjs";
import { planProposal } from "./apply.mjs";
import { buildContext, ownTaskOrigins } from "./context.mjs";
import { promptFor } from "./prompt.mjs";
import { sb, sbRead } from "./sb.mjs";

export function chunkItems(items, maxCount, budget = CHUNK_CHAR_BUDGET) {
  const chunk = [];
  let chars = 0;
  for (const item of items) {
    const size = JSON.stringify(item).length;
    if (chunk.length && (chunk.length >= maxCount || chars + size > budget)) break;
    chunk.push(item);
    chars += size;
  }
  return chunk;
}

function readState() {
  try { return JSON.parse(fs.readFileSync(STATE_PATH, "utf8")); } catch { return {}; }
}

function writeState(state) {
  fs.mkdirSync(path.dirname(STATE_PATH), { recursive: true });
  const tmp = `${STATE_PATH}.${process.pid}.tmp`;
  fs.writeFileSync(tmp, `${JSON.stringify(state, null, 2)}\n`, { mode: 0o600 });
  fs.renameSync(tmp, STATE_PATH);
}

function runChunk({ source, chunk, now, runModel }) {
  const tasks = sbRead(["task", "list", "--all"]).tasks || [];
  const projects = (sbRead(["project", "list"]).projects || []).filter((p) => p.where === "active").map((p) => p.name);
  const refs = new Map(chunk.map((item, i) => [`r${i + 1}`, item]));
  const origins = ownTaskOrigins(tasks, { by: BY });
  const context = buildContext({ source, items: chunk, refs, tasks, projects, now, origins });
  const { proposal, exitCode } = runModel(promptFor({ source, now, context }));
  if (!proposal || !Object.keys(proposal).length) return { error: `model_exit_${exitCode}` };
  let plan;
  try {
    plan = planProposal(proposal, refs, { tasks, projects, now, by: BY, origins });
  } catch (error) {
    return { error: `invalid_proposal:${error.message}` };
  }
  const created = [];
  const notes = [];
  const updated = new Set();
  const closed = [];
  const skipped = [...plan.skipped];
  const quarantined = [...plan.quarantined];
  for (const action of plan.actions) {
    const out = sb(action.args);
    const own = action.kind === "update" || action.kind === "close";
    // 直す・閉じる相手が、この回の途中で消えていた（3 = 無い）。見送って先へ進む。archive・秘密で断った 4 は下で隔離に記録する。
    if (!out.ok && own && out.code === 3) { skipped.push({ ref: action.ref, id: action.id, reason: "sb_3" }); continue; }
    if (!out.ok) {
      // 4 = 秘密・会社機密などで sb が断った。その件だけ隔離して先へ進む。それ以外（ロック・内部の誤り）は止める。
      if (out.code === 4) { quarantined.push({ ref: action.ref, id: refs.get(action.ref).id, reason: `sb_refused:${out.error || ""}`.slice(0, 200) }); continue; }
      return { error: `sb_${out.code}:${out.error || ""}`.slice(0, 300), created, notes, updated: [...updated], closed, quarantined };
    }
    for (const follow of action.followUp || []) {
      const res = sb(follow);
      if (!res.ok) return { error: `sb_${res.code}:${res.error || ""}`.slice(0, 300), created, notes, updated: [...updated], closed, quarantined };
    }
    if (action.kind === "note") notes.push(action.args[2]);
    else if (action.kind === "update") updated.add(action.id);
    else if (action.kind === "close") closed.push(action.id);
    else created.push({ id: out.id || action.id, policy: action.policy });
  }
  if (plan.ackRef) {
    const ack = sb(["inbox", "ack", "--reader", READER, "--source", source, "--until", refs.get(plan.ackRef).id]);
    if (!ack.ok) return { error: `ack_${ack.code}:${ack.error || ""}`.slice(0, 300), created, notes, updated: [...updated], closed, quarantined };
  }
  const acked = plan.ackRef ? Number(plan.ackRef.slice(1)) : 0;
  return {
    created, notes, updated: [...updated], closed, quarantined, skipped, redactions: plan.redactions, acked,
    stalled: acked < chunk.length ? { failed_refs: plan.failedRefs, retry: plan.retry } : null,
  };
}

export function runOnce({ now = new Date(), runModel, sources = SOURCES } = {}) {
  const previous = readState();
  const result = { at: now.toISOString(), status: "ok", sources: {} };
  const quarantineLog = Array.isArray(previous.quarantined) ? previous.quarantined : [];
  for (const [source, maxCount] of Object.entries(sources)) {
    const summary = { reviewed: 0, created: [], notes: [], updated: [], closed: [], skipped: 0, quarantined: 0, redactions: 0, error: "" };
    result.sources[source] = summary;
    for (let n = 0; n < MAX_CHUNKS_PER_SOURCE; n += 1) {
      let items;
      try {
        items = sbRead(["inbox", "list", "--source", source, "--since", READER]).items || [];
      } catch (error) {
        summary.error = String(error.message).slice(0, 300);
        break;
      }
      if (!items.length) break;
      const chunk = chunkItems(items, maxCount);
      const out = runChunk({ source, chunk, now, runModel });
      summary.created.push(...(out.created || []));
      summary.notes.push(...(out.notes || []));
      summary.updated.push(...(out.updated || []));
      summary.closed.push(...(out.closed || []));
      summary.skipped += (out.skipped || []).length;
      summary.redactions += out.redactions || 0;
      summary.reviewed += out.acked || 0;
      for (const q of out.quarantined || []) {
        summary.quarantined += 1;
        quarantineLog.push({ at: result.at, source, id: q.id, reason: q.reason });
      }
      if (out.error) { summary.error = out.error; break; }
      if (out.stalled) { summary.error = `stalled:${JSON.stringify(out.stalled)}`.slice(0, 300); break; }
    }
    if (summary.error || summary.quarantined) result.status = "warn";
  }
  writeState({ ...result, quarantined: quarantineLog.slice(-200) });
  const lines = Object.entries(result.sources).map(([s, v]) =>
    `- ${s}: 確認 ${v.reviewed}件 / タスク ${v.created.length}件 / 経緯 ${v.notes.length}件 / 更新 ${v.updated.length}件 / 完了・取消 ${v.closed.length}件 / 重複で見送り ${v.skipped}件 / 隔離 ${v.quarantined}件${v.error ? ` / 未完了: ${v.error.split(":")[0]}` : ""}`);
  sb(["log", "schedule", "--task", "taskizer", "--text", `${result.status}\n${lines.join("\n")}`, "--by", BY]);
  return result;
}
