---
name: git-push
description: Use this skill whenever the user asks Claude to push code to git — phrases like "push this", "push my changes", "push to git", "commit and push", "ship this", "push AMI-54's branch up", or "get this onto origin". Handles scoping the commit to the relevant changes (without sweeping up unrelated work-in-progress sitting in the same tree), cutting a feature branch automatically if the current branch is master/main, writing a commit message that matches the repo's existing style, and pushing to the remote. Trigger this even for a bare "push it" right after finishing some work — figuring out what "it" refers to is part of the job.
compatibility: Requires a git repository with a configured remote.
---

# Git Push

This skill turns "push this" into a safe, well-scoped push — not a blind `git add -A && git commit && git push`.
The two failure modes it's built to avoid: bundling unrelated work into one commit because the working tree
has several things going on at once, and pushing straight to a shared branch that other people (or CI) depend on.

## Step 1 — Scope the change

Run `git status --short` and `git diff --stat` before touching anything. If the working tree only has one
coherent thread of changes, the scope is everything. If it has several unrelated efforts mixed together
(this happens more often than you'd think — e.g. half-finished work from a different feature sitting
alongside what you just built), don't stage all of it just because the user said "push this." Use the
conversation context to figure out which files belong to the thing that was just worked on, and stage only
those:

```bash
git add path/to/file1.py path/to/file2.tsx   # scoped, not -A
```

If it's genuinely ambiguous which files belong to "this" — say, the user has been bouncing between two
features in the same session — ask rather than guess. A commit that silently includes someone else's WIP
is annoying to untangle later.

## Step 2 — Check the branch, cut a new one if needed

```bash
git branch --show-current
```

If the current branch is `master`, `main`, or `develop`, **do not commit directly on it** — these are shared
branches other things depend on (CI, deploys, other branches rebasing off them). Cut a feature branch first:

- **If this work corresponds to a known Linear issue** (you have an issue ID from context, or this session
  also used the `linear-implementation-sync` skill), use Linear's own naming convention so the two skills
  compose cleanly: `<username>/<team-key-lowercase>-<number>-<slug>` (e.g. `amitghosh80/ami-61-csv-export`).
- **Otherwise**, derive a short kebab-case slug from what actually changed (e.g. `add-csv-export-button`)
  and use that directly, or prefix with `feature/` if that matches what you see in `git branch -a` for this repo.

```bash
git checkout -b <branch-name>
```

If the current branch is already a feature branch (not master/main/develop), just use it — no need to
create another one on top.

## Step 3 — Write the commit message

Look at recent history to match the repo's actual voice instead of imposing a fixed format:

```bash
git log --oneline -10
```

Some repos use Conventional Commits (`feat: ...`, `fix: ...`); others just use a concise imperative sentence
with no prefix (e.g. "Anchor chat answers to today's date to prevent wrong-period guesses"). Match whichever
pattern is already there. Either way, the message should describe what actually changed, grounded in the
diff you scoped in Step 1 — not a restatement of the original ask. Check `git diff --cached --stat` (after
staging) to confirm the message matches what's actually staged.

## Step 4 — Show the diff and message, then push

Recap what's about to happen before running it — file list, branch, and the drafted commit message — then
proceed with the commit and push in the same turn (no separate approval round-trip needed; the user asking
for this is the approval):

```bash
git commit -m "<message>"
git push -u origin <branch-name>          # -u on first push of a new branch
git push                                  # subsequent pushes to a branch already tracking upstream
```

**Hard rules, regardless of how the push goes:**

- **Never `--force` or `--force-with-lease`.** If `git push` is rejected because the remote has diverged,
  stop and tell the user what happened — don't rewrite history to make it go through. Force-pushing without
  being explicitly asked is the kind of thing that quietly destroys someone's work.
- **Never push directly to master/main/develop** — that's what Step 2 is for. If you somehow end up there
  anyway (e.g. the user explicitly insists), confirm that's really what they want before doing it.
- **Respect `.gitignore`.** Don't add files it excludes even if they show up some other way (e.g. explicitly
  named) — `.env` files and similar are excluded for a reason.

## Step 5 — Confirm back to the user

Recap clearly: branch pushed, commit message used, and (if the remote is a GitHub/GitLab/Bitbucket-style
URL) construct the compare/PR-creation link so it's one click away — without actually opening a PR, since
that's a separate action this skill doesn't take:

```
Pushed to amitghosh80/ami-61-csv-export:
"Add CSV export button to transactions table"
Compare/PR: https://github.com/<owner>/<repo>/compare/master...amitghosh80/ami-61-csv-export
```

If a GitHub-style remote isn't present, just confirm the push and skip the link rather than guessing at a URL.

## Non-goals

- **No automatic PR creation.** This skill pushes the branch; opening a pull request (via `gh pr create` or
  otherwise) is a deliberate separate step, not something to do automatically just because a push succeeded.
- **No test-gating.** Some repos (this one included, per its CLAUDE.md) expect specific test suites to be run
  before committing changes to certain files. This skill doesn't enforce that automatically — that's a
  conscious choice to keep this skill narrowly about git mechanics. If the repo's project instructions call
  for running tests first, do that as a separate step before invoking this skill, not as part of it.
- **No merging, rebasing, or conflict resolution.** If a push fails for reasons other than a simple
  fast-forward (diverged history, merge conflicts), stop and explain the situation rather than trying to
  resolve it automatically.
