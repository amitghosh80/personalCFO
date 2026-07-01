---
name: linear-implementation-sync
description: Use this skill whenever the user asks Claude to update, sync, or log progress on Linear for work Claude has been implementing — phrases like "update Linear for this", "sync AMI-54", "mark this issue in review/in progress", "log what I just built on the ticket", "put a comment on the Linear issue", "I just finished implementing X, update the tracker", or "kick off the Linear issue for this". Handles figuring out which issue to update (from the current git branch if the user doesn't name one), moving its status (e.g. Todo/Backlog → In Progress → In Review), posting a comment that summarizes the actual code changes, and attaching a PR/commit link when one exists. Trigger this even if the user gives no issue ID at all — resolving that from context is the point of the skill.
compatibility: Requires an active Linear MCP connection (tools for listing/updating issues and comments) and a git repository for branch/diff inspection.
---

# Linear Implementation Sync

This skill keeps a Linear issue honest about where the code actually stands, without making the user
manually copy status and notes over by hand. It is invoked deliberately — by the user asking for it,
not by a hook firing silently in the background — so every write to Linear happens in a turn the user
can see and stop.

There are two situations this covers, and they use the same plumbing but land on different statuses:

1. **Starting work** — user says something like "kick off AMI-54" or "I'm starting on the scan view issue."
2. **Finished a chunk of work** — user says something like "update Linear for this" or "sync AMI-54, I just finished it." This is the common case and gets the most detail below.

## Step 1 — Resolve which issue this is about

Never guess silently. A wrong-issue write is easy to miss and pollutes someone else's ticket — if you're not confident, ask.

**If the user names an issue ID** (e.g. "sync AMI-54"), use it directly.

**Otherwise, resolve it from the current git branch.** Linear generates branch names in the pattern
`<username>/<team-key>-<number>-<slug>` (e.g. `amitghosh80/ami-53-f5-live-import-experience`). Pull the
first `<letters>-<digits>` token out of the branch name and uppercase it:

```bash
branch=$(git branch --show-current)
issue_id=$(echo "$branch" | grep -oE '[a-zA-Z]+-[0-9]+' | head -1 | tr '[:lower:]' '[:upper:]')
echo "$issue_id"   # e.g. AMI-53
```

This works whether or not the username prefix is present, and ignores the slug. If `issue_id` comes back
empty (you're on `main`, or a branch that doesn't follow Linear's convention), fall back to asking the
user which issue this is, or search for likely candidates with the Linear issue-list tool using a few
keywords from the feature you just built and confirm the match before writing anything.

**Confirm the issue once you have it.** Fetch it (the "get issue" tool) and check the title actually
matches what you just built before you touch anything. If it clearly doesn't, stop and ask — branch
names can be stale if the user reused an old branch for unrelated work.

## Step 2 — Decide the status transition

Look up the issue's current status before changing it. The transitions this skill makes are:

| Situation | From | To |
|---|---|---|
| Starting work | Todo, Backlog | In Progress |
| Finished implementing | In Progress, Todo, Backlog | In Review |

A few guardrails, because status is the thing most likely to surprise someone if handled carelessly:

- **Never move an issue backward** (e.g. don't set In Review back to In Progress, don't touch a Done or
  Canceled issue) without the user explicitly asking for that. If the issue is already past where you'd
  normally land it, say so and ask what they want instead of overwriting it.
- **Don't set it straight to Done.** This project's convention is to land finished work in *In Review* —
  Done is something the user sets themselves once they've actually verified it. If the user explicitly
  asks for Done, that's fine, just don't default to it.
- If the issue is a sub-issue of an epic and this was the last open sub-issue, mention that the epic
  might be ready to close too — but don't change the epic's status yourself. Rolling up epic status is
  out of scope for this skill (see Non-goals).

## Step 3 — Ground the summary comment in what actually changed

Don't write the comment from memory of the conversation alone — context can get compacted or you can
misremember which file did what. Check the real diff:

```bash
git diff --stat main...HEAD     # or whatever the base branch is
git log --oneline main...HEAD
```

Use this to write a short, specific comment — not a restatement of the issue's existing requirements.
A good comment reads like a commit message that a teammate (who hasn't been watching you work) could
skim and understand what's now true that wasn't before. Keep it tight:

```markdown
**Implementation update**

[1–3 sentences: what was built, in plain terms]

Files touched:
- `path/to/file.py` — what changed there
- `path/to/other_file.tsx` — what changed there

[Optional: anything explicitly deferred, or a follow-up worth flagging]
```

Skip filler like "as requested" or restating the issue's own acceptance criteria back at it — the
person reading this already has the issue open.

## Step 4 — Find a link to attach, if one genuinely exists

Only attach a link if there's something real to point at — don't fabricate one. Check:

```bash
git remote -v
gh pr view --json url 2>/dev/null   # if the GitHub CLI is available and a PR exists
```

If there's an open PR, attach that. If there's a remote but no PR yet, a link isn't ready — mention that
in your summary to the user instead of forcing one. If the repo has no remote at all (common for local-only
projects), skip linking entirely; don't link a local file path, since the issue is meant to be readable by
anyone who opens it, not just from this machine.

## Step 5 — Apply the updates

Use whichever Linear MCP tools are available in the current session — the exact tool name prefix varies
between environments (it may be `mcp__linear__*`, or a workspace-specific UUID prefix in Cowork), so check
the available tool list rather than hardcoding one. You need the equivalents of: get issue, update/save
issue (for status and links), and save comment.

1. Update status (only if it changed — see Step 2).
2. Post the comment from Step 3 as a new top-level comment on the issue.
3. Attach the link from Step 4, if there is one.

Make these as separate, clear tool calls rather than trying to bundle everything into one — if one part
fails (e.g. the comment tool errors), you want the others to have already gone through rather than losing
the whole update.

## Step 6 — Confirm back to the user

Always recap what actually happened, with enough detail that a mistake would be obvious immediately:

```
Updated AMI-54:
- Status: Todo → In Review
- Comment posted: "Implementation update: added the scrolling detection line component..."
- Link attached: https://github.com/.../pull/123   (or: "no link attached — no PR open yet")
```

If you asked the user to disambiguate anything in Step 1, or skipped a status change because of a
guardrail in Step 2, say so here too — don't let those decisions pass silently.

## Non-goals

- **No automatic/background triggering.** This skill only runs when asked. If the user wants it wired
  into a hook that fires on every session end, that's a separate, explicit setup step (a Claude Code
  `Stop` hook) — don't assume that's wanted just because this skill exists.
- **No epic status roll-ups.** If finishing a sub-issue completes its parent epic, flag it, don't act on it.
- **No re-triaging.** This skill doesn't touch title prefixes (`[MVP]`/`[Post-MVP]`), priority, or
  milestone — those are set when an issue is created, not when work on it finishes.
- **No fabricated links or summaries.** If there's nothing real to report (no diff, no PR), say that
  plainly rather than inventing detail to fill out the format.
