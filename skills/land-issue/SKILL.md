---
name: land-issue
description: "Land a completed issue: push the current branch, comment a summary on the issue, and close it. Use after the implementation session has committed and the work has been accepted — it does not care which skill or model did the implementing."
disable-model-invocation: true
---

# Land Issue

Finish an implemented issue: push, report back on the ticket, close it.

The issue tracker conventions should have been provided to you — see `docs/agents/issue-tracker.md`; run `/setup-matt-pocock-skills` if it's missing. All tracker operations below (comment, close) follow that file, so this skill works with GitHub, GitLab, or local-markdown trackers alike.

## Process

### 1. Identify the issue

Use the argument (`#N`, URL, or path). If none was given, infer it from issue references in the unpushed commit messages. If more than one candidate, ask the user which to land.

### 2. Preflight — refuse to land half-done work

- Working tree must be clean. Uncommitted changes → stop and report; don't commit or stash on the user's behalf.
- At least one unpushed commit must reference the issue. None → nothing to land; say so.
- If the repo has a verification entrypoint (a `verify`/`check` script under `scripts/`, or a test suite named in `AGENTS.md`/`CLAUDE.md`), run it once. Failure → stop and report; don't push.

### 3. Push

Push the current branch to its remote, setting upstream if needed.

### 4. Report on the issue

Comment on the issue following the tracker conventions: one short paragraph of what shipped, the commit SHAs, and how it was verified. Write it for the person doing acceptance, not as a changelog dump.

### 5. Close

Close the issue via the tracker's convention, ticking acceptance-criteria checkboxes if supported.

Do **not** close any parent PRD issue. If this was the parent's last open child, mention that to the user so they can close the parent after their own acceptance pass.
