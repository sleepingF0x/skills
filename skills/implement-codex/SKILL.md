---
name: implement-codex
description: "Implement a spec or tickets — Codex (gpt-5.6-sol) does the whole job: writes the failing tests, writes the code, runs the suite. You brief it, then review the result."
disable-model-invocation: true
---

Implement the work described by the user in the spec or tickets, by delegating the whole job to Codex. For a tracker issue, first pull the full issue **and its comments** (`gh issue view N --comments`, or the conventions in `docs/agents/issue-tracker.md` if present) — the body plus any later comments is the spec.

Write the brief to a scratchpad file: the spec inline (Codex won't read the tracker for you), the exact typecheck and test commands (including any container invocation), the repo conventions to follow, and the instruction to use /tdd where possible — write the failing tests first — at pre-agreed seams, then run typechecking and single test files regularly and the full suite once at the end. Confine Codex in the brief: edit only inside the repo (plus `/tmp` scratch), no commits, no pushes, no tracker writes — the working-tree diff is its only output.

Run Codex directly via `codex exec` — not the plugin subagent, whose sandbox has no network and can't reach the Docker socket, so container suites dead-end there. Launch in the background; implementation runs exceed foreground timeouts:

    codex exec --sandbox danger-full-access \
      --model gpt-5.6-sol -c model_reasoning_effort='"xhigh"' \
      --output-last-message <scratchpad>/report.md \
      - < <scratchpad>/brief.md

Always pass the effort override explicitly — the local codex config default is not `xhigh` and can change under you. `danger-full-access` runs unsandboxed (that is how Codex reaches Docker to run the suite); the confinement you wrote into the brief is what keeps it in bounds, and `git status` after the run is your check that it held.

If Codex finishes with tests still failing, resume the same session (`codex exec resume <session-id>`, the id is in the run header) with the failure output — don't restart.

Once Codex reports done, use /code-review to review the work — a second model reviewing Codex's diff is the whole point of the split; never skip it. Then commit to the current branch.

For a tracker issue, reference it (`#N`) in the commit message and end with the trailer that `/accept-issue` routes on:

    Implemented-by: codex gpt-5.6-sol

Then stop. Pushing, accepting, and closing belong to `/accept-issue #N` in a fresh session — do not push or close the issue here.
