#!/usr/bin/env node
/**
 * Cross-platform launcher for the repo's Python virtual environment.
 *
 * npm scripts cannot portably reference `.venv/Scripts/python.exe` (Windows)
 * and `.venv/bin/python` (macOS/Linux) at the same time, so this thin wrapper
 * resolves the right interpreter and forwards every argument to it.
 *
 *   node scripts/py.mjs -m pytest
 *   node scripts/py.mjs --cwd apps/api -m uvicorn app.main:app --reload
 *
 * `--cwd <dir>` (optional, must come first) runs Python from that directory.
 * Falls back to the system `python` if no virtualenv has been created yet.
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const argv = process.argv.slice(2);
let cwd = repoRoot;
if (argv[0] === "--cwd") {
  cwd = resolve(repoRoot, argv[1] ?? ".");
  argv.splice(0, 2);
}

const venvPython =
  process.platform === "win32"
    ? join(repoRoot, ".venv", "Scripts", "python.exe")
    : join(repoRoot, ".venv", "bin", "python");

const python = existsSync(venvPython) ? venvPython : "python";

if (python === "python") {
  console.warn(
    "[py.mjs] No .venv found — falling back to the system Python.\n" +
      "[py.mjs] Create one with:  python -m venv .venv  &&  npm run setup:py\n",
  );
}

const child = spawn(python, argv, {
  cwd,
  stdio: "inherit",
  // Ensure local packages/services resolve without an install step in CI.
  env: { ...process.env, PYTHONPATH: [repoRoot, process.env.PYTHONPATH].filter(Boolean).join(process.platform === "win32" ? ";" : ":") },
});

child.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  else process.exit(code ?? 0);
});
