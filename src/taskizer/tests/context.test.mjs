// モデルに渡す材料（TRUSTED 側）の試験。論理日は偽 sb 経由で本物の sb day に尋ねる。
import assert from "node:assert/strict";
import test from "node:test";
import { fakeSb } from "./helpers.mjs";

const D = "2026-09-29";
const env = fakeSb({
  "show.json": {
    [`claude:${D}`]: [
      { id: "c1", 時刻: "23:00", 会話ID: "a", 本人: "SNSにログインしたのはXXX", 返答: "REPLY_SECRET" },
      { id: "c2", 時刻: "23:30", 会話ID: "a", 本人: "<scheduled-task name=\"x\">SCHEDULED_BODY", 返答: "" },
      { id: "c3", 時刻: "23:40", 会話ID: "a", 本人: "<task-notification><summary>NOTIFY_BODY</summary>", 返答: "" },
      { id: "c4", 時刻: "23:41", 会話ID: "a", 本人: "This session is being continued from a previous conversation. SUMMARY_BODY", 返答: "" },
      { id: "c5", 時刻: "23:42", 会話ID: "a", 本人: "[Request interrupted by user] INTERRUPT_BODY", 返答: "" },
      { id: "c6", 時刻: "23:43", 会話ID: "a", 本人: "<local-command-caveat>CAVEAT_BODY</local-command-caveat>", 返答: "" },
    ],
    [`codex:${D}`]: [{ id: "x1", 時刻: "01:00", 会話ID: "b", 本人: "日付をまたいだ後の発言", 返答: "" }],
    [`talk:${D}`]: [{ id: "L1", 時刻: "09:00", 相手: "佐藤", 場所: "読書会", 向き: "other", 本文: "TALK_BODY" }],
  },
  "distill.json": { "2026-09-28:talk": "昨日のトーク蒸留", "2026-09-22:claude": "7日前の蒸留", "2026-09-21:claude": "8日前の蒸留" },
  "memos.json": { 案件A: "---\n案件: 案件A\n---\n# 案件A\n\n## 目的\nPURPOSE\n\n## 今の状態\n### 進み具合\n- 進んでいる\n\n## 決まっていること\n- 決定X\n\n## 経緯\n- LOG_LINE\n" },
  "tasks.json": [], "projects.json": [{ name: "案件A", where: "active" }],
});
const { buildContext, todayStatements, recentDistills, projectNotes, newestWithin } = await import("../src/context.mjs");
const NOW = new Date("2026-09-29T10:00:00+09:00");
const build = () => buildContext({ source: "talk", items: [], refs: new Map(), tasks: [], projects: ["案件A"], now: NOW });
test.after(() => env.cleanup());

test("今日の本人の発言だけが入る（返答・定時処理の本文・作業完了通知・要約の引き継ぎ・中断の印・連絡は入らない）。05:00 前の時刻は後ろに並ぶ", () => {
  const text = build();
  assert.match(text, /SNSにログインしたのはXXX/u);
  assert.match(text, /\[23:00 \/ claude\].*\n\[01:00 \/ codex\] 日付をまたいだ後の発言/u);
  assert.doesNotMatch(text, /REPLY_SECRET|SCHEDULED_BODY|NOTIFY_BODY|TALK_BODY|SUMMARY_BODY|INTERRUPT_BODY|CAVEAT_BODY/u);
});

test("蒸留は今日の前日から7日前まで。案件メモは「今の状態」「決まっていること」の2節だけ", () => {
  const text = build();
  assert.match(text, /昨日のトーク蒸留/u);
  assert.match(text, /7日前の蒸留/u);
  assert.doesNotMatch(text, /8日前の蒸留/u);
  assert.match(text, /### 案件A\n\[今の状態\]\n###### 進み具合\n- 進んでいる\n\[決まっていること\]\n- 決定X/u);
  assert.doesNotMatch(text, /PURPOSE|LOG_LINE/u);
});

test("字数の上限は新しい物から切る。入りきらない1件は先頭だけで、切ったと分かる", () => {
  const items = ["OLD", "MID", "NEW"].map((t, i) => ({ 時刻: `1${i}:00`, 本人: t.repeat(10) }));
  const run = () => ({ ok: true, sources: { claude: { dir: "conversations", items } } });
  const full = todayStatements(D, { run, budget: 10_000 });
  assert.match(full, /OLD/u);
  const cut = todayStatements(D, { run, budget: 70 });
  assert.ok(cut.length <= 70 + 40, cut); // 先頭の省略の注記の分だけ超えてよい
  assert.match(cut, /NEW/u);
  assert.doesNotMatch(cut, /OLD|MID/u);
  assert.match(cut, /古い2件は入れていない/u);
  const head = newestWithin(["あ".repeat(100)], 60);
  assert.equal(head.picked.length, 1);
  assert.ok(head.picked[0].length <= 60);
  assert.match(head.picked[0], /^あ+…（字数の上限で以下を省いた。元は100字）$/u);
  const days = [];
  const dRun = (args) => { days.push(args.at(-1)); return { ok: true, sources: { s: { text: `${args.at(-1)}の蒸留`.padEnd(30, "。") } } }; };
  const out = recentDistills(D, { run: dRun, budget: 80 });
  assert.deepEqual(days.sort(), ["2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25", "2026-09-26", "2026-09-27", "2026-09-28"]);
  assert.match(out, /2026-09-28/u);
  assert.doesNotMatch(out, /2026-09-22/u);
});

test("読み取りの失敗は「読めなかった」と書き、空（無い）と区別する", () => {
  const bad = () => ({ ok: false, code: 5, error: "壊れた" });
  assert.match(todayStatements(D, { run: bad }), /^読めなかった/u);
  assert.match(recentDistills(D, { run: bad }), /読めなかった日がある/u);
  assert.match(projectNotes(["案件A"], { run: bad }), /### 案件A\n読めなかった/u);
  const empty = () => ({ ok: true, sources: {} });
  assert.match(todayStatements(D, { run: empty }), /記録は無い/u);
  assert.doesNotMatch(todayStatements(D, { run: empty }), /読めなかった/u);
  assert.match(recentDistills(D, { run: empty }), /蒸留は無い/u);
  // 実際の呼び出し（偽 sb）でも、失敗は空にならない
  process.env.FAKE_SB_FAIL = "distill show";
  try {
    assert.match(build(), /読めなかった日がある/u);
  } finally {
    delete process.env.FAKE_SB_FAIL;
  }
});

test("この処理が作った open のタスクは中身と経緯まで入り、同じ場所の前後の文はそのタスクの元の日まで遡る", async () => {
  const { ownTasks, ownTaskOrigins, ownTaskPlaces, threadContext } = await import("../src/context.mjs");
  const tasks = [
    { ID: "20260920-own", 件名: "送金する", 作った物: "taskizer/task-checks", 出典: "00_inbox/messages/talk/2026-09-20.md id:OLD", archived: false },
    { ID: "20260920-other", 件名: "本人のタスク", 作った物: "claude", archived: false },
  ];
  const run = (args) => ({ ok: true, text: `---\nID: ${args[2]}\n---\n# x\n\n## 内容\nBODY_${args[2]}\n\n## 経緯\n- LOG_${args[2]}\n` });
  const text = ownTasks(tasks, { run });
  assert.match(text, /BODY_20260920-own[\s\S]*LOG_20260920-own/u);
  assert.doesNotMatch(text, /20260920-other/u);
  const days = {
    "2026-09-20": [{ id: "OLD", 時刻: "10:00", 場所: "読書会", 向き: "other", 本文: "送金して" }],
    "2026-09-25": [{ id: "MID", 時刻: "10:00", 場所: "読書会", 向き: "self", 本文: "あとで送る" }],
  };
  const read = (_, date) => days[date] || [];
  const origins = ownTaskOrigins(tasks, { read });
  assert.deepEqual(origins.get("20260920-own"), { source: "talk", date: "2026-09-20", place: "読書会" });
  const since = ownTaskPlaces("talk", origins);
  assert.equal(ownTaskPlaces("mail", origins).size, 0);
  assert.equal(since.get("読書会"), "2026-09-20");
  const items = [{ id: "NEW", date: "2026-09-29", 場所: "読書会" }];
  const near = threadContext("talk", items, { read });
  assert.equal(near.length, 0);
  const far = threadContext("talk", items, { read, since });
  assert.deepEqual(far[0].直近.map((x) => x.本文), ["送金して", "あとで送る"]);
  const capped = threadContext("talk", [{ id: "NEW", date: "2026-10-08", 場所: "読書会" }], { read, since });
  assert.deepEqual(capped.map((p) => p.直近.map((x) => x.本文)), [["あとで送る"]]);
});
