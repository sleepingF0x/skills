---
name: accept-issue
description: "Acceptance pass for an implemented issue: run verification, exercise the behavior for real, judge each acceptance criterion with evidence, then hand off to /land-issue on pass or send it back with findings on fail. Must run in a fresh session — never the session that implemented the issue."
disable-model-invocation: true
---

# Accept Issue

Judge whether an implemented issue actually delivers what was asked, then either land it or send it back.

**Hard rule: the acceptance session must not be the implementation session.** The implementer carries its own rationalizations ("this is obviously what the issue meant"); a cold-start session can only re-derive the requirement from the issue text, which is the point. The acceptance criteria were authored by a different model than the implementer, so judging against them is already a cross-check — but only if the judge reads them fresh.

The default acceptor is a fresh Codex session. For high-stakes issues, escalate to the Claude session that produced the PRD: it adds a cross-model perspective and still holds the original intent context, at the cost of Claude tokens.

The issue tracker conventions should have been provided to you — see `docs/agents/issue-tracker.md`; run `/setup-matt-pocock-skills` if it's missing. All tracker operations below follow that file.

## Process

### 1. Identify the issue

Use the argument (`#N`, URL, or path). If none was given, infer it from issue references in the unpushed commit messages. If more than one candidate, ask the user which to accept.

### 2. Gather the evidence

- Read the issue body (acceptance criteria) and all comments.
- Diff the unpushed commits that reference the issue — that is the work under acceptance.
- Read the parent PRD issue for intent. If this session happens to contain the original requirements conversation (escalated acceptance in the Claude feature session), that intent outranks the issue text.

### 3. Verify mechanically

Run the repo's verification entrypoint (a `verify`/`check` script under `scripts/`, or the test suite named in `AGENTS.md`/`CLAUDE.md`). Failure → immediate reject; skip to step 6.

### 4. Exercise the behavior

Green tests are necessary, not sufficient. Actually drive the changed behavior end-to-end — run the CLI, hit the endpoint, execute the script — and observe the output. Prefer inputs the tests did *not* use.

### 5. Judge each criterion — evidence is mandatory

For every acceptance criterion, record a verdict **with the evidence attached**: the exact command you ran and the output you observed for a **pass**; expected vs actual with a concrete repro for a **fail**. A verdict without evidence is not a verdict — the human reading the report trusts the evidence, not the conclusion. Then judge one level up: does the implementation match the *intent*, not just the letter? If a criterion itself seems to misencode the intent (the issue was written wrong), do not silently pass or fail it — flag it to the user; that is a spec bug, not an implementation bug.

### 6. Verdict and handoff

**All criteria pass:**
1. Comment the acceptance report on the issue: per-criterion verdicts with their evidence, one line on how the behavior was exercised beyond the tests.
2. Invoke `/land-issue #N` to push, summarize, and close.
3. Show the user the acceptance report in the session — they spot-check the evidence, they don't re-verify.

**Any criterion fails:**
1. Comment the failures on the issue: expected vs actual, concrete repro steps, pointers into the code where useful. Write it for a cold-start implementer — the fixing session has no memory of this one.
2. Ensure the issue carries the `ready-for-agent` label and stays open. Do **not** push, do **not** close, do **not** fix it yourself — the fix belongs to a fresh `/implement #N` session, or acceptance stops being acceptance.
3. Tell the user to re-run `codex "/implement #N"`; the fix session will pick up the comment.

**Criteria are ambiguous or the spec itself is wrong:** stop and put the question to the user before any verdict. If the issue needs rewording, update it (or label `needs-info`) so the next implementation pass starts from a correct spec.

Never close the parent PRD issue — that stays with the human.
