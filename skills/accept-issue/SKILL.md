---
name: accept-issue
description: "Acceptance pass for an implemented issue: run verification, exercise the behavior for real, judge each acceptance criterion, then hand off to /land-issue on pass or send it back with findings on fail. Claude-only by design — the implementer (Codex) must not accept its own work."
disable-model-invocation: true
---

# Accept Issue

Judge whether an implemented issue actually delivers what was asked, then either land it or send it back. This skill is deliberately installed only for Claude: acceptance must be done by a different model than the one that implemented, and ideally in the same session that produced the PRD and issues, so the original intent is still in context.

The issue tracker conventions should have been provided to you — see `docs/agents/issue-tracker.md`; run `/setup-matt-pocock-skills` if it's missing. All tracker operations below follow that file.

## Process

### 1. Identify the issue

Use the argument (`#N`, URL, or path). If none was given, infer it from issue references in the unpushed commit messages. If more than one candidate, ask the user which to accept.

### 2. Gather the evidence

- Read the issue body (acceptance criteria) and all comments.
- Diff the unpushed commits that reference the issue — that is the work under acceptance.
- If this session contains the original requirements conversation (grilling, PRD), that intent outranks the issue text. If the issue is from an earlier session, also read the parent PRD issue for intent.

### 3. Verify mechanically

Run the repo's verification entrypoint (a `verify`/`check` script under `scripts/`, or the test suite named in `AGENTS.md`/`CLAUDE.md`). Failure → immediate reject; skip to step 6.

### 4. Exercise the behavior

Green tests are necessary, not sufficient. Actually drive the changed behavior end-to-end — run the CLI, hit the endpoint, execute the script — and observe the output. Prefer inputs the tests did *not* use.

### 5. Judge each criterion

For every acceptance criterion, record a verdict with evidence: **pass** (what you ran, what you saw) or **fail** (expected vs actual, with a concrete repro). Then judge one level up: does the implementation match the *intent*, not just the letter? If a criterion itself seems to misencode the intent (the issue was written wrong), do not silently pass or fail it — flag it to the user; that is a spec bug, not an implementation bug.

### 6. Verdict and handoff

**All criteria pass:**
1. Comment the acceptance report on the issue: per-criterion verdicts with evidence, one line on how the behavior was exercised beyond the tests.
2. Invoke `/land-issue #N` to push, summarize, and close.
3. Show the user the acceptance report in the session — they spot-check it, they don't re-verify.

**Any criterion fails:**
1. Comment the failures on the issue: expected vs actual, concrete repro steps, pointers into the code where useful. Write it for a cold-start implementer — the fixing Codex session has no memory of this one.
2. Ensure the issue carries the `ready-for-agent` label and stays open. Do **not** push, do **not** close, do **not** fix it yourself.
3. Tell the user to re-run `codex "/implement #N"`; the fix session will pick up the comment.

**Criteria are ambiguous or the spec itself is wrong:** stop and put the question to the user before any verdict. If the issue needs rewording, update it (or label `needs-info`) so the next implementation pass starts from a correct spec.

Never close the parent PRD issue — that stays with the human.
