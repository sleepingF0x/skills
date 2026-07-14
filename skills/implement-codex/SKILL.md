---
name: implement-codex
description: "Implement a spec, tickets, or tracker issues — Codex (gpt-5.6-sol) writes the code, you specify and verify. Handles a queue of issues sequentially."
disable-model-invocation: true
---

Implement the work described by the user — a spec, or one or more tracker issues. Division of labor: Codex writes the code; you specify, verify, and review. Only implement in the main thread when the change is trivial (single file, obvious diff).

## 0. Resolve the work

- Spec or ticket text given directly → use it as-is.
- Issue refs (`#N`, URL) → pull the full issue **and its comments** (`gh issue view N --comments`, or the conventions in `docs/agents/issue-tracker.md` if present). The issue body plus any agent brief is the spec; later comments may amend or reject earlier attempts — read them all.
- Multiple refs, or "all ready-for-agent issues" → Batch mode (bottom of this skill).

## 1. Pin the spec

Resolve ambiguities with the user now — reasoning effort buys inference over gaps in the spec, so every gap you close here lowers the tier you pay for below. For an issue without a written agent brief, the briefing is your job in this step, not Codex's job at `xhigh`.

Use /tdd where possible, at pre-agreed seams: write the failing tests yourself before delegating. A red test is the tightest spec you can hand Codex.

Done when: the behavior is pinned by red tests and/or an unambiguous brief.

## 2. Pick the effort tier

Default is `xhigh`. Downgrade only when the remaining uncertainty is genuinely low, and state which tier you picked and why:

| Tier     | When                                                                      |
| -------- | ------------------------------------------------------------------------- |
| `xhigh`  | Default for all implementation work                                       |
| `high`   | Good brief, change follows existing patterns, no architectural surprises  |
| `medium` | Behavior fully pinned by red tests; localized, mechanical change          |

- Never `minimal`/`low` for implementation — rework costs more than the effort saved.
- Always pass the effort override (`-c model_reasoning_effort='"<tier>"'`) explicitly — never rely on the local codex config default, which is not `xhigh` and can change under you. An omitted override runs the task at whatever the config says, silently, with no error.

## 3. Delegate

Run Codex **directly via `codex exec`** — not through the codex plugin subagent. The plugin sandbox (`workspace-write`) has no network and cannot reach the Docker socket, so in repos whose tests run in containers Codex implements blind — it cannot run tests or typecheck on its own work, and every red-green iteration bounces back to you.

Write the brief to a scratchpad file, then launch in the background (Bash `run_in_background: true` — implementation runs exceed foreground command timeouts):

    codex exec --sandbox danger-full-access \
      --model gpt-5.6-sol -c model_reasoning_effort='"<tier>"' \
      --output-last-message <scratchpad>/issueN-report.md \
      - < <scratchpad>/issueN-brief.md

The brief must contain: the spec (inline the issue content — do not assume Codex will read the tracker), the red tests and how to run them (the exact container/test commands), repo conventions to follow, and the instruction to run typechecking and the affected test files before finishing.

`danger-full-access` runs **unsandboxed** — it exists so Codex can run the container test suite while implementing. The brief must therefore state the confinement explicitly: edit only within the repo (plus its own scratch under `/tmp`), no commits, no pushes, no issue-tracker writes — the working-tree diff is its only output; you commit after review.

Done when: Codex reports completion.

## 4. Verify — yourself

Codex's own report is not verification. Run typechecking and the full test suite yourself; drive the affected flow if it has a runtime surface.

If verification fails: escalate, don't restart — resume the same Codex session (`codex exec resume <session-id>`, the id is printed in the run header) one tier higher, with the failure output in the prompt. From `xhigh` the next step is `max` — pass `-c model_reasoning_effort='"max"'` explicitly. Never escalate by dropping the override: that falls back to the config default, which is lower than `xhigh`, so the retry runs weaker than the run it is meant to rescue.

## 5. Review and commit

Use /code-review to review the work — a second model reviewing gpt-5.6-sol's diff is the point of the split; never skip it.

Commit to the current branch. For an issue, reference it (`#N`) in the commit message — `/land-issue` finds the work by that reference.

End the message with a trailer naming who wrote the code, and at what tier the accepted diff was produced (the tier you escalated *to*, if you escalated):

    Implemented-by: codex gpt-5.6-sol (xhigh)

For the trivial changes you took in the main thread yourself, that is `Implemented-by: claude`. This is not bookkeeping: acceptance runs in a **fresh session** with no memory of this one, and `/accept-issue` picks its judge on exactly this fact — a judge must never be the model that wrote the code (step 2.5 there). With no trailer, acceptance cannot route and has to stop and ask.

Stop here for issues: acceptance and landing belong to `/accept-issue #N` in a **fresh session**. Do not push or close the issue from this session.

## Batch mode

For a queue of issues, process **sequentially** — the working tree is shared, so never run two Codex write jobs at once:

1. List the queue (`ready-for-agent` first, else ask the user to pick). Confirm scope and order with the user before starting.
2. Per issue: run steps 0–5 — one fresh Codex thread per issue, its own effort tier, commits referencing `#N`.
3. An issue that still fails verification after one escalation: comment the findings on the issue, leave it open, skip it, continue the queue.
4. End with a queue report: implemented / skipped / failed, one line each, and remind the user each implemented issue awaits `/accept-issue #N` in a fresh session.
