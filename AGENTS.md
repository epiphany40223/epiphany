# Working in this repository

Conventions for humans and AI assistants working in this repo. `CLAUDE.md`
is a symlink to this file, so Claude Code reads the same guidance.

## About this repo

Automation and scripting for Epiphany Catholic Church ("ECC"). Most code is
Python 3 glue around third-party services: ParishSoft (parish database),
Constant Contact (email), Google Workspace / Drive, OpenAI, Meraki, and
Slack. Scripts generally run on a schedule (see the per-project `run.sh`
files) rather than interactively.

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
  around 75 characters.
- **One logical change per commit.** Keep incidental "drive-by" fixes you
  notice while working on something else as their own standalone commits,
  separate from your main change, so each can be reviewed and bisected on
  its own.

## Branches & pull requests

- `main` is production. This repo does not use release branches.
- Do work on a topic branch named `pr/<short-topic>` and land it through a
  GitHub pull request. Don't commit directly to `main`.

## Shared Python modules

- Common code lives in the top-level `python/` directory (`ECC.py`,
  `ConstantContact.py`, `ParishSoftv2.py`, `Google.py`, `GoogleAuth.py`,
  `ECCUploader.py`, ...).
- Individual projects reach it through an `ecc-python-modules` symlink that
  points (via a relative path) at `python/`. Run scripts from their own
  directory so the symlink and the `sys.path` insert resolve.
- On Windows the symlink may be checked out as a text file containing the
  target path; the scripts already handle that case — don't "fix" it.

## Secrets & parishioner data — never commit them

- This repo handles real parishioner PII and live service credentials.
  **Never commit** API keys, OAuth client IDs, access/refresh tokens, or
  exported member data.
- Credentials live **outside** the repo and are passed in as CLI arguments
  (e.g. `--cc-client-id`, `--cc-access-token`, `--ps-api-keyfile`,
  `--service-account-json`). See `run.sh` for the canonical invocations.
- `.gitignore` already excludes the usual offenders (`client_id.json`,
  `user-credentials.json`, `slack_token.txt`, `*.csv`, `*.xlsx`,
  `*.sqlite3`, `venv`, caches). Stage explicit paths — don't `git add -A` —
  and check `git status` so local logs, caches, `*.out`, and scratch
  scripts don't sneak into a commit.

## Running & testing

- Python 3 with a per-project `venv/` (gitignored); dependencies in
  `requirements.txt`. Scripts use `#!/usr/bin/env python3`.
- Many scripts mutate live third-party state (Constant Contact contacts,
  Google group membership, ParishSoft data, ...). Prefer `--dry-run` /
  `--no-sync` style flags while iterating, and validate destructive
  behavior against throwaway data before running against production.
