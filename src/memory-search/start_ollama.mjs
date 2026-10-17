#!/usr/bin/env node
import os from "node:os";
import path from "node:path";
import { execFileSync, spawn } from "node:child_process";
import { pathToFileURL } from "node:url";

// 索引作りの埋め込みに使う Ollama を、Workspace/models/ollama-fallback のモデルで起動する。
const workspace = process.env.WORKSPACE || path.join(os.homedir(), "Workspace");
export const DEFAULT_MODEL_ROOT = path.join(workspace, "models", "ollama-fallback");
export const REQUIRED_MODEL = "hf.co/Abiray/Nemotron-3-Embed-8B-GGUF:Q8_0";

export function parseExactUserOllamaServePids(psOutput, uid = os.userInfo().uid) {
  return String(psOutput || "")
    .split(/\r?\n/u)
    .map((line) => line.match(/^\s*(\d+)\s+(\d+)\s+(.+)$/u))
    .filter(Boolean)
    .filter((match) => Number(match[2]) === Number(uid))
    .filter((match) => match[3].trim() === "/opt/homebrew/bin/ollama serve")
    .map((match) => Number(match[1]));
}

function currentOllamaServePids() {
  const output = execFileSync("/bin/ps", ["-axo", "pid=,uid=,command="], {
    encoding: "utf8",
  });
  return parseExactUserOllamaServePids(output);
}

async function exactModelAvailable(fetchImpl = globalThis.fetch) {
  const response = await fetchImpl("http://127.0.0.1:11434/api/tags", {
    signal: AbortSignal.timeout(5000),
  });
  if (!response.ok) return false;
  const payload = await response.json();
  return Array.isArray(payload?.models)
    && payload.models.some((model) => model?.name === REQUIRED_MODEL);
}

export async function startManagedOllama({
  readPids = currentOllamaServePids,
  modelAvailable = exactModelAvailable,
  spawnImpl = spawn,
} = {}) {
  const modelRoot = process.env.OLLAMA_MODEL_ROOT || DEFAULT_MODEL_ROOT;
  const existingPids = readPids();
  if (existingPids.length > 1) {
    throw new Error(`ollama_server_count_invalid:${existingPids.length}`);
  }
  if (existingPids.length === 1) {
    if (!await modelAvailable()) {
      throw new Error(`ollama_existing_server_model_missing:${REQUIRED_MODEL}`);
    }
    return {
      pid: existingPids[0],
      modelRoot: "existing_server",
      alreadyRunning: true,
    };
  }
  const child = spawnImpl("/opt/homebrew/bin/ollama", ["serve"], {
    detached: true,
    stdio: "ignore",
    env: {
      ...process.env,
      OLLAMA_HOST: "127.0.0.1:11434",
      OLLAMA_MODELS: modelRoot,
    },
  });
  child.unref();
  return { pid: child.pid, modelRoot, alreadyRunning: false };
}

const direct = process.argv[1]
  && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href;
if (direct) {
  try {
    const result = await startManagedOllama();
    console.log(JSON.stringify({ ok: true, ...result }));
  } catch (error) {
    console.error(JSON.stringify({ ok: false, error: error.message }));
    process.exitCode = 1;
  }
}
