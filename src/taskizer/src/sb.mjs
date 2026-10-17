// sb はコマンドとしてだけ使う（中のファイル・関数は使わない）。
import { spawnSync } from "node:child_process";
import { SB_BIN } from "./config.mjs";

export function sb(args, { input } = {}) {
  const result = spawnSync(SB_BIN, [...args, "--json"], {
    encoding: "utf8", input, maxBuffer: 64 * 1024 * 1024, timeout: 120_000,
  });
  let payload = {};
  try {
    payload = JSON.parse(String(result.stdout || "").trim().split("\n").at(-1) || "{}");
  } catch {
    payload = { ok: false, code: 5, error: `sb の出力が JSON でない: ${String(result.stderr || result.stdout).slice(-300)}` };
  }
  const code = result.status ?? 5;
  return { ...payload, ok: code === 0 && payload.ok !== false, code: code || payload.code || 0 };
}

// 読むだけのコマンド。失敗は例外にする（空と取り違えない）。
export function sbRead(args) {
  const out = sb(args);
  if (!out.ok) throw new Error(`sb ${args.slice(0, 2).join(" ")} failed (${out.code}): ${out.error || ""}`);
  return out;
}
