#!/usr/bin/env node
// 試験用の偽 sb。呼ばれた引数を FAKE_SB_DIR/calls.jsonl に残し、FAKE_SB_DIR の JSON から答える。
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { spawnSync } from "node:child_process";

const dir = process.env.FAKE_SB_DIR;
const args = process.argv.slice(2).filter((a) => a !== "--json");
fs.appendFileSync(path.join(dir, "calls.jsonl"), `${JSON.stringify(args)}\n`);
const read = (name, fallback) => { try { return JSON.parse(fs.readFileSync(path.join(dir, name), "utf8")); } catch { return fallback; } };
const write = (name, value) => fs.writeFileSync(path.join(dir, name), JSON.stringify(value));
const opt = (name) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : undefined; };
const out = (value, code = 0) => { console.log(JSON.stringify(value)); process.exit(code); };
const [target, action] = args;

// 論理日は本物の sb に尋ねる（試験の中で日を計算しない）。sb day は読むだけ。
if (target === "day") {
  const real = process.env.REAL_SB_BIN || path.join(os.homedir(), "Workspace", "sb", "bin", "sb");
  const r = spawnSync(real, [...args, "--json"], { encoding: "utf8" });
  process.stdout.write(r.stdout || "");
  process.stderr.write(r.stderr || "");
  process.exit(r.status ?? 5);
}

// FAKE_SB_FAIL に含まれる語を引数に持つ呼び出しは内部の誤りで失敗させる（読み取りの失敗の試験）。
if (process.env.FAKE_SB_FAIL && args.join(" ").includes(process.env.FAKE_SB_FAIL)) out({ ok: false, code: 5, error: "壊れた" }, 5);

if (target === "inbox" && action === "list") {
  const pos = read("checkpoint.json", {})[opt("--source")] || 0;
  out({ ok: true, items: read("inbox.json", []).filter((i) => i.source === opt("--source") && i.seq > pos) });
}
if (target === "inbox" && action === "ack") {
  const item = read("inbox.json", []).find((i) => i.source === opt("--source") && i.id === opt("--until"));
  if (!item) out({ ok: false, code: 3, error: "無い" }, 3);
  write("checkpoint.json", { ...read("checkpoint.json", {}), [item.source]: item.seq });
  out({ ok: true, moved: true });
}
if (target === "inbox" && action === "show" && !opt("--source")) {
  // 全ソース。本人の発言を持つ件のソースは会話（conversations）として答える。
  const sources = {};
  for (const [key, items] of Object.entries(read("show.json", {}))) {
    const [source, date] = key.split(":");
    if (date === opt("--date")) sources[source] = { dir: items.some((i) => "本人" in i) ? "conversations" : "messages", path: key, items };
  }
  out({ ok: true, date: opt("--date"), sources });
}
if (target === "inbox" && action === "show") {
  const items = read("show.json", {})[`${opt("--source")}:${opt("--date")}`];
  if (!items) out({ ok: false, code: 3, error: "無い" }, 3);
  out({ ok: true, items });
}
if (target === "distill" && action === "show") {
  const sources = {};
  for (const [key, text] of Object.entries(read("distill.json", {}))) {
    const [date, source] = key.split(":");
    if (date === opt("--date")) sources[source] = { path: key, text };
  }
  out({ ok: true, date: opt("--date"), sources });
}
if (target === "project" && action === "show") out({ ok: true, name: args[2], text: read("memos.json", {})[args[2]] || "" });
if (target === "task" && action === "list") out({ ok: true, tasks: read("tasks.json", []) });
if (target === "project" && action === "list") out({ ok: true, projects: read("projects.json", []) });
if (target === "task" && action === "new") {
  if (String(opt("--text")).includes("REFUSE")) out({ ok: false, code: 4, error: "秘密" }, 4);
  if (process.env.FAKE_SB_LOCKED) out({ ok: false, code: 2, error: "ロック" }, 2);
  const tasks = read("tasks.json", []);
  tasks.push({ ID: opt("--id"), 件名: opt("--title"), 状態: "open", 担当: opt("--owner"), 区分: opt("--type"), 期限: opt("--due") || "", archived: false });
  write("tasks.json", tasks);
  out({ ok: true, id: opt("--id") });
}
out({ ok: true });
