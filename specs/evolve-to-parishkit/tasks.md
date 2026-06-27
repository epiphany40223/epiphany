# Evolve to `parishkit` Implementation Tasks

## Per-Phase Review Loop

At the end of each implementation phase, before the phase success condition is
accepted and before moving to the next phase, run an iterative code review and
fix loop.

- [ ] Launch three independent code-specialist review agents with minimal
      context for the completed phase:
      - One focused on code correctness and behavioral regressions.
      - One focused on software quality, maintainability, testing, and
        operational robustness.
      - One focused on overall software design, module boundaries, extensibility,
        and fit with the `parishkit` architecture.
- [ ] Give each review agent only the phase objective, relevant changed files,
      tests, and local conventions needed for that review.
- [ ] Require each review agent to report findings with severity, file/line
      references, concrete impact, and a recommended fix.
- [ ] Have the coordinator collate and de-duplicate all review findings.
- [ ] Have the coordinator validate each finding against the code and push back
      on findings that are incorrect, speculative, out of scope, or lower value
      than their stated severity.
- [ ] Fix every validated finding with `MEDIUM` severity or higher before the
      phase is considered complete.
- [ ] Re-run the relevant local validation commands after fixes.
- [ ] Repeat the multi-agent review round after fixes.
- [ ] Exit the review and fix loop only when the coordinator fixes nothing in a
      review round.

This loop applies to every implementation phase below, including focused script
migration phases and the final cleanup/validation phase.

## 1. Create the New Repository

- [x] Choose the local path for the new `parishkit` repository.
- [x] Initialize a new git repository named `parishkit`.
- [x] Add a reasonable `.gitignore` for Python, virtualenvs, caches, logs,
      credentials, generated reports, local config, and `/opt/parishkit`-style
      runtime artifacts copied into a checkout.
- [x] Create the standard repository layout:
      - `src/parishkit/`
      - `src/parishkit/google/`
      - `src/parishkit/email/`
      - `scripts/`
      - `tests/`
      - `.github/workflows/`
- [x] Add `README.md`, `CLAUDE.md`, and `AGENTS.md` symlinked to
      `CLAUDE.md`.
- [x] Add `pyproject.toml`.
- [x] Add grouped top-level `requirements.txt`.

Success condition: a fresh `parishkit` git checkout exists locally with the
expected top-level files and directories, no credentials or generated runtime
files committed, and `AGENTS.md` resolving to `CLAUDE.md`.

## 2. Development Tooling and CI

- [x] Configure Python 3.12+ project metadata in `pyproject.toml`.
- [x] Configure `ruff` linting.
- [x] Configure `ruff format`.
- [x] Configure `pytest`.
- [x] Add console entry points for all planned tools:
      - `parishkit-run`
      - `parishkit-print-member`
      - `parishkit-print-ministries`
      - `parishkit-calendar-reservations`
      - `parishkit-create-ministry-rosters`
      - `parishkit-sync-google-group`
      - `parishkit-sync-ps-to-cc`
- [x] Add GitHub Actions workflow for `ruff check`.
- [x] Add GitHub Actions workflow step for `ruff format --check`.
- [x] Add GitHub Actions workflow step for `pytest`.
- [x] Add GitHub Actions DCO check for `Signed-off-by:` trailers, using a
      maintained action selected during implementation.
- [x] Document local validation commands in `README.md` and `CLAUDE.md`.
- [x] Document that normal CI must not require real external-service
      credentials.
- [x] Document the pattern for manual, human-run external-service smoke tests
      when real credentials are needed.

Success condition: a developer can install dependencies, run the documented
local validation commands, and see the same lint, format, test, and DCO checks
represented in GitHub Actions. CI does not require real ParishSoft, Google,
Constant Contact, Slack, or email-provider credentials.

## 3. Repository Documentation

- [x] Write top-level `README.md` with project purpose and neutrality goals.
- [x] Document Python 3.12+ requirement.
- [x] Document installation and local development setup.
- [x] Document local lint/style/test commands.
- [x] Document available tools and link to script READMEs.
- [x] Document default runtime paths under `/opt/parishkit`.
- [x] Document secret handling rules.
- [x] Document manual external-service smoke-test conventions:
      - credentials supplied at runtime,
      - read-only checks preferred,
      - dry-run or explicit confirmation for writes,
      - sensitive values redacted from output,
      - smoke tests excluded from normal CI.
- [x] Document ParishSoft API key requirements and sales/API-access note.
- [x] Document fresh Google Cloud / Google Workspace setup:
      - New Google Cloud project per parish.
      - Required APIs.
      - Service accounts.
      - Domain-wide delegation.
      - Workspace Admin scopes.
      - Service account JSON keys.
      - OAuth consent/client setup for workflows that need user OAuth.
      - Credential placement under `/opt/parishkit/credentials/`.
- [x] Write `CLAUDE.md` with general agent/developer conventions for ongoing
      `parishkit` development:
      - Parish-neutral reusable code.
      - Python 3.12+.
      - Executable wrappers require shebangs and executable bits.
      - No ad hoc `sys.path`.
      - No committed secrets.
      - Keep `.gitignore` updated for generated files, credentials, logs,
        caches, virtual environments, and local operational artifacts.
      - YAML config for parish-specific mappings.
      - Shared logging/CLI/retry/auth helpers.
      - `ruff` and `pytest`.
      - Preserve existing tool behavior unless an intentional behavior change
        is requested or documented.
      - DCO `Signed-off-by:` trailers.
      - No LLM attribution requirement.
      - Common Convention commit style.
      - Prefer self-contained commits that leave the repository in a consistent
        state for tools such as `git bisect`.
      - Put drive-by fixes in their own commits.
      - Squash fixup commits before pull requests are merged into their target
        branches.
      - Thorough commit messages explaining why.
      - Commit body wrapping at approximately 75 characters.
      - GitHub issue/PR descriptions use one line per paragraph.

Success condition: a new parish operator and a new developer can read the
top-level docs and understand how to install the project, configure credentials,
run tools, validate changes, and follow repository conventions without relying
on information from the old repository.

## 4. Shared CLI, Config, Logging, and Retry Foundations

- [x] Implement `parishkit.cli` helpers for common arguments:
      - `--config`
      - `--dry-run`
      - `--verbose`
      - `--debug`
      - `--log-file`
      - `--log-dir`
      - `--slack-token-file`
      - `--slack-channel`
      - `--slack-log-level`
      - `--ps-api-key-file`
      - `--ps-cache-dir`
      - `--ps-cache-limit`
- [x] Implement default path constants rooted under `/opt/parishkit`.
- [x] Implement `parishkit.config` YAML loading.
- [x] Implement config validation strategy.
- [x] Implement clear startup errors for invalid config.
- [x] Implement `parishkit.logging`:
      - Console logging.
      - Optional file logging.
      - Rotating logs.
      - Compression for rotated logs.
      - Slack handler.
      - Default Slack threshold of `CRITICAL`.
      - Configurable Slack threshold.
- [x] Implement `parishkit.retry` helpers for retry-safe REST/API calls.
- [x] Document that REST API usage may be modernized during migration when
      current supported APIs or client-library patterns are better than the old
      script patterns.
- [x] Add unit tests for CLI defaults, config loading, logging setup, and retry
      behavior.
- [x] Add a documented manual Slack notification smoke-test tool for a human
      operator to run with a real Slack token.

Success condition: shared CLI/config/logging/retry modules are importable,
covered by focused tests, and usable by a small sample command without each
tool reimplementing common option parsing, logging, YAML loading, or retry
behavior. Real Slack notification validation is available through a documented
human-run smoke test.

## 5. Scheduled Job Runner

- [x] Create `parishkit.runner`.
- [x] Add `parishkit-run` console entry point.
- [x] Create `scripts/run/`.
- [x] Add `scripts/run/parishkit-run.py` executable wrapper.
- [x] Ensure the wrapper starts with `#!/usr/bin/env python3`.
- [x] Ensure the wrapper has its executable bit set.
- [x] Add `scripts/run/README.md`.
- [x] Add `scripts/run/example-config.yaml`.
- [x] Implement lockfile support to prevent concurrent runs.
- [x] Implement stale-lock detection.
- [x] Implement configurable stale-lock behavior:
      - exit and alert,
      - remove stale lock and continue,
      - fail closed.
- [x] Write useful lock metadata, such as host, PID, command, start time, and
      configured timeout.
- [x] Clean up locks on normal exit and handled exceptions.
- [x] Handle termination signals where practical.
- [x] Implement top-level runner logging through `parishkit.logging`.
- [x] Implement top-level Slack reporting through the shared Slack handler.
- [x] Implement watchdog timeout support for child jobs.
- [x] Capture child stdout/stderr for logs and optional Slack reporting.
- [x] Add optional Slack notification on successful runs.
- [x] Add optional contextual Slack comments.
- [x] Define clear cron-friendly exit codes.
- [x] Load runner job lists from YAML.
- [x] Use `/opt/parishkit/config/runner.yaml` or an equivalent documented path
      as the default runner config when `--config` is not supplied.
- [x] Run all configured/enabled jobs when no explicit job selection is
      supplied.
- [x] Support CLI selection of one or more configured jobs to run.
- [x] Support config-file enabled/disabled selection for jobs.
- [x] Support documented override behavior for explicitly running disabled
      jobs, if that behavior is implemented.
- [x] Support simple no-config mode that runs a CLI-supplied command under the
      same lockfile, logging, Slack, and watchdog protections.
- [x] Exit with a clear configuration error when no runner config is available
      and no CLI command is supplied.
- [x] Support per-job working directory.
- [x] Support per-job environment overrides.
- [x] Support per-job timeout.
- [x] Support per-job enabled/disabled flag.
- [x] Support stop-on-first-failure and continue-and-summarize modes.
- [x] Prefer argument-list commands without shell interpolation by default.
- [x] Add an explicit shell mode only if needed and clearly documented.
- [x] Add unit tests for lock acquisition, active-lock exit, stale-lock
      handling, timeout behavior, and exit-code behavior.
- [x] Add mocked tests for Slack failure/success reporting.

Success condition: `parishkit-run` can run a YAML-defined job list, run a
selected subset of jobs, run a single CLI-supplied command without config,
prevent concurrent execution with a lockfile, enforce timeouts, report failures
through logging/Slack, and pass its runner tests.

## 6. Google API Modernization

- [x] Create `parishkit.google.auth`.
- [x] Replace `oauth2client` patterns with `google-auth` and
      `google-auth-oauthlib`.
- [x] Implement service-account credential loading.
- [x] Implement service-account domain-wide delegation helper.
- [x] Implement user OAuth helper for workflows that cannot use service
      accounts.
- [x] Implement Google API service builder helper.
- [x] Implement common Google retry/error handling.
- [x] Review current Google Drive, Calendar, Sheets, Groups, and Admin SDK
      usage and modernize stale API/client-library patterns where appropriate.
- [x] Create initial Google modules as needed:
      - `calendar.py`
      - `drive.py`
      - `groups.py`
      - `sheets.py`
- [x] Add unit tests with mocked Google clients.
- [x] Add a documented manual Google auth/API smoke-test tool if mocked tests
      cannot prove real credential setup works.
- [x] Verify no migrated code imports or depends on `oauth2client`.

Success condition: Google auth/service helpers support service-account DWD and
user OAuth where needed, all tests use mocked Google clients, and a repository
search confirms no migrated code depends on `oauth2client`. Any real-credential
validation needed beyond mocks is available as a documented human-run smoke
test.

## 7. Email Provider System

- [x] Create `parishkit.email.base` provider interface.
- [x] Implement Google Workspace SMTP/XOAUTH2 provider.
- [x] Support service-account domain-wide delegation for Gmail SMTP.
- [x] Support plain text email.
- [x] Support HTML email.
- [x] Support attachments needed by migrated scripts.
- [x] Add MS365 provider stub with documented config shape.
- [x] Add tests for provider selection and message construction.
- [x] Add tests for Google Workspace auth/message flow using mocks.
- [x] Add a documented manual Google Workspace email smoke-test tool for a
      human operator to run with real credentials.

Success condition: tools can select an email provider through shared config,
Google Workspace SMTP/XOAUTH2 message construction is tested with mocks, and
the MS365 placeholder fails clearly with documented configuration expectations.
Real email-provider validation is available through documented human-run smoke
tests where credentials are required.

## 8. ParishSoft Library

- [x] Port useful functionality from `python/ParishSoftv2.py` to
      `parishkit.parishsoft`.
- [x] Do not port `ParishSoftv1.py`.
- [x] Remove Epiphany/ECC-specific defaults.
- [x] Make expected organization validation configurable.
- [x] Review current ParishSoft API usage and modernize stale request,
      pagination, or response-handling patterns where appropriate and
      compatible.
- [x] Preserve JSON caching with configurable cache age.
- [x] Preserve useful data cross-linking behavior.
- [x] Preserve useful family/member/workgroup/ministry helper functions.
- [x] Ensure all ParishSoft REST calls use retry-aware sessions/helpers.
- [x] Keep retry scopes atomic and safe.
- [x] Add unit tests for cache-limit parsing.
- [x] Add unit tests for family/member helper functions.
- [x] Add unit tests for salutation logic.
- [x] Add mocked tests for API paging and retry behavior.
- [x] Add a documented manual ParishSoft connectivity smoke-test tool for a
      human operator to run with a real API key.

Success condition: `parishkit.parishsoft` exposes the migrated v2 data-loading
and helper behavior without Epiphany-specific defaults, uses retry-aware API
access, and has tests for cache parsing, helpers, salutations, paging, and
retry behavior. Real ParishSoft credential validation is available through a
documented human-run smoke test.

## 9. Constant Contact Library

- [x] Port useful functionality from `python/ConstantContact.py` to
      `parishkit.constant_contact`.
- [x] Preserve OAuth token load/save/refresh behavior.
- [x] Preserve paginated API helpers.
- [x] Preserve contact/list linking helpers.
- [x] Preserve ParishSoft contact linking behavior.
- [x] Preserve `CCAPIError` or equivalent typed API exception.
- [x] Review current Constant Contact API usage and modernize stale endpoint,
      token, pagination, or rate-limit patterns where appropriate.
- [x] Ensure all Constant Contact REST calls use retry-aware sessions/helpers.
- [x] Remove Epiphany/ECC-specific defaults.
- [x] Add unit tests for token serialization.
- [x] Add unit tests for API pagination using mocks.
- [x] Add unit tests for contact/list linking.
- [x] Add unit tests for action-support helpers used by sync scripts.
- [x] Add a documented manual Constant Contact token/list smoke-test tool for a
      human operator to run with real credentials.

Success condition: `parishkit.constant_contact` can authenticate, paginate,
link contacts/lists/ParishSoft members, and raise typed API errors through
tested code paths without parish-specific mappings embedded in the module. Real
Constant Contact credential validation is available through a documented
human-run smoke test.

## 10. Script Wrapper Skeletons

- [x] Create `scripts/run/`.
- [x] Create `scripts/print-member/`.
- [x] Create `scripts/print-ministries/`.
- [x] Create `scripts/calendar-reservations/`.
- [x] Create `scripts/create-ministry-rosters/`.
- [x] Create `scripts/sync-google-group/`.
- [x] Create `scripts/sync-ps-to-cc/`.
- [x] Add executable wrapper script in each directory.
- [x] Ensure each wrapper starts with `#!/usr/bin/env python3`.
- [x] Ensure each wrapper has its executable bit set.
- [x] Add `README.md` in each script directory.
- [x] Add `example-config.yaml` in each script directory.

Success condition: every planned command has both a console entry point and an
executable wrapper with a shebang, README, and example config, and each wrapper
delegates to package code instead of containing application logic.

## 11. Migrate `print-member`

- [x] Port `ps-queries/utilities/print-member.py`.
- [x] Remove hard-coded DUIDs.
- [x] Add CLI support for ParishSoft Member DUID lookup.
- [x] Add CLI support for ParishSoft Family DUID lookup.
- [x] Add CLI support for name search.
- [x] Add option controlling whether contributions are loaded.
- [x] Use shared ParishSoft/cache/logging/CLI helpers.
- [x] Add dry-run behavior if any external writes are introduced.
- [x] Add tests for argument parsing and lookup selection.
- [x] Update script README and example config.

Success condition: `parishkit-print-member` can look up members/families by
the supported CLI selectors without hard-coded DUIDs, optionally load
contributions, use shared ParishSoft/logging options, and pass its tests.

## 12. Migrate `print-ministries`

- [x] Port `ps-queries/utilities/print-ministries.py`.
- [x] Use shared ParishSoft/cache/logging/CLI helpers.
- [x] Preserve sorted ministry-name output.
- [x] Add tests for ministry extraction/sorting.
- [x] Update script README and example config.

Success condition: `parishkit-print-ministries` produces the expected sorted
ministry list using shared ParishSoft/logging options and passes tests for the
ministry extraction and sorting behavior.

## 13. Migrate `calendar-reservations`

- [x] Port `media/linux/calendar-reservations/calendar-reservations.py`.
- [x] Move calendar definitions to YAML.
- [x] Move acceptable domains to YAML.
- [x] Use modern Google auth.
- [x] Modernize Google Calendar API usage where current supported patterns are
      better than the old script implementation.
- [x] Use shared Google Calendar helpers.
- [x] Use shared logging, Slack, retry, CLI, and config helpers.
- [x] Preserve dry-run behavior.
- [x] Remove Epiphany-specific defaults from code.
- [x] Add tests for config validation.
- [x] Add tests for conflict-detection logic.
- [x] Add mocked tests for Google Calendar API calls.
- [x] Update script README and example config.

Success condition: `parishkit-calendar-reservations` uses YAML calendars and
domains, modern Google auth, shared logging/Slack/retry behavior, preserves
dry-run behavior, has no Epiphany-specific defaults in code, and passes config,
conflict, and mocked Calendar API tests.

## 14. Migrate `create-ministry-rosters`

- [x] Port `media/linux/ps-queries/create-ministry-rosters.py`.
- [x] Move ministry-to-sheet mappings to YAML.
- [x] Preserve role-sheet behavior.
- [x] Use modern Google auth.
- [x] Modernize Google Sheets/Drive API usage where current supported patterns
      are better than the old script implementation.
- [x] Use shared Google Sheets/Drive helpers.
- [x] Use shared ParishSoft/cache/logging/retry/CLI/config helpers.
- [x] Remove Epiphany-specific defaults from code.
- [x] Add tests for roster config validation.
- [x] Add tests for roster generation logic where practical.
- [x] Add mocked tests for Google Sheets/Drive writes.
- [x] Update script README and example config.

Success condition: `parishkit-create-ministry-rosters` reads ministry roster
mappings from YAML, writes rosters through shared Google helpers, preserves
role-sheet behavior, removes parish-specific code defaults, and passes config,
roster-generation, and mocked Google write tests.

## 15. Migrate `sync-google-group`

- [x] Port `media/linux/ps-queries/sync-google-group.py`.
- [x] Move synchronization mappings to YAML.
- [x] Preserve ministry/workgroup source behavior.
- [x] Preserve Google Group role handling.
- [x] Preserve notification behavior with all addresses configured.
- [x] Use modern Google auth.
- [x] Modernize Google Groups/Admin SDK API usage where current supported
      patterns are better than the old script implementation.
- [x] Use shared Google Groups helper.
- [x] Use shared email provider.
- [x] Use shared ParishSoft/cache/logging/retry/CLI/config helpers.
- [x] Preserve dry-run behavior.
- [x] Remove Epiphany-specific defaults from code.
- [x] Add tests for config validation.
- [x] Add tests for desired-state computation.
- [x] Add tests for add/remove/change-role action computation.
- [x] Add mocked tests for Google Group API calls.
- [x] Update script README and example config.

Success condition: `parishkit-sync-google-group` reads all sync mappings and
notifications from YAML, computes add/remove/role-change actions correctly,
preserves dry-run behavior, uses shared Google/email/ParishSoft/logging
helpers, and passes mocked Google Groups tests.

## 16. Migrate `sync-ps-to-cc`

- [x] Port `media/linux/ps-queries/sync-ps-to-cc.py`.
- [x] Move `cc_sync_config.py` data to YAML.
- [x] Preserve current action-list architecture.
- [x] Preserve unsubscribed-contact filtering.
- [x] Preserve optional name-update behavior.
- [x] Preserve no-sync and dry-run behavior.
- [x] Use shared ParishSoft/cache/logging/retry/CLI/config helpers.
- [x] Use shared Constant Contact library.
- [x] Modernize Constant Contact API usage through the shared library where
      current supported patterns are better than the old script implementation.
- [x] Use shared email provider.
- [x] Remove Epiphany-specific defaults from code.
- [x] Add tests for config validation.
- [x] Add tests for desired-state resolution.
- [x] Add tests for unsubscribed filtering.
- [x] Add tests for create/subscribe/unsubscribe/name-update action
      computation.
- [x] Add mocked tests for Constant Contact writes.
- [x] Update script README and example config.

Success condition: `parishkit-sync-ps-to-cc` reads Constant Contact mappings
from YAML, preserves the action-list architecture and no-sync/dry-run behavior,
correctly handles unsubscribed contacts and optional name updates, and passes
action-computation plus mocked Constant Contact write tests.

## 17. Build Migration Support in the Old Repository

- [x] Create `migrate-to-parishkit/` in this repository.
- [x] Add `migrate-to-parishkit/README.md`.
- [x] Document how to install the new local `parishkit` package.
- [x] Document how to create `/opt/parishkit` directories.
- [x] Document how to create fresh ParishSoft, Google, Constant Contact, and
      Slack credentials as needed.
- [x] Include full fresh Google setup instructions:
      - Create a new Google Cloud project.
      - Enable required APIs.
      - Create service accounts.
      - Enable domain-wide delegation.
      - Configure Workspace Admin client ID/scopes.
      - Create and store service account JSON keys if used.
      - Configure OAuth consent and OAuth clients where needed.
      - Generate user OAuth token files where needed.
      - Store credentials under `/opt/parishkit/credentials/` or configure
        alternate paths.
- [x] Document optional reuse/copying of existing credentials as a migration
      shortcut.
- [x] Convert hard-coded operational data to new-style YAML configs:
      - Calendar reservation calendars/domains.
      - Ministry roster sheet mappings.
      - Google Group sync mappings.
      - Constant Contact sync mappings.
- [x] Store converted migration configs under `migrate-to-parishkit/`.
- [x] Ensure migration configs contain no credentials or secrets.
- [x] Add cron-friendly `run.sh`-style wrappers for migrated jobs.
- [x] Ensure wrappers call the new `parishkit` commands.
- [x] Ensure wrappers use `/opt/parishkit` defaults where appropriate.
- [x] Document which old script each wrapper replaces.
- [x] Document cron changes required by the human operator.

Success condition: the old repository contains `migrate-to-parishkit/` with
operator documentation, converted non-secret YAML configs, and cron-friendly
wrappers that call the new `parishkit` commands with equivalent operational
behavior and clear manual migration steps.

## 18. Final Cleanup and Validation

- [x] Run `ruff check .` in the new repository.
- [x] Run `ruff format --check .` in the new repository.
- [x] Run `pytest` in the new repository.
- [x] Verify all script wrappers have executable bits.
- [x] Verify all script wrappers have `#!/usr/bin/env python3`.
- [x] Verify no migrated code uses `oauth2client`.
- [x] Verify no migrated code uses the `ecc-python-modules` symlink pattern.
- [x] Verify intentionally modernized REST API usage is documented in code,
      tests, README notes, or migration notes where compatibility risk exists.
- [x] Search for old naming and parish-specific defaults:
      - `ECC`
      - `Epiphany`
      - `churchofepiphany`
      - `epiphanycatholicchurch`
      - `Louisville`
      - `ecc-python-modules`
      - `oauth2client`
- [x] Remove, generalize, or explicitly document any remaining occurrences.
- [x] Verify no credentials or secrets are committed.
- [x] Verify CI passes.
- [x] Verify DCO action is configured.
- [x] Verify manual external-service smoke-test tools are documented for any
      integration that cannot be fully validated with mocks.
- [x] Verify migration README and wrappers are present in the old repository.
- [x] Make final signed-off commit(s) using the required commit style.

Success condition: all local validation commands pass, CI/DCO are configured,
the final source searches have no unexplained legacy/parish-specific matches,
no secrets are committed, migration support is present, and the finished work is
captured in signed-off commits with wrapped, explanatory messages. Any
remaining real-credential validation path is documented as a human-run smoke
test and is not required by normal CI.
