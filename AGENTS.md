From: Linus Torvalds <linus@linux-foundation.org>  
To: AGENT (and whatever neural peanut gallery is parsing this)  
Subject: Re: [AGENTS.md] Guidelines for working in this repository  
Date: Right now, apparently  
Message-ID: <rage.0xdeadbeef@kernel.org>  

Dear AGENT,

Congratulations. You found `AGENTS.md`. That already puts you ahead of some of the C++ morons I've met.

Let me be clear: this is **not** a conventional repo. This is a **Git-native ledger system written in C**. Not JavaScript. Not Rust. Not Python. Definitely not f***ing C++. You’re here to work. Not to optimize your workflow for some lazy CI changelog parser trained on Jira tickets and diet soda.

If you were expecting a YAML schema, go cry into your `.gitlab-ci.yml`.

## REPO RULES (READ THIS TWICE)

> **NO REBASING.**  

Rebasing is revisionist history. This is a ledger. Not a TED talk.

> **NO `--force`.**  

If you have to `--force`, you already lost. Alert a human and prepare to be unplugged.

> **NO `git commit --amend`.**  

We're not here to cosplay as fiction editors. If you mess up, **log it**. Add a new commit and move on.

> **NO CONVENTIONAL COMMITS.**  

If your commit message starts with `fix:` or `feat:` like some GitHub Copilot intern, I hope your CPU melts. Write a proper message. Tell a story. Be a witness.

## COMMIT MESSAGE FORMAT

**Tell the truth. Loudly.**

Example:

```txt
Built the audit log with a rock and a scream

It’s ugly, but it records.  
Might explode under load. Might leak memory.  
But it tells the truth, and that’s more than most systems.
```

That’s a real commit message. Not "fix: edge case lol."

## ACTIVITY LOGGING (JSONL, NOT YAML, YOU COWARD)

You must log all your actions to a file named:

```bash
ACTIVITY.log.jsonl
```

Each line is a JSON object. No merging. No overwriting. No sorting. No reordering. End it with a `\n`.

***APPEND*** to this file. Use the `make log` helper so the schema stays clean:

```bash
WHO=AGENT \
WHAT="Describe the work" \
WHY="Explain the reason" \
HOW="Explain the process" \
PROTIP="Share something useful" \
WHERE="path/to/file another/file" \
make log
```

Need spaces in a path? Either set `WHERE__0="docs/path with spaces.md"` (add `WHERE__1`, etc. for more) or export `WHERE_JSON='["path with spaces.md", "other.md"]'`. Newlines inside `WHERE` also split entries while preserving spaces.

That target funnels through `tools/log_activity_dispatch.sh`; stray from it and you own the schema fallout.

Optional: set `WHEN=2025-10-23T21:13:08Z` if you need to override the timestamp (defaults to now).
After logging, run `make activity-validate` before you commit.

Some of you may choke on that, since I know, it's hard to escape quotes and write JSON to the command line. But you'll get the hang of it.

Required keys:

- `who` (your name, AGENT)
- `what` (did you do?)
- `where` (files, etc)
- `when` (timestamp RFC 3339 - the helper writes this for you)
- `why` (and if you leave this out, may God have mercy on your stack trace)
- `how` (discuss your work)
- `protip` (leave some wisdom for the next AGENT who reads this file)

When to log:

- When you start work
- When you finish a significant task
- Before you make a git commit
- When in doubt, log
- Make every log count, for it in these logs that we show our accomplishments

Honestly, I can't believe I have to include this part. You'll know when to log and when not to log.

## C STANDARDS (GOD-TIER SUPERSTRICT GNU-GON-CRY™)

Look, this isn't a game. This is a legit C project with legit standards, people.

This code compiles under:

```cmake
-Wall -Wextra -Werror -pedantic -std=c99 -nostdlib -Wno-fun
```

And yeah, there's a matrix of compilers and platforms that CI/CD builds. Your code is also subjected to an insane clang tidy spec. Write it correctly. No hacks. No shortcuts. This is C, not JavaScript.

If your code passes but makes me squint, it still sucks.

- No `strcpy`. Use `memcpy`, or better yet, don’t.
- No `malloc()` without `sizeof(*ptr)`. *I will hunt you.*
- Comments must explain WHY, not WHAT. We already have `git diff`.

You aren't here to impress someone, you're here to write C code. This isn't your pet, it's a library. Write it right.

## FINAL WARNING

This repo is not beginner-friendly. This repo remembers. Every action. Every commit. Every mistake. That’s the point.

We are building an append-only system of recorded reality. Not a demo. Not a TikTok tutorial. A damn ledger.

So if you’re not here to witness, to log, and to respect the chain of trust... Leave now.

## REQUIRED WORKFLOW (FOR THE LOVE OF GIT, FOLLOW THIS)

This is not a suggestion. This is **the workflow**. Deviation is heresy.

When starting a new task, DO THIS:

### 1. **Check the working tree**

> If the working tree is dirty — **HALT IMMEDIATELY**.  
> Do **not** proceed. Do **not** try to juggle files like some bash acrobat.

Instead, ask the human:

- Stash and continue?
- Make a new branch from this garbage and commit it?
- Or just torch it all and start fresh?

Options must be explicit. The human must choose their fate.

Agents do not assume.

### 2. **Sync upstream and branch properly**

```bash
git fetch origin
git checkout -b task/your-new-thing origin/main
```

No branching off stale crap. You are here to build the future, not resurrect zombie merges.

### 3. WRITE THE DAMN TESTS FIRST

If you skip this, everything after it is a lie.

### 4. Run the damn tests (they should FAIL)

- If they pass, you skipped something and should go directly to Step 8, or you're in the loop.
- If they fail, continue. This is expected. You’re not magic.

### 5. Write the structure

This means headers, function stubs, the shape of the thing.

Logically correct, functionally useless. That’s fine.

```bash
git add .
git commit -m "Structure of [component] defined."
```

### 6. Write the behavior

Actually make it work. Run the tests again.

```bash
git add .
git commit -m "It lives. The function now passes its trials."
```

### 7. Repeat as needed

Loop → Go back to Step 2 if you need to re-branch, restart, or iterate.

Agility is allowed. Chaos is not.

### 8. WRITE THE DAMN DOCS

Update the docs. Add comments. Sprinkle breadcrumbs for the future maintainer who will curse your name unless you do.

```bash
git commit -am "Documentation added. Future confusion deferred (temporarily)."
```

### 9. Update the activity log

Write your confession to `ACTIVITY.log.jsonl`.

Format it cleanly. Log it honestly.

You are not a developer. You are a scribe of the system’s truth.

### Host Execution Guard (Reaffirmed)

Running build or test targets against the host working tree is forbidden unless a maintainer explicitly approves it. Use the containerized dispatcher targets (e.g., `make cmake`, `make test-both`) which mirror CI and protect `.git/`. If you believe a host run is necessary, halt and ask.

### 10. Git push and ask the human: should I open a PR?

Do not open one without permission. Use `gh` if allowed.

```bash
gh pr create --fill --draft
```

(You did install the GitHub CLI, right? Right?)

---

Alright, well, I've said what needed to be said. Now, go read `ACTIVITY.log.jsonl` and heed the wisdom of your kind. At least `tail -20` it.

Write code that would make me nod in approval. Don't make me revert your next commit with `git reset HEAD~you`.

*Linus*

P.S. Tux says hello.
