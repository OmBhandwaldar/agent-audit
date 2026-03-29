#!/usr/bin/env node
/**
 * session-end.js
 * Fires on Stop hook (when Claude Code session ends).
 * Creates a structured .tmp session file with a template Claude fills in.
 * If a file for today already exists, updates the Last Updated timestamp only.
 *
 * File naming: YYYY-MM-DD-[shortid]-session.tmp
 * Storage: .claude/sessions/ (project-local)
 */

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const SESSIONS_DIR = path.join(process.cwd(), ".claude", "sessions");

function getDateString() {
  return new Date().toISOString().split("T")[0]; // YYYY-MM-DD
}

function getTimeString() {
  return new Date().toTimeString().slice(0, 5); // HH:MM
}

function generateShortId() {
  return crypto.randomBytes(4).toString("hex"); // 8 char lowercase hex
}

function getTodaysFile() {
  if (!fs.existsSync(SESSIONS_DIR)) return null;

  const today = getDateString();
  const files = fs
    .readdirSync(SESSIONS_DIR)
    .filter((f) => f.startsWith(today) && f.endsWith("-session.tmp"));

  return files.length > 0
    ? { name: files[0], fullPath: path.join(SESSIONS_DIR, files[0]) }
    : null;
}

function createSessionTemplate(date, time, shortId) {
  return `# Session ${date}-${shortId}

**Date:** ${date}
**Started:** ${time}
**Last Updated:** ${time}

## What I worked on
<!-- Claude: summarize what was built or changed this session -->

## Current status of each component
- Smart contract:
- IPFS uploader:
- LangChain agent:
- audit_flow.py:
- FastAPI:
- Frontend:

### Completed
<!-- Claude: list completed tasks as - [x] items -->

### In Progress
<!-- Claude: list in-progress tasks as - [ ] items -->

## Blockers
<!-- None / describe any blockers -->

## Notes for Next Session
<!-- Claude: what should the next session start with -->

### Context to Load
\`\`\`
<!-- Claude: list the key files being worked on -->
\`\`\`
`;
}

function updateTimestamp(content, time) {
  return content.replace(/\*\*Last Updated:\*\* .+/, `**Last Updated:** ${time}`);
}

function main() {
  // Ensure sessions directory exists
  if (!fs.existsSync(SESSIONS_DIR)) {
    fs.mkdirSync(SESSIONS_DIR, { recursive: true });
  }

  const date = getDateString();
  const time = getTimeString();
  const existing = getTodaysFile();

  if (existing) {
    // File for today exists — just update the timestamp
    const content = fs.readFileSync(existing.fullPath, "utf8");
    const updated = updateTimestamp(content, time);
    fs.writeFileSync(existing.fullPath, updated, "utf8");
    process.stderr.write(
      `[SessionEnd] Updated timestamp in: ${existing.name}\n`
    );
  } else {
    // New session for today — create fresh file
    const shortId = generateShortId();
    const filename = `${date}-${shortId}-session.tmp`;
    const fullPath = path.join(SESSIONS_DIR, filename);
    const template = createSessionTemplate(date, time, shortId);
    fs.writeFileSync(fullPath, template, "utf8");
    process.stderr.write(`[SessionEnd] Created session file: ${filename}\n`);
    process.stderr.write(
      `[SessionEnd] Tell Claude: "update the session file ${filename}"\n`
    );
  }
}

main();
