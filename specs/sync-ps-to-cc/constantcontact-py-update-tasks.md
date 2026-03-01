# ConstantContact.py Update Tasks

Tasks to update `python/ConstantContact.py` to match the planned changes
in `specs/constantcontact/spec.md` (sections 2.2, 6, 7, 10).

## Phase 1: Foundation

These must be completed first; all other tasks depend on them.

- [x] **1.1 Add imports for retry/adapter**
  Add `from urllib3.util.retry import Retry` and
  `from requests.adapters import HTTPAdapter` to the imports section
  (after `import requests`).

- [x] **1.2 Define CCAPIError exception class**
  Add a `CCAPIError` exception class after the imports (before the
  first `####` section divider). Per the spec (Section 2.2):
  - Attributes: `status_code` (int), `response_text` (str),
    `endpoint` (str)
  - Inherits from `Exception`
  - `__str__` should include the endpoint and status code for
    readable error messages

## Phase 2: Retry and Rate Limit Infrastructure

Depends on: Phase 1

- [x] **2.1 Create a module-level session factory**
  Add a helper function (e.g., `_create_session()`) that creates a
  `requests.Session` with an `HTTPAdapter` configured with
  `urllib3.util.Retry`:
  - `total=3` retries
  - `backoff_factor=0.2`
  - `status_forcelist=[429]` (retry on rate limit)
  - `respect_retry_after_header=True` (honor Retry-After from 429s)
  - Mount the adapter on both `https://` and `http://`
  - Return the configured session

  This avoids duplicating session setup in every API function.
  The `allowed_methods` parameter should be set by the caller or
  default to `["GET", "PUT", "POST"]`.

## Phase 3: Update API Functions

Depends on: Phase 2

- [x] **3.1 Update `api_get_all()` to use session and raise CCAPIError**
  - Replace `requests.get(url, ...)` with `session.get(url, ...)`
    using a session from `_create_session()`
  - Replace `exit(1)` (lines 56-58) with
    `raise CCAPIError(r.status_code, r.text, api_endpoint)`
  - Remove the `# JMS Need to surround this in a retry` comment
    (the retry is now implemented)

- [x] **3.2 Update `_api_put_or_post()` to use session and raise CCAPIError**
  - The current design passes `requests.put` or `requests.post` as
    `action_fn`. This won't work with a session object. Refactor to
    use `action_name` (the string "PUT" or "POST") to select
    `session.put` or `session.post` instead of accepting a function
    reference.
  - Replace `exit(1)` (lines 87-90) with
    `raise CCAPIError(r.status_code, r.text, api_endpoint)`
  - Update callers `api_put()` and `api_post()` accordingly (they
    currently pass `requests.put`/`requests.post` as the first arg).

## Phase 4: Backward Compatibility

Depends on: Phase 3

- [x] **4.1 Update `sync-constant-contact.py` for CCAPIError**
  Add `try`/`except CCAPIError` around all CC API calls in
  `media/linux/ps-queries/sync-constant-contact.py` to preserve its
  current behavior:
  - `CC.api_get_all()` calls (lines 1024, 1031, 1038): catch
    `CCAPIError`, log the error, and `exit(1)` — same as the old
    behavior.
  - `CC.create_or_update_contact()` (line 741): catch, log, exit(1).
  - `CC.update_contact_full()` (line 759): catch, log, exit(1).
  - Import `CCAPIError` from `ConstantContact` at the top of the
    script (e.g., `from ConstantContact import CCAPIError`).

## Phase 5: Verification

Depends on: Phase 4

- [x] **5.1 Verify no remaining `exit(1)` in API functions**
  Confirm that `api_get_all`, `_api_put_or_post`, `api_put`, and
  `api_post` no longer call `exit(1)`. The only `exit(1)` calls
  remaining in ConstantContact.py should be in `get_access_token()`
  (for authentication failures, which are not API operation errors).

- [x] **5.2 Verify old script still functions**
  Confirm that `sync-constant-contact.py` handles `CCAPIError` in
  all code paths that previously relied on `exit(1)`.

## Notes

- The `get_access_token()` function has two `exit(1)` calls (lines
  291-294, 301-304) for authentication failures. These are NOT
  changed because they are not API operation errors — they indicate
  the script cannot proceed at all (no token, or token not yet valid).
  The spec says "error and exit" for these cases.

- The `oauth2_device_flow_refresh()` function already returns `None`
  on error instead of calling `exit(1)`, so no change is needed there.

- The session/retry changes do not alter function signatures or return
  types, so they are backward-compatible. Only the error handling
  change (exit → exception) affects callers.
