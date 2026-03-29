#!/usr/bin/env node
/**
 * session-start.js
 * Fires on SessionStart hook.
 * Finds the most recent session .tmp file and outputs its content to stdout.
 * Claude Code injects stdout from SessionStart hooks into the conversation context.
 */

const fs = require("fs");
const path = require("path");

const SESSIONS_DIR = path.join(process.cwd(), ".claude", "sessions");

function getLatestSession() {
  if (!fs.existsSync(SESSIONS_DIR)) return null;

  const files = fs
    .readdirSync(SESSIONS_DIR)
    .filter((f) => f.endsWith("-session.tmp"))
    .map((f) => ({
      name: f,
      fullPath: path.join(SESSIONS_DIR, f),
      mtime: fs.statSync(path.join(SESSIONS_DIR, f)).mtime,
    }))
    .sort((a, b) => b.mtime - a.mtime); // newest first

  return files.length > 0 ? files[0] : null;
}

function main() {
  const latest = getLatestSession();

  if (!latest) {
    process.stderr.write("[SessionStart] No previous sessions found.\n");
    process.exit(0);
  }

  const content = fs.readFileSync(latest.fullPath, "utf8").trim();

  if (!content) {
    process.stderr.write(
      `[SessionStart] Found session file but it is empty: ${latest.name}\n`
    );
    process.exit(0);
  }

  process.stderr.write(`[SessionStart] Loading context from: ${latest.name}\n`);

  // This is the critical line — stdout is injected into Claude's context
  process.stdout.write(
    `\n--- PREVIOUS SESSION CONTEXT ---\n${content}\n--- END PREVIOUS SESSION CONTEXT ---\n`
  );
}

main();
