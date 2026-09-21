---
name: land-issue
description: "Land a completed issue: push the branch, integrate it per the repo's convention, comment a summary on the issue, and close it. Use after the implementation session has committed and the work has been accepted — it does not care which skill or model did the implementing."
disable-model-invocation: true
---

# Land Issue

Finish an implemented issue: push, integrate, report back on the ticket, close it.

The issue tracker conventions should have been provided to you — see `docs/agents/issue-tracker.md`; run `/setup-matt-pocock-skills` if it's missing. All tracker and integration operations below follow that file, so this skill works with GitHub, GitLab, or local-markdown trackers alike, and with review-required or direct-merge repos alike.

## Process

### 1. Identify the issue

Use the argument (`#N`, URL, or path). If none was given, infer it from issue references in the unpushed commit messages. If more than one candidate, ask the user which to land.

### 2. Preflight — refuse to land half-done work

- Working tree must be clean. Uncommitted changes → stop and report; don't commit or stash on the user's behalf.
- At least one unpushed commit must reference the issue. None → nothing to land; say so. If the branch also carries unpushed commits for *other* issues, stop and ask — pushing here lands them too, and they may not be accepted; don't push a mixed branch on your own.
- The branch must already contain the integration target's latest commit (usually `main`). Behind → bring the target in first (rebase or merge, whichever the repo uses). Two things break otherwise: the verification below runs against a tree that is not the one that lands, and on a direct-merge repo a stale branch can silently revert commits that landed while this work was in flight.
- If the repo has a verification entrypoint (a `verify`/`check` script under `scripts/`, or a test suite named in `AGENTS.md`/`CLAUDE.md`), run it once — *after* the branch is up to date, so it verifies what will actually land. Failure → stop and report; don't push.

### 3. Push

Push the current branch to its remote, setting upstream if needed.

### 4. Integrate

Pushing a branch is not integrating it. Finish the job the way the repo says:

- **Review required** → open a pull/merge request against the integration branch and carry its link into the comment below. The issue stays OPEN until that request merges — say so instead of closing it.
- **Direct merge declared** → merge into the integration branch using the merge shape the repo states, push, then delete the remote branch and remove any worktree this work used.
- **Repo declares nothing** → stop here and tell the user plainly that the code is pushed but is NOT in the integration branch, and what remains to be done. Never infer a merge policy, and never force-push.

Resolve conflicts by the repo's stated rule if it has one. After any conflict resolution, re-run the verification entrypoint before merging: two branches that were each green apart are not necessarily green together.

### 5. Report on the issue

Comment on the issue following the tracker conventions: one short paragraph of what shipped, the commit SHAs, where it landed (integration branch, or the request's link), and how it was verified. Write it for the person doing acceptance, not as a changelog dump.

### 6. Close

Close the issue via the tracker's convention, ticking acceptance-criteria checkboxes if supported.

Close only once the code is actually integrated. On a review-required repo that means the issue closes when the request merges, not now. Keeping the tracker BEHIND the code is deliberate: an interrupted run should leave an open issue over merged code (visible, recoverable), never a closed issue over code that never reached the integration branch (invisible until someone stumbles on it).

Do **not** close any parent PRD issue. If this was the parent's last open child, mention that to the user so they can close the parent after their own acceptance pass.
