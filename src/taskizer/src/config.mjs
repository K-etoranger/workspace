// 置き場と外部コマンドはここだけで決める（環境変数で差し替え、既定は切り替え後の本番の置き場）。
import os from "node:os";
import path from "node:path";

const HOME = os.homedir();
export const WORKSPACE = process.env.SB_WORKSPACE || path.join(HOME, "Workspace");
export const SB_BIN = process.env.SB_BIN || path.join(WORKSPACE, "sb", "bin", "sb");
export const STATE_DIR = process.env.TASKIZER_STATE_DIR
  || path.join(process.env.SB_DATA || path.join(WORKSPACE, "data"), "taskizer", "state");
export const STATE_PATH = path.join(STATE_DIR, "taskizer_state.json");
export const MODEL_USAGE_PATH = path.join(STATE_DIR, "taskizer_model_usage.jsonl");
// モデル判定は Claude CLI。
export const CLAUDE_BIN = process.env.SECONDBRAIN_CLAUDE_BIN || path.join(HOME, ".local", "bin", "claude");
// タスクの決まり（この repo の skill。エージェントにも配置される）。モデルへの指示に差し込む。
export const TASK_SKILL = process.env.TASKIZER_TASK_SKILL || new URL("../skills/manage-taro-tasks/SKILL.md", import.meta.url).pathname;
export const READER = "taskizer";
export const BY = "taskizer/task-checks";
// タスク化する 00_inbox/messages のソースと、1回のモデル呼び出しに渡す件数の上限。
// メールは1通が長いので小さく。
export const SOURCES = { mail: 8, talk: 30, sns_dm: 30, forum: 30 };
export const CHUNK_CHAR_BUDGET = 50_000;
export const MAX_CHUNKS_PER_SOURCE = 20;

export function now() {
  return process.env.SB_NOW ? new Date(process.env.SB_NOW) : new Date();
}
