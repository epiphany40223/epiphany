# Evolve Existing Parish Scripts to `parishkit`

## Overview

Create a new GitHub repository named `parishkit` in the
`epiphany40223` organization. The new repository will contain evolved,
generalized versions of selected Python scripts from this repository.

The primary goal is to remove Epiphany Catholic Church-specific assumptions
from reusable code and make the scripts suitable for use by other Catholic
parishes. Parish-specific behavior, names, domains, Google object IDs,
ministry mappings, Constant Contact list mappings, credentials, and secrets
must be supplied at runtime through command-line options and YAML
configuration files.

The new repository is both:

1. An installable Python package named `parishkit`.
2. A collection of executable script wrappers, each with its own README and
   example configuration.

Target runtime: Python 3.12 or newer.

## Repository Name

Repository name: `parishkit`

Python package name: `parishkit`

Preferred CLI naming convention:

- `parishkit-print-member`
- `parishkit-print-ministries`
- `parishkit-calendar-reservations`
- `parishkit-create-ministry-rosters`
- `parishkit-sync-google-group`
- `parishkit-sync-ps-to-cc`
- `parishkit-run`

The repository and package name intentionally avoid references to Epiphany,
ECC, Louisville, or a specific diocese. The package should be reusable by any
Catholic parish with compatible ParishSoft, Google Workspace, and related
services.

## Repository Layout

Use a standard Python source layout:

```text
README.md
CLAUDE.md
AGENTS.md -> CLAUDE.md
.gitignore
requirements.txt
pyproject.toml
src/parishkit/
  __init__.py
  cli.py
  config.py
  logging.py
  runner.py
  retry.py
  parishsoft.py
  constant_contact.py
  google/
    __init__.py
    auth.py
    calendar.py
    drive.py
    groups.py
    sheets.py
  email/
    __init__.py
    base.py
    google_workspace.py
    ms365.py
scripts/
  run/
    README.md
    parishkit-run.py
    example-config.yaml
  print-member/
    README.md
    print-member.py
    example-config.yaml
  print-ministries/
    README.md
    print-ministries.py
    example-config.yaml
  calendar-reservations/
    README.md
    calendar-reservations.py
    example-config.yaml
  create-ministry-rosters/
    README.md
    create-ministry-rosters.py
    example-config.yaml
  sync-google-group/
    README.md
    sync-google-group.py
    example-config.yaml
  sync-ps-to-cc/
    README.md
    sync-ps-to-cc.py
    example-config.yaml
tests/
.github/workflows/ci.yml
migrate-to-parishkit/
  README.md
  run-*.sh
```

The exact internal module names can evolve during implementation, but the
layout should preserve these principles:

- Shared code lives under `src/parishkit`.
- Script wrappers live under `scripts/<tool-name>/`.
- Each script directory has its own `README.md`.
- Example configuration files contain fake or generic sample data only.
- No `ecc-python-modules` symlink strategy is carried forward.
- No script should modify `sys.path` to import common code.

The implementation work is expected to create the new repository locally and
fully populate it. It should also create a `migrate-to-parishkit/` directory in
the old repository containing cron-friendly wrapper scripts that invoke the new
`parishkit` commands in place of the old repository scripts.

## Executables

Each script wrapper must:

- Start with `#!/usr/bin/env python3`.
- Have its executable bit set.
- Contain minimal logic.
- Import real implementation code from `parishkit`.
- Use the common CLI, logging, configuration, retry, and auth helpers.

The package should also expose console entry points via `pyproject.toml`, so
the tools can be run after installation without referencing the wrapper files
directly.

## Common CLI Conventions

All tools should use consistent option names and behavior.

Common options:

```text
--config CONFIG.yaml
--dry-run
--verbose
--debug
--log-file PATH
--log-dir PATH
--slack-token-file PATH
--slack-channel CHANNEL
--slack-log-level CRITICAL
--ps-api-key-file PATH
--ps-cache-dir PATH
--ps-cache-limit 14m
```

Tool-specific options are allowed, but common concepts must use common names.

Rules:

- `--debug` implies verbose logging.
- `--dry-run` must avoid mutating external systems.
- CLI options should override config values when both are supplied.
- Secrets may be provided by file path, environment-variable reference, or
  another explicit runtime mechanism, but must not be embedded in code or
  sample config.

## Scheduled Job Runner

Create shared runner/orchestration support for cron-driven scheduled jobs.
This should carry forward the useful operational ideas from the current
`media/linux/run-all.py` and `slack/runner.py` scripts, but in a reusable
`parishkit` form.

The runner should support:

- Lockfile protection to prevent more than one concurrent run.
- Stale-lock detection.
- Configurable stale-lock behavior:
  - exit and alert,
  - remove stale lock and continue,
  - or fail closed.
- Lock metadata that is useful for debugging, such as host, PID, command,
  start time, and configured timeout.
- Safe lock cleanup on normal exit and handled exceptions.
- Top-level logging using `parishkit.logging`.
- Top-level Slack reporting using the standard Slack handler.
- Watchdog timeout support for child commands.
- Capture of child stdout/stderr for logging and optional Slack attachment or
  message inclusion.
- Optional Slack notification on success.
- Optional contextual Slack comments, such as "Linux cron run-all automation".
- Clear exit codes suitable for cron.
- Configurable job list in YAML.
- Optional CLI selection of which configured jobs/executables to run.
- Optional config-file selection of which jobs are enabled.
- Default behavior that runs all configured/enabled jobs when no explicit job
  selection is supplied.
- Per-job working directory.
- Per-job environment overrides.
- Per-job timeout.
- Per-job enabled/disabled flag.
- A choice of whether the runner stops on first failure or continues through
  later jobs and reports a summary.

Recommended console entry point:

```text
parishkit-run
```

Recommended wrapper directory:

```text
scripts/run/
```

The runner should be able to replace the old pattern where cron calls a shell
wrapper, which calls `slack/runner.py`, which calls `media/linux/run-all.py`,
which then calls multiple `run.sh` scripts. Shell wrappers may still exist for
site-specific deployment convenience, but the lockfile, timeout, logging, and
Slack behavior should be available from `parishkit-run` itself.

Example runner config shape:

```yaml
lock:
  path: /opt/parishkit/run/linux.lock
  stale_after: 16m
  stale_action: remove-and-continue

logging:
  log_file: /opt/parishkit/logs/runner.log
  rotate: true

slack:
  token_file: /opt/parishkit/credentials/slack-token.txt
  channel: "#bot-errors"
  level: CRITICAL
  notify_success: false

jobs:
  - name: sync-google-group
    enabled: true
    cwd: /opt/parishkit
    timeout: 15m
    command:
      - parishkit-sync-google-group
      - --config
      - /opt/parishkit/config/sync-google-group.yaml
```

Expected runner selection behavior:

- If no `--config` is supplied, look for a default runner config such as
  `/opt/parishkit/config/runner.yaml`.
- If a runner config file is available and no CLI job filter is supplied, run
  all enabled jobs in the config.
- If CLI job names are supplied, run only those configured jobs.
- If config marks jobs disabled, do not run them unless an explicit override is
  provided and documented.
- If no runner config file is available and a command is supplied on the CLI,
  support a simple mode that runs that command under the same lockfile,
  logging, Slack, and watchdog protections.
- If no runner config file is available and no command is supplied, exit with a
  clear configuration error.

Additional runner considerations:

- Prefer an atomic lock implementation. If a dependency is used, keep it small
  and well maintained.
- Handle termination signals where practical so lock cleanup is reliable.
- Avoid shell interpolation by default; commands should preferably be expressed
  as argument lists.
- Allow an explicit shell mode only if needed and clearly documented.
- Do not put secrets directly in runner YAML.
- Keep scheduling decisions simple. Cron can continue to decide when the
  top-level runner starts; the runner config can handle lightweight per-job
  enablement and sequencing.

## Default Runtime Paths

Default runtime file locations may be rooted under `/opt/parishkit`.

Recommended defaults:

```text
/opt/parishkit/config/
/opt/parishkit/credentials/
/opt/parishkit/cache/
/opt/parishkit/logs/
/opt/parishkit/run/
```

Examples:

- Logs default to `/opt/parishkit/logs/`.
- ParishSoft API key files may default to
  `/opt/parishkit/credentials/parishsoft-api-key.txt`.
- Google service account JSON files may default to
  `/opt/parishkit/credentials/google-service-account.json`.
- Google OAuth user token files may default under
  `/opt/parishkit/credentials/`.
- Constant Contact client/token files may default under
  `/opt/parishkit/credentials/`.
- YAML configs may default under `/opt/parishkit/config/`.

All such defaults must be overridable by CLI parameters and/or YAML config.

## Configuration

All parish-specific mappings and operational settings should be expressed as
YAML files.

Configuration examples to migrate from code into YAML:

- Google calendar IDs and acceptable sender domains from
  `calendar-reservations.py`.
- Ministry-to-Google-Sheet mappings from `create-ministry-rosters.py`.
- ParishSoft ministry/workgroup to Google Group mappings from
  `sync-google-group.py`.
- ParishSoft Member Workgroup to Constant Contact list mappings from
  `cc_sync_config.py` and `sync-ps-to-cc.py`.

Configuration must be validated at startup. Invalid config should fail fast
with a clear error message before any external writes occur.

Recommended implementation:

- `parishkit.config` loads YAML.
- Validation uses either dataclasses with explicit validation or a validation
  library such as Pydantic.
- Example configs are committed.
- Real configs containing parish-specific private data are not committed.

## Secrets and Credentials

No secrets or credentials may be committed or hard-coded.

This includes:

- ParishSoft API keys.
- Google Cloud service account JSON keys.
- Google OAuth client secrets.
- Google OAuth refresh/user token files.
- Constant Contact OAuth tokens.
- Slack bot tokens.
- SMTP credentials.
- Parish-specific private IDs if they should not be public.

Secrets should be passed by command-line file paths, environment variables, or
documented runtime deployment mechanisms.

## ParishSoft

Carry forward `python/ParishSoftv2.py` as the basis for
`parishkit.parishsoft`. Do not carry forward `ParishSoftv1.py`.

Goals:

- Preserve useful v2 API behavior.
- Keep local JSON caching with configurable cache age.
- Keep useful cross-linking and helper/query functions.
- Remove Epiphany/ECC-specific defaults.
- Make expected organization names and validation settings configurable.
- Ensure all REST calls use retry-aware sessions or decorators.
- Keep API calls small enough that retrying a function is safe and atomic.

The ParishSoft API key must be supplied at runtime, typically through
`--ps-api-key-file`.

Documentation should state that parishes must contact ParishSoft sales to
purchase or obtain API access.

## Constant Contact

Carry forward `python/ConstantContact.py` as the basis for
`parishkit.constant_contact`.

Goals:

- Preserve useful OAuth2 token handling, API pagination, list/contact helpers,
  and ParishSoft linking behavior.
- Keep retry behavior for transient API failures and rate limits.
- Improve naming/style to match the new package.
- Avoid assumptions about Epiphany-specific lists or notification addresses.
- Ensure all mappings are supplied by YAML config.

The Constant Contact module is shared library code and does not need to be
executable.

## Google APIs

Modernize Google API usage.

The existing code uses older `oauth2client` patterns in several places. The
new repository should drop `oauth2client` and use current Google libraries:

- `google-auth`
- `google-auth-oauthlib`
- `google-api-python-client`
- `google-auth-httplib2` if needed by `google-api-python-client`

Preferred auth strategy:

1. Use Google Cloud service accounts with Google Workspace domain-wide
   delegation wherever possible.
2. Use user OAuth only for APIs or workflows where service-account delegation
   cannot satisfy the requirement.

Documentation should recommend one Google Cloud project per parish. This keeps
IAM, API enablement, quotas, ownership, auditability, and offboarding scoped to
the parish using the software.

The top-level README should include setup guidance for:

- Creating a Google Cloud project.
- Enabling required APIs.
- Creating service accounts.
- Creating service account keys when needed.
- Configuring domain-wide delegation in Google Workspace.
- Creating OAuth clients for user-consent flows when needed.
- Storing credential files outside git.
- Passing credential file paths through CLI/config.

## Email

Create a modular email provider system under `parishkit.email`.

Initial provider:

- Google Workspace SMTP using XOAUTH2 and a service account with domain-wide
  delegation.

Future/stub provider:

- Microsoft 365.

The MS365 provider should include a clear interface and configuration shape,
but it can be a stub in the first version because there is no available test
environment.

Email design goals:

- Common send API used by all tools.
- Provider selected at runtime from config/CLI.
- No default sender address tied to Epiphany.
- Support plain text and HTML bodies.
- Support attachments where existing scripts need them.
- Keep authentication setup separate from message construction.

## Logging and Slack

All tools should use shared logging setup from `parishkit.logging`.

Required logging features:

- Console logging.
- Optional file logging.
- Optional rotating logs.
- Compression of rotated logs.
- Common `--verbose` and `--debug` behavior.
- Optional Slack handler for critical errors.

Slack behavior:

- Slack token is supplied at runtime.
- Slack channel is configurable.
- Slack emission is reserved for `CRITICAL` logs by default, matching the
  behavior of the current codebase.
- The Slack threshold may be configurable, but the default should remain
  `CRITICAL`.
- Failure to emit to Slack should be logged without masking the original
  critical error.

## Retry and REST API Calls

All RESTful API usage may be modernized as part of the migration. Some of the
existing scripts are old and may rely on stale client-library patterns, older
REST endpoints, or outdated examples. It is acceptable, and often desirable, to
move to current recommended APIs, client-library methods, request/response
shapes, auth patterns, pagination behavior, and rate-limit handling.

All RESTful API calls should also be wrapped in retry-aware helpers or
decorators for common transient failures.

This applies to:

- Google APIs.
- ParishSoft APIs.
- Constant Contact APIs.
- Slack APIs.
- Future external APIs.

Modernization examples:

- Newer Google Drive, Calendar, Sheets, Groups, and Admin SDK client patterns.
- Newer Constant Contact API endpoints or token-handling conventions.
- Newer ParishSoft API conventions, if documented and compatible with the
  needed data.
- Newer Slack SDK/API conventions.
- Replacing ad hoc `requests` usage with shared sessions and typed helper
  functions where doing so improves correctness and maintainability.

Modernization rules:

- Preserve user-visible tool behavior unless an intentional behavior change is
  requested or documented.
- Prefer current official documentation and supported client libraries.
- Keep compatibility risks visible in comments, tests, or migration notes.
- Use mocked tests and manual smoke tests where real credentials are required
  to verify modernized integrations.

Retry rules:

- Retry only atomic operations where repeating the call is safe.
- Keep API-call functions small enough that retrying the whole function is
  appropriate.
- Respect service-specific rate-limit signals such as `Retry-After` when
  available.
- Do not retry validation errors, authentication errors, or permanent
  authorization failures unless the API explicitly documents them as
  transient.

## Scripts to Migrate

### Common Library Code

From `python/`:

- `ParishSoftv2.py` -> `parishkit.parishsoft`
- `ConstantContact.py` -> `parishkit.constant_contact`
- `Google.py` and `GoogleAuth.py` -> modules under `parishkit.google`
- Useful parts of `ECC.py` -> `parishkit.logging`, `parishkit.email`, and
  other neutral helpers as appropriate

Do not carry forward:

- `ParishSoftv1.py`
- `ECC` naming
- Epiphany-specific defaults in reusable modules
- `ecc-python-modules` symlink/import pattern

### ParishSoft Utilities

From `ps-queries/utilities/`:

- `print-member.py`
- `print-ministries.py`

`print-member.py` changes:

- Accept a ParishSoft Member DUID, Family DUID, or name search from CLI.
- Remove hard-coded DUIDs.
- Add a CLI option controlling whether family contributions are loaded.
- Use common ParishSoft/cache/logging options.

`print-ministries.py` changes:

- Use common ParishSoft/cache/logging options.
- Use shared package imports.
- Preserve the ability to print sorted ministry names.

### Calendar Reservations

From `media/linux/calendar-reservations/`:

- `calendar-reservations.py`

Changes:

- Move calendar definitions and acceptable domains to YAML.
- Use modern Google auth.
- Use common logging, Slack, retry, and CLI behavior.
- Preserve dry-run behavior.
- Remove Epiphany-specific defaults from code.

### ParishSoft to Google/Constant Contact Scripts

From `media/linux/ps-queries/`:

- `create-ministry-rosters.py`
- `sync-google-group.py`
- `sync-ps-to-cc.py`

`create-ministry-rosters.py` changes:

- Move ministry-to-sheet mappings to YAML.
- Use modern Google auth.
- Use shared ParishSoft, Google, logging, retry, and config helpers.

`sync-google-group.py` changes:

- Move synchronization mappings to YAML.
- Use modern Google auth.
- Keep notification behavior, but make all notification addresses configured.
- Use shared email provider.
- Use common dry-run/logging/retry behavior.

`sync-ps-to-cc.py` changes:

- Move `cc_sync_config.py` data to YAML.
- Preserve the current cleaner action-list architecture.
- Use shared ParishSoft, Constant Contact, email, logging, retry, and config
  helpers.

## Documentation

Top-level `README.md` should include:

- Project purpose.
- Non-goals and neutrality statement.
- Supported Python version.
- Installation instructions.
- Local development setup.
- Local lint/style/test commands.
- Overview of available tools.
- Links to each script README.
- ParishSoft API key instructions.
- Google Cloud / Google Workspace authentication setup.
- Secret handling rules.
- Basic scheduled-job guidance.

Each script README should include:

- What the script does.
- Required external systems.
- Required credentials.
- Required config file.
- Example command.
- Dry-run behavior.
- Logging behavior.
- Example YAML config.

## Migration Support

The implementation should create a `migrate-to-parishkit/` directory in this
repository.

That directory should contain:

- `README.md` explaining how a human operator migrates scheduled jobs from the
  old scripts to the new `parishkit` scripts.
- New-style `config.yaml` files as appropriate for the migrated scripts,
  including YAML conversions of existing hard-coded Python data structures.
- `run.sh`-style cron wrapper scripts that call the new local `parishkit`
  commands with equivalent config, credential, log, and cache paths.
- Clear notes about which old script each wrapper replaces.
- Any required manual setup steps, such as creating `/opt/parishkit`
  directories, creating or copying credentials, installing the new package, and
  updating cron entries.
- Detailed credential setup instructions, not only copy instructions. The
  migration README should describe how to create new credentials from scratch
  as if the operator is setting up a new parish.

The migration wrappers are transitional operational aids. They should not
contain secrets and should not duplicate application logic.

Migration config files may contain parish-specific operational identifiers
converted from the old scripts, such as calendar IDs, Google Group mappings,
ministry roster sheet IDs, and Constant Contact list mappings. They must not
contain credentials or secrets.

The migration README should include a fresh Google setup path:

- Create a new Google Cloud project for the parish.
- Enable the required Google APIs.
- Create service accounts where domain-wide delegation is appropriate.
- Enable domain-wide delegation on the service account.
- Configure the service account client ID and required scopes in Google
  Workspace Admin.
- Create and securely store service account JSON keys if key-based auth is
  used.
- Create OAuth consent configuration and OAuth client credentials for any
  workflows that still require user OAuth.
- Generate any required user OAuth token files.
- Place credentials under `/opt/parishkit/credentials/` or pass alternate
  paths through CLI/config.
- Update YAML config and cron wrappers to reference the chosen credential
  paths.

The README may also include an optional shortcut for reusing existing
credentials during migration, but the complete new-project setup should be
documented first.

## Agent Instructions

The new repository should have:

- `CLAUDE.md`
- `AGENTS.md` as a symlink to `CLAUDE.md`

The instructions should include:

- Purpose of the project.
- Guidance for ongoing development and maintenance of the `parishkit`
  repository, not migration-only instructions.
- Rule that reusable code must remain parish-neutral.
- Python 3.12+ requirement.
- Executable wrappers must have a shebang and executable bit.
- No ad hoc `sys.path` changes.
- No committed secrets or credentials.
- Keep `.gitignore` updated for generated files, local credentials, logs,
  caches, virtual environments, and other local operational artifacts.
- Config must be YAML for parish-specific mappings.
- Use shared logging/CLI/retry/auth helpers.
- Use `ruff` and `pytest`.
- Local validation commands.
- Preserve existing tool behavior unless an intentional behavior change is
  requested or documented.
- All commits should include a Developer Certificate of Origin
  `Signed-off-by:` trailer.
- There is no requirement for LLM attribution in commits.
- Use the Common Convention commit style.
- Prefer self-contained commits that leave the repository in a consistent
  state, so tools such as `git bisect` remain useful.
- Put drive-by fixes in their own commits instead of combining them with
  larger behavior changes.
- Squash fixup commits appropriately before pull requests are merged into their
  target branches.
- Prefer thorough commit messages that explain why the change exists, not only
  what changed.
- Commit message body lines should wrap at approximately 75 characters.
- GitHub pull request and issue descriptions should use GitHub's normal
  convention of one line per paragraph and let GitHub render wrapping.

## Dependencies

Create a top-level `requirements.txt` with grouped comments.

Expected dependency groups:

- Runtime core.
- Google APIs/auth.
- HTTP/retry.
- YAML/config validation.
- Email/Slack.
- Testing.
- Linting/formatting.

The exact package list will be finalized during implementation, but should
include at least:

- `google-api-python-client`
- `google-auth`
- `google-auth-oauthlib`
- `google-auth-httplib2`
- `requests`
- `urllib3`
- `PyYAML`
- `slack_sdk`
- `pytest`
- `ruff`

Avoid carrying forward obsolete dependencies unless a specific migrated script
still requires them. In particular, do not use `oauth2client`.

## CI and Local Validation

Use GitHub Actions for:

- Python linting.
- Python style/format checks.
- Python unit tests.
- Developer Certificate of Origin checks for `Signed-off-by:` trailers.

Use the same commands locally and in CI.

Recommended commands:

```bash
python -m pip install -r requirements.txt
ruff check .
ruff format --check .
pytest
```

The top-level README and `CLAUDE.md`/`AGENTS.md` should document these
commands.

The DCO workflow should use a maintained GitHub Action suitable for checking
commit sign-off trailers in pull requests. The exact action/version should be
selected during implementation based on current maintenance status.

## External-Service Validation

Automated unit tests should not require real ParishSoft, Google, Constant
Contact, Slack, or email-provider credentials. Those tests should use mocks,
fixtures, and local sample data wherever practical.

Some success conditions still require confidence that real credentials and
external integrations work. For those cases, implementation may include
throwaway or one-time smoke-test tools that a human operator runs manually with
real credentials. These tools should:

- Be clearly documented as manual validation tools.
- Require credentials through CLI options or environment-variable references.
- Avoid committing credentials, tokens, API responses with private data, or
  generated artifacts.
- Prefer read-only API checks where possible.
- Use explicit `--dry-run` or confirmation requirements before any external
  write.
- Keep output minimal and redact sensitive values.
- Be excluded from normal CI.

Examples include a Google auth smoke test, a Google Workspace email smoke test,
a ParishSoft API connectivity smoke test, a Constant Contact token/list smoke
test, and a Slack notification smoke test.

## Migration Quality Bar

Before considering the migration complete:

- All wrappers have shebangs and executable bits.
- No reusable module names contain `ECC`.
- No reusable code has Epiphany-specific defaults.
- No code relies on `ecc-python-modules` symlinks.
- No code uses `oauth2client`.
- All hard-coded operational mappings have moved to YAML.
- All scripts use common CLI/logging/config conventions.
- All scripts can run in dry-run mode where external writes are possible.
- Critical errors can be sent to Slack when configured.
- REST calls have appropriate retry behavior.
- Unit tests cover shared logic and action computation.
- Manual external-service smoke tests exist or are documented where real
  credentials are required to validate behavior beyond mocks.
- DCO sign-off checking is enabled in GitHub Actions.
- CI passes.
- `migrate-to-parishkit/` contains migration wrappers and operator
  documentation.

Perform a final source search for terms such as:

```text
ECC
Epiphany
churchofepiphany
epiphanycatholicchurch
Louisville
ecc-python-modules
oauth2client
```

Any remaining occurrences must be either removed, generalized, or explicitly
documented as historical/example-only text.
