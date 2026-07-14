---
name: accept-issue
description: "Acceptance pass for an implemented issue: delegate the judging to Codex (gpt-5.6-sol) — it runs verification, exercises the behavior, judges each criterion with evidence — then land on pass or send back with findings on fail. Must run in a fresh session — never the session that implemented the issue."
disable-model-invocation: true
---

# Accept Issue

Judge whether an implemented issue actually delivers what was asked, then either land it or send it back.

**Hard rule: the acceptance session must not be the implementation session.** The implementer carries its own rationalizations ("this is obviously what the issue meant"); a cold-start judge can only re-derive the requirement from the issue text, which is the point.

Division of labor: **Codex (gpt-5.6-sol) is the judge by default** — it runs verification, exercises the behavior, and produces per-criterion verdicts with evidence, in its own fresh thread. **You are the clerk** — you assemble the dossier, forward it verbatim, check that the verdict carries evidence, and execute the tracker operations. You do not judge, and you do not overrule the judge. Step 2.5 is where the judge gets picked, and it turns on which model wrote the code.

Why a same-model judge is sound on the default path, where Codex wrote the code: the judge is not re-reviewing Codex's diff — `/code-review` already did that, with Claude's priors against Codex's. What the judge tests is whether the delivered behavior satisfies the **issue**, and the issue was written by Claude. So the cross-model check runs both ways across the pipeline: Claude audits Codex's code, Codex audits Claude's spec — and a judge with no stake in that spec is the only thing positioned to catch a spec that was wrong from the start. What a fresh thread cannot remove is shared priors: implementer and judge read the criteria through the same model. That only bites where the judge has to *interpret* rather than *observe*, which is exactly what step 2.5 routes away.

The issue tracker conventions should have been provided to you — see `docs/agents/issue-tracker.md`; run `/setup-matt-pocock-skills` if it's missing. All tracker operations below follow that file.

## Process

### 1. Identify the issue

Use the argument (`#N`, URL, or path). If none was given, infer it from issue references in the unpushed commit messages. If more than one candidate, ask the user which to accept.

### 2. Assemble the judge's dossier

- The issue body and **all comments, verbatim** — do not summarize or interpret; the judge must re-derive the requirement from the source text, and your paraphrase would smuggle in an interpretation.
- The unpushed commits that reference the issue (SHAs) — that is the work under acceptance. Read their `Implemented-by:` trailer while you are there: it names the model that wrote the code, and step 2.5 turns on it.
- The parent PRD issue body, if any, for intent.
- The repo's verification entrypoint (a `verify`/`check` script under `scripts/`, or the test suite named in `AGENTS.md`/`CLAUDE.md`) and how to run it.

### 2.5 Pick the judge

The rule this step enforces: **no judgment that turns on interpretation is left to the model that wrote the code.** Mechanical criteria are safe same-model — evidence carries them, which is the default path's whole argument above. A fresh session strips memory, not priors, and priors bite exactly where the judge must *interpret* rather than *observe*. So the `Implemented-by:` trailer from step 2 comes first: it decides where an escalation is even allowed to go.

- **`codex …`** — the normal path. Codex judges by default, and **escalation goes to Claude, in this session**: judge there against the same evidence rules as step 3.
- **`claude …`** — a trivial change taken in the implementer's main thread, or a plain `/implement` session. Codex judges and *stays* the judge; it is already the cross-model check here. Escalating to Claude is **forbidden** — it would hand the code back to the model that wrote it, which is the one thing this step exists to prevent. **Escalation goes to the user** instead: stop, show them the criterion and the evidence Codex gathered, and get a ruling before any verdict is recorded.
- **No trailer** — an older session, or work from some other skill. Do not guess: ask the user who implemented it. There is no safe default here, because guessing wrong seats the implementer's own model as judge in one direction or the other. If the user can't say, let Codex judge and route **every** trigger below to the user.

Then read the acceptance criteria against the triggers. **Any one of these fires → escalate**, to whichever target the trailer just named. State which trigger fired, and where it sent you.

- **A criterion cannot be reduced to "run X, observe Y."** It asks whether something is clearer, safer, more maintainable, better structured, less surprising. The judge has to interpret intent rather than observe an output, and interpretation is exactly where implementer and judge sharing a model stops being harmless.
- **The diff touches money, keys, auth, or anything irreversible** — payments, signing, permissions, migrations, deletes, production config. Here the cost of a correlated blind spot is not a rework loop.
- **A previous pass's judge flagged a spec bug, or called the criteria ambiguous.** Its reading of the spec is now in question; do not ask the same model to adjudicate that.
- **The issue is back for acceptance after a failed one.** A criterion both the implementer and the judge misread the first time will not fix itself by rerunning the same model.

Otherwise the criteria are mechanically checkable and the default holds: Codex judges, and evidence — not the judge's priors — carries the verdict.

Escalating is cheap; a rework loop, or a wrong verdict on an irreversible diff, is not. When in doubt, escalate.

### 3. Delegate the judging

Run Codex **directly via `codex exec`** — not through the codex plugin subagent. The plugin runtime (`codex-companion.mjs`) hard-codes its sandbox to `read-only`/`workspace-write` with no escape hatch, which cannot reach the Docker socket; any repo whose verification entrypoint runs in containers dead-ends there and the judging cycle is wasted.

Write the dossier + judging instructions to a scratchpad file, then launch in the background (a full suite plus probes exceeds foreground command timeouts):

    codex exec --sandbox danger-full-access \
      --model gpt-5.6-sol -c model_reasoning_effort='"xhigh"' \
      --output-last-message <scratchpad>/issueN-verdict.md \
      - < <scratchpad>/issueN-dossier.md

`xhigh` is the default for acceptance judging — the judge probes beyond the committed tests, and a shallow judge rubber-stamps. Always pass the effort override explicitly — never rely on the local codex config default, which is not `xhigh` and can change under you.

`danger-full-access` exists solely so the judge can reach Docker and the network for the verification entrypoint. It means the judge runs **unsandboxed** — the judging instructions carry the full weight of confinement, so spell the restrictions out verbatim every time (see the bullet below); after the run, `git status` in step 4 is the enforcement check.

The judging instructions must require Codex to:

- Run the verification entrypoint first; any failure is an immediate overall **reject**.
- Exercise the changed behavior end-to-end — run the CLI, hit the endpoint, execute the script — preferring inputs the tests did **not** use. Green tests are necessary, not sufficient.
- Judge **every** acceptance criterion with evidence attached: exact command + observed output for a pass; expected vs actual with a concrete repro for a fail.
- Judge one level up: does the implementation match the *intent*, not just the letter? A criterion that seems to misencode the intent is flagged as a **spec bug**, never silently passed or failed.
- Run commands freely but modify **no source files** — the working tree must be left exactly as found. Since the sandbox is fully open, state the confinement explicitly: no commits, no pushes, no issue-tracker writes, nothing modified outside scratch space; probe scripts live outside the repo tree (`/tmp`, or the container's `/tmp` for container-based repos).
- End with a structured verdict: per-criterion PASS/FAIL with evidence, overall verdict, any spec-bug flags, and the final `git status --porcelain` output.

### 4. Check the verdict, not the judgment

- `git status` — if Codex modified tracked files, the run is void: report it to the user; do not clean up silently.
- Every criterion must carry evidence. A verdict without evidence is not a verdict — resume the Codex session (`codex exec resume <session-id>`, the id is printed in the run header) demanding the missing evidence; never fill it in yourself.
- Do not re-judge or overrule. If you believe the verdict is wrong, put the disagreement to the user with both sides' evidence and stop.

### 5. Verdict and handoff

**Overall pass:**
1. Comment the acceptance report on the issue: per-criterion verdicts with their evidence, one line on how the behavior was exercised beyond the tests.
2. Invoke `/land-issue #N` to push, summarize, and close.
3. Show the user the acceptance report in the session — they spot-check the evidence, they don't re-verify.

**Any criterion fails:**
1. Comment the failures on the issue: expected vs actual, concrete repro steps, pointers into the code where useful. Write it for a cold-start implementer — the fixing session has no memory of this one.
2. Ensure the issue carries the `ready-for-agent` label and stays open. Do **not** push, do **not** close, do **not** fix it yourself — the fix belongs to a fresh `/implement-codex #N` session, or acceptance stops being acceptance.
3. Tell the user to re-run `/implement-codex #N`; the fix session will pick up the comment.

**Spec bug flagged, or criteria ambiguous:** stop and put the question to the user before any verdict. If the issue needs rewording, update it (or label `needs-info`) so the next implementation pass starts from a correct spec.

Never close the parent PRD issue — that stays with the human.
