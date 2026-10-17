// Claude CLI を読み取り専用の提案器として呼ぶ。
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { CLAUDE_BIN, MODEL_USAGE_PATH } from "./config.mjs";

const SCHEMA_PATH = path.join(path.dirname(fileURLToPath(import.meta.url)), "proposal.schema.json");

function absolute(value, label) {
  const text = String(value || "");
  if (!path.isAbsolute(text) || path.resolve(text) !== text) throw new Error(`invalid_${label}`);
  return fs.realpathSync.native(text);
}

function seatbeltString(value) {
  return String(value).replace(/\\/gu, "\\\\").replace(/"/gu, '\\"');
}

// Claude CLI は ~/.claude と ~/.claude.json* に状態を書き、OAuth を Keychain から読むため /usr/bin/security の
// 実行を許す（CLI は /bin/sh 経由で呼ぶので sh・bash も許す）。それ以外の書込みと子プロセスの起動は拒否する。
export function claudeTaskizerSandboxProfile({ claudeRealPath, home, temporaryRoots = ["/private/tmp", "/tmp", "/private/var/folders"] } = {}) {
  const executable = absolute(claudeRealPath, "claude_real_path");
  const homeDir = absolute(home, "home");
  const claudeDir = path.join(homeDir, ".claude");
  const escapedHome = homeDir.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
  const writable = temporaryRoots.map((root) => absolute(root, "temporary_root"));
  return [
    "(version 1)",
    "(allow default)",
    `(deny file-write* (require-all (require-not (subpath "${seatbeltString(claudeDir)}")) (require-not (regex #"^${seatbeltString(escapedHome)}/\\.claude\\.json")) ${writable.map((root) => `(require-not (subpath "${seatbeltString(root)}"))`).join(" ")} (require-not (literal "/dev/null"))))`,
    "(deny process-exec*)",
    `(allow process-exec (literal "${seatbeltString(executable)}") (literal "/usr/bin/security") (literal "/bin/sh") (literal "/bin/bash"))`,
  ].join("\n");
}

export function structuredOutputFromClaudeJson(stdout) {
  try {
    const result = JSON.parse(String(stdout || ""));
    if (result?.is_error) return {};
    const payload = result?.structured_output;
    return payload && typeof payload === "object" && !Array.isArray(payload) ? payload : {};
  } catch {
    return {};
  }
}

// Claude CLI の usage を記録欄へ写す。input_tokens は cache 分を含む総量。
export function claudeUsageFromJson(text) {
  const empty = { input_tokens: null, cached_input_tokens: null, output_tokens: null, reasoning_output_tokens: null, reported_turns: 0, usage_available: false };
  let result;
  try { result = JSON.parse(String(text || "")); } catch { return empty; }
  const usage = result?.usage;
  if (!usage || !Number.isSafeInteger(usage.input_tokens)) return empty;
  const n = (value) => (Number.isSafeInteger(value) && value >= 0 ? value : 0);
  return {
    input_tokens: n(usage.input_tokens) + n(usage.cache_creation_input_tokens) + n(usage.cache_read_input_tokens),
    cached_input_tokens: n(usage.cache_read_input_tokens),
    output_tokens: n(usage.output_tokens),
    reasoning_output_tokens: n(usage.output_tokens_details?.thinking_tokens),
    reported_turns: n(result.num_turns),
    usage_available: true,
  };
}

// 数値だけを残す（モデルの文章・本文は残さない）。
function appendUsage(record) {
  fs.mkdirSync(path.dirname(MODEL_USAGE_PATH), { recursive: true });
  fs.appendFileSync(MODEL_USAGE_PATH, `${JSON.stringify(record)}\n`, { mode: 0o600 });
}

function childEnv() {
  const user = os.userInfo().username;
  return { HOME: os.homedir(), PATH: "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin", LANG: "en_US.UTF-8", LC_ALL: "en_US.UTF-8", TMPDIR: process.env.TMPDIR || "/tmp", USER: user, LOGNAME: user };
}

// 返り値: { proposal, exitCode }。proposal が {} なら使えない。
export function runModel(prompt) {
  const claudeReal = fs.realpathSync(CLAUDE_BIN);
  // Claude CLI の検証器は draft 2020-12 の $schema 宣言を解決できないため、宣言だけ外して渡す。
  const { $schema, ...schema } = JSON.parse(fs.readFileSync(SCHEMA_PATH, "utf8"));
  // 読取りの道具だけを渡し、本人の設定・hook・MCP は読まない。書込み・子プロセスは Seatbelt で拒否する。
  const result = spawnSync("/usr/bin/sandbox-exec", [
    "-p", claudeTaskizerSandboxProfile({ claudeRealPath: claudeReal, home: os.homedir() }),
    claudeReal, "-p", "--output-format", "json", "--json-schema", JSON.stringify(schema),
    "--tools", "Read", "--setting-sources", "", "--strict-mcp-config", "--no-session-persistence",
    "--permission-mode", "dontAsk", "--effort", "high",
  ], { cwd: os.tmpdir(), input: prompt, encoding: "utf8", maxBuffer: 16 * 1024 * 1024, timeout: 900_000, env: childEnv() });
  appendUsage({ at: new Date().toISOString(), prompt_characters: prompt.length, exit_code: result.status, ...claudeUsageFromJson(result.stdout) });
  return { proposal: result.status === 0 ? structuredOutputFromClaudeJson(result.stdout) : {}, exitCode: result.status };
}
