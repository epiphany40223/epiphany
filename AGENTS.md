# Working in this repository

Conventions for humans and AI assistants working in this repo. `CLAUDE.md`
is a symlink to this file, so Claude Code reads the same guidance.

## About this repo

Automation and scripting for Epiphany Catholic Church ("ECC"). Most code is
Python 3 glue around third-party services: ParishSoft (parish database),
Constant Contact (email), Google Workspace / Drive, OpenAI, Meraki, and
Slack. Scripts generally run on a schedule (see the per-project `run.sh`
files) rather than interactively.

This repository is a collection of operational scripts, not a single packaged
application. Many scripts have local assumptions from how they are actually
run for ECC in Louisville, KY, so read the relevant scripts and any local
README files before changing behavior.

## Working style

- Keep changes scoped to the script, helper module, or operational area being
  worked on.
- Preserve existing behavior unless an intentional change is requested or
  documented.
- Do not remove, rewrite, or clean up unrelated files.
- Assume untracked or modified files may be local operational artifacts or
  user work; do not clean them up unless explicitly asked.

## Commits

- **Sign off every commit.** Each commit needs a `Signed-off-by:` line per
  the Contributor's Declaration — use `git commit -s`. Commits without it
  are not accepted. This applies to AI-assisted work too: the human
  submitter certifies the contribution. Use your real name and email.
- **Commit messages:** a short first line saying *what* changed, then a
  blank line, then a body explaining *why*. An optional area prefix is
  common (e.g. `sync-ps-to-cc:`, `sync-google-group:`, `cc-sync:`). This
  repo does **not** use Conventional Commits (`feat:`/`fix:`/`chore:`
  prefixes) — write prose. **Do not add AI tooling attribution** (no
  `Co-Authored-By:` or "Generated with" trailers). Wrap message lines at
  around 75 characters. Use an editor or message file for multi-line commit
  messages; avoid relying on inline `\n` sequences in command-line
  arguments.
- **One logical change per commit.** Keep incidental "drive-by" fixes you
  notice while working on something else as their own standalone commits,
  separate from your main change, so each can be reviewed and bisected on
  its own. Squash fixup commits appropriately before pull requests are
  merged into their target branches.

## Branches & pull requests

- `main` is production. This repo does not use release branches.
- Do work on a topic branch named `pr/<short-topic>` and land it through a
  GitHub pull request. Don't commit directly to `main`.
- Working in git worktrees is fine, especially when coordinating with
  multiple agents or teams. When working in a worktree, avoid repo-global
  commands such as `git stash` or `git worktree prune`.
- GitHub pull request and issue descriptions should use one line per
  paragraph and let GitHub render wrapping.

## Shared Python modules

- Common code lives in the top-level `python/` directory (`ECC.py`,
  `ConstantContact.py`, `ParishSoftv2.py`, `Google.py`, `GoogleAuth.py`,
  `ECCUploader.py`, ...).
- Individual projects reach it through an `ecc-python-modules` symlink that
  points (via a relative path) at `python/`. Run scripts from their own
  directory so the symlink and the `sys.path` insert resolve.
- On Windows the symlink may be checked out as a text file containing the
  target path; the scripts already handle that case — don't "fix" it.
- Many script directories have their own `requirements.txt`; use the local one
  for that directory when installing or validating dependencies.
- New executable Python scripts should start with `#!/usr/bin/env python3`
  where practical and should have their executable bit set.
- Prefer `argparse` for new command-line options, matching the surrounding
  scripts.
- Prefer explicit CLI options or local config files for new operational
  settings. Do not introduce new hard-coded secrets.

## Operations

- `media/linux/run-all.py` is the top-level cron-oriented runner for the
  Linux/media automation area.
- `media/linux/run-all.py` uses a lockfile to avoid overlapping runs.
- `media/linux/run-all.py` invokes `run.sh` scripts in subdirectories;
  preserve that convention when changing scheduled media/Linux jobs.
- Keep `run.sh` wrappers simple. They should set up the local environment and
  invoke the real script, not duplicate application logic.

## Secrets & parishioner data — never commit them

- This repo handles real parishioner PII and live service credentials.
  **Never commit** API keys, OAuth client IDs, access/refresh tokens, or
  exported member data.
- Credentials live **outside** the repo and are passed in as CLI arguments
  (e.g. `--cc-client-id`, `--cc-access-token`, `--ps-api-keyfile`,
  `--service-account-json`). See `run.sh` for the canonical invocations.
- `.gitignore` already excludes the usual offenders (`client_id.json`,
  `user-credentials.json`, `slack_token.txt`, `*.csv`, `*.xlsx`,
  `*.sqlite3`, `venv`, caches, `cache-v1-*.json`, `cache-v2-*.json`). Stage
  explicit paths — don't `git add -A` — and check `git status` so local logs,
  caches, `*.out`, and scratch scripts don't sneak into a commit.
- If a script needs a new credential or generated artifact, add or update
  `.gitignore` as part of the change.

## Running & testing

- Python 3 with a per-project `venv/` (gitignored); dependencies in
  `requirements.txt`. Scripts use `#!/usr/bin/env python3`.
- Many scripts mutate live third-party state (Constant Contact contacts,
  Google group membership, ParishSoft data, ...). Prefer `--dry-run` /
  `--no-sync` style flags while iterating, and validate destructive
  behavior against throwaway data before running against production.
- There is no repository-wide CI, lint, format, or test command at present.
- Validate changes with the most local applicable command for the script or
  directory being changed.
- If a directory has tests, run those tests.
- For documentation/spec-only changes, review the rendered structure and check
  the git diff.
