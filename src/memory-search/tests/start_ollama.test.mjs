import assert from "node:assert/strict";
import test from "node:test";
import {
  parseExactUserOllamaServePids,
  startManagedOllama,
} from "../start_ollama.mjs";

test("managed起動は既存の正常なOllama 1本を再利用してspawnしない", async () => {
  let spawnCount = 0;
  const result = await startManagedOllama({
    readPids: () => [101],
    modelAvailable: async () => true,
    spawnImpl: () => {
      spawnCount += 1;
      throw new Error("must not spawn");
    },
  });
  assert.equal(result.pid, 101);
  assert.equal(result.alreadyRunning, true);
  assert.equal(spawnCount, 0);
});

test("managed起動は複数serverと必要model欠落をfail-closedにする", async () => {
  await assert.rejects(
    startManagedOllama({ readPids: () => [101, 102] }),
    /ollama_server_count_invalid:2/u,
  );
  await assert.rejects(
    startManagedOllama({
      readPids: () => [101],
      modelAvailable: async () => false,
    }),
    /ollama_existing_server_model_missing:hf\.co\/Abiray\/Nemotron-3-Embed-8B-GGUF:Q8_0/u,
  );
});

test("managed起動のprocess照合は本人所有の完全一致serveだけ", () => {
  const output = [
    "  101 501 /opt/homebrew/bin/ollama serve",
    "  102 501 /bin/zsh -lc /opt/homebrew/bin/ollama serve",
    "  103   0 /opt/homebrew/bin/ollama serve",
  ].join("\n");
  assert.deepEqual(parseExactUserOllamaServePids(output, 501), [101]);
});
