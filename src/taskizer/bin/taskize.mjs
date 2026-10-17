#!/usr/bin/env node
// 定時の入口。00_inbox の新着 → モデル判定 → sb task new。
import { now } from "../src/config.mjs";
import { runModel } from "../src/model.mjs";
import { runOnce } from "../src/taskize.mjs";

const result = runOnce({ now: now(), runModel });
console.log(JSON.stringify(result));
if (result.status !== "ok") process.exitCode = 1;
