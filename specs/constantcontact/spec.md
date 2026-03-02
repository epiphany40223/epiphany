# ConstantContact Module Specification

**Module**: `python/ConstantContact.py`
**Purpose**: Helper module for applications that interact with the Constant Contact V3 REST API. Provides OAuth2 authentication (device flow), generic API operations (GET/PUT/POST), contact management, and cross-linking of Constant Contact data with ParishSoft member data.

---

## 1. Overview

ConstantContact is a data-access and synchronization layer that:

1. Authenticates with the Constant Contact V3 API using OAuth2 device flow
2. Manages access token lifecycle (obtain, persist, refresh, re-authorize)
3. Provides generic paginated GET and PUT/POST API helpers
4. Creates and updates contacts at Constant Contact
5. Cross-links CC contacts, custom fields, and lists into an interconnected in-memory data model
6. Links CC contacts to ParishSoft members by email address

**API Base URL**: Configurable via `client_id['endpoints']['api']`, typically `https://api.cc.email`
**Auth Endpoints**: Configurable via `client_id['endpoints']['auth']` and `client_id['endpoints']['token']`

---

## 2. Public API

### 2.1 Authentication

#### `load_client_id(filename, log) -> dict`

Loads the CC client ID configuration from a JSON file. The file contains:

```json
{
    "client id": "<client_id_string>",
    "client secret": "<client_secret_string>",
    "endpoints": {
        "api": "https://api.cc.email",
        "auth": "https://authz.constantcontact.com/oauth2/default/v1/device/authorize",
        "token": "https://authz.constantcontact.com/oauth2/default/v1/token"
    }
}
```

**Note**: The `client secret` is present in the file but is not currently used by the code (the device flow does not require it).

#### `get_access_token(access_token_filename, client_id, log) -> dict`

**Primary authentication entry point.** Loads or obtains a valid CC OAuth2 access token.

**Logic**:
1. If `access_token_filename` does not exist: run device flow, save token
2. If file exists: load token from file
3. If token is not yet valid (`valid from > now`): error and exit
4. If token is expired (`now > valid to`): attempt refresh; if refresh fails, run device flow again

Returns an access token dict containing `access_token`, `refresh_token`, `expires_in`, `valid from`, `valid to`.

#### `oauth2_device_flow(client_id, log) -> dict`

Implements the CC OAuth2 Device Flow:

1. POSTs to the auth endpoint with `client_id`, `response type: "code"`, `scope: "contact_data offline_access"`, and a random `state` value
2. Displays a verification URL for the user to visit in a browser
3. Waits for user confirmation (interactive `input()` prompt)
4. POSTs to the token endpoint with `client_id`, `device_code`, and `grant_type: "urn:ietf:params:oauth:grant-type:device_code"`
5. Returns the token response with `valid from` and `valid to` added

#### `oauth2_device_flow_refresh(client_id, access_token, log) -> dict | None`

Refreshes an expired access token:

1. POSTs to the token endpoint with `client_id`, `refresh_token`, and `grant_type: "refresh_token"`
2. Returns `None` on error (logs the error)

**Discrepancy**: The CC API docs state that refresh requires a `Base64(client_id:client_secret)` Authorization header. The code passes `client_id` as a POST body parameter and does not include a client secret. This works in practice, likely because the device flow does not require a client secret (unlike the Authorization Code flow).

#### `save_access_token(filename, access_token, log)`

Serializes the access token to a JSON file. Converts `datetime.datetime` objects (`valid from`, `valid to`) to ISO format strings for JSON compatibility.

#### `load_access_token(filename, log) -> dict`

Loads an access token from a JSON file. Converts ISO format strings back to `datetime.datetime` objects.

#### `set_valid_from_to(start, response)`

Adds `valid from` (a `datetime.datetime`) and `valid to` (computed as `start + expires_in seconds`) to a token response dict.

### 2.2 Generic API Operations

#### `CCAPIError` (Exception Class)

Custom exception raised by API functions on non-2xx HTTP responses (after retry exhaustion).

**Attributes**:
- `status_code`: The HTTP status code
- `response_text`: The response body text
- `endpoint`: The API endpoint that failed

Consumers should catch this exception to handle individual API failures gracefully (e.g., log and continue processing remaining contacts).

#### `api_headers(client_id, access_token, include=None, limit=None, status=None) -> tuple[dict, dict]`

Builds HTTP headers and query parameters for CC API calls.

**Headers**: `Authorization: Bearer {access_token}`, `Cache-Control: no-cache`
**Params**: Optional `include`, `limit`, `status` query parameters.

#### `api_get_all(client_id, access_token, api_endpoint, json_response_field, log, include=None, status=None) -> list`

Fetches all items from a paginated CC V3 endpoint.

**Pagination**: Uses `_links.next.href` from each response to follow pages. Requests `limit=500` (the CC maximum). Stops when no `_links.next` is present.

**Parameters**:
- `api_endpoint`: Path relative to `/v3/` (e.g., `"contacts"`, `"contact_lists"`, `"contact_custom_fields"`)
- `json_response_field`: Key in the JSON response containing the data array (e.g., `"contacts"`, `"lists"`, `"custom_fields"`)
- `include`: Comma-separated subresources (e.g., `"custom_fields,list_memberships,street_addresses"`)
- `status`: Contact status filter (e.g., `"all"` to include deleted/unsubscribed)

**Error handling**: Raises `CCAPIError` on non-2xx responses after retry exhaustion.

#### `api_put(client_id, access_token, api_endpoint, body, log) -> dict`

PUTs a JSON body to a CC V3 endpoint. Used for updating existing contacts.

**Error handling**: Raises `CCAPIError` on non-2xx responses after retry exhaustion.

#### `api_post(client_id, access_token, api_endpoint, body, log) -> dict`

POSTs a JSON body to a CC V3 endpoint. Used for creating/updating contacts via sign-up form.

**Error handling**: Raises `CCAPIError` on non-2xx responses after retry exhaustion.

### 2.3 Contact Management

#### `update_contact_full(contact, client_id, access_token, log)`

Updates an existing CC contact using the PUT endpoint (`/v3/contacts/{contact_id}`).

**Use case**: Unsubscribing contacts from lists. The sign-up form POST endpoint can only *add* list memberships; this PUT endpoint can *remove* them.

**Design note**: The existence of two separate functions for writing contacts (`update_contact_full` and `create_or_update_contact`) is a workaround for the CC API's split behavior. A future consolidation into a single function is intended.

**Request body** includes `update_source: "Contact"` and copies these fields from the contact if present: `first_name`, `last_name`, `email_address` (full object), `job_title`, `company_name`, `birthday_month`, `birthday_day`, `anniversary`, `street_addresses`, `list_memberships`.

**Known workaround**: Strips periods from `first_name` because CC rejects names containing periods (e.g., `"T.J."` becomes `"TJ"`).

#### `create_or_update_contact(contact, client_id, access_token, log)`

Creates a new contact or updates an existing one via the sign-up form endpoint (`/v3/contacts/sign_up_form`).

**Use case**: Adding new contacts or adding contacts to lists. Cannot unsubscribe from lists.

**Key difference from `update_contact_full`**: Uses `email_address` as a simple string (`contact['email_address']['address']`) rather than the full email address object.

**Request body** includes the email string and copies these fields from the contact if present: `first_name`, `last_name`, `job_title`, `company_name`, `birthday_month`, `birthday_day`, `anniversary`, `street_addresses`, `list_memberships`.

**Known workaround**: Same period-stripping for `first_name`.

#### `create_contact_dict(email, ps_members, log) -> dict`

Creates a CC contact data structure in local memory (does not make any API call).

**Returns** a dict with:
- `email_address`: `{'address': email.lower()}`
- `first_name`, `last_name`: Computed from ParishSoft members via `ParishSoft.salutation_for_members()`
- `list_memberships`: Empty list (to be populated later)
- `LIST MEMBERSHIPS`: Empty list (human-readable names, populated during linking)
- `PS MEMBERS`: Reference to the ParishSoft member list

Also sets `member['CONTACT'] = contact` on each PS member, creating a back-reference.

### 2.4 Data Linking

#### `link_cc_data(contacts, custom_fields_arg, lists_arg, log)`

Cross-references CC contacts with custom fields and lists. Creates enriched data structures for human-readable access.

**Custom field linking**:
- Builds a lookup dict of custom fields by `custom_field_id`
- For each contact, resolves custom field UUIDs to names
- Stores in `contact['CUSTOM FIELDS']` (dict keyed by field name)

**List linking**:
- Builds a lookup dict of lists by `list_id`
- For each contact, resolves list membership UUIDs to names
- Stores human-readable names in `contact['LIST MEMBERSHIPS']` (list of strings)
- Builds reverse index: `list['CONTACTS'][email] = contact`

#### `link_contacts_to_ps_members(contacts, ps_members, log)`

Cross-references CC contacts with ParishSoft members by email address.

1. Builds a lookup of PS members by their first email address (`py emailAddresses[0]`)
2. For each CC contact, if the email matches a PS member:
   - Sets `contact['PS MEMBERS']` = list of matching PS members
   - Sets `member['CONTACT']` = back-reference to the CC contact

### 2.5 Function Classification

Verified against the sole consumer (`sync-constant-contact.py`):

**Consumer-facing** (called directly by consumer):

| Function | Consumer Lines |
|---|---|
| `load_client_id()` | 1015 |
| `get_access_token()` | 1016 |
| `api_get_all()` | 1024, 1031, 1038 |
| `create_contact_dict()` | 591 |
| `create_or_update_contact()` | 741 |
| `update_contact_full()` | 759 |
| `link_cc_data()` | 1065 |
| `link_contacts_to_ps_members()` | 1078 |

**Internal** (used within the module's call chain, not called by consumer):

| Function | Called By |
|---|---|
| `api_headers()` | `api_get_all`, `_api_put_or_post` |
| `_api_put_or_post()` | `api_put`, `api_post` |
| `api_put()` | `update_contact_full` |
| `api_post()` | `create_or_update_contact` |
| `set_valid_from_to()` | `oauth2_device_flow`, `oauth2_device_flow_refresh` |
| `oauth2_device_flow()` | `get_access_token` |
| `oauth2_device_flow_refresh()` | `get_access_token` |
| `save_access_token()` | `get_access_token` |
| `load_access_token()` | `get_access_token` |

---

## 3. Data Model

### 3.1 Client ID Structure

```json
{
    "client id": "string",
    "client secret": "string",
    "endpoints": {
        "api": "https://api.cc.email",
        "auth": "https://authz.constantcontact.com/oauth2/default/v1/device/authorize",
        "token": "https://authz.constantcontact.com/oauth2/default/v1/token"
    }
}
```

**Note**: `client secret` is stored in the file but not used by the code (device flow clients are public).

### 3.2 Access Token Structure

```json
{
    "access_token": "JWT string (1000-1200 chars)",
    "refresh_token": "string (42 chars)",
    "expires_in": 28800,
    "token_type": "Bearer",
    "scope": "contact_data offline_access",
    "valid from": "datetime.datetime (ISO string when persisted)",
    "valid to": "datetime.datetime (ISO string when persisted)"
}
```

### 3.3 Contact Enrichments

After `link_cc_data` and `link_contacts_to_ps_members`:

| Key | Type | Source |
|-----|------|--------|
| `CUSTOM FIELDS` | `dict[str, dict]` | Keyed by custom field name |
| `LIST MEMBERSHIPS` | `list[str]` | Human-readable list names |
| `PS MEMBERS` | `list[dict]` | ParishSoft member objects |

### 3.4 List Enrichments

After `link_cc_data`:

| Key | Type | Source |
|-----|------|--------|
| `CONTACTS` | `dict[str, dict]` | Keyed by email address, values are contact objects |

---

## 4. Cross-Reference with CC V3 API Documentation

**Source**: https://developer.constantcontact.com/api_guide/index.html

### 4.1 Endpoints Used

| Code Function | CC V3 Endpoint | Method | Purpose |
|---|---|---|---|
| `api_get_all` | `/v3/contacts` | GET | Download all contacts with pagination |
| `api_get_all` | `/v3/contact_lists` | GET | Download all contact lists |
| `api_get_all` | `/v3/contact_custom_fields` | GET | Download all custom fields |
| `api_put` (via `update_contact_full`) | `/v3/contacts/{contact_id}` | PUT | Update existing contact (incl. list unsubscribe) |
| `api_post` (via `create_or_update_contact`) | `/v3/contacts/sign_up_form` | POST | Create or update contact (subscribe only) |

### 4.2 Endpoint Details: Code vs API Documentation

| Aspect | Code Behavior | API Documentation | Discrepancies |
|---|---|---|---|
| **GET pagination** | Follows `_links.next.href`, `limit=500` | Pagination via `_links.next.href`, max `limit=500` | Matches |
| **GET contacts params** | Uses `include`, `status`, `limit` | Supports `include`, `status`, `limit`, plus `email`, `lists`, `segment_id`, `tags`, `updated_after`, `created_after` | Code doesn't use all available filters — this is fine for bulk download use case |
| **PUT contacts** | Sends `update_source: "Contact"` | Requires `update_source` field | Matches. API docs say `"Account"` or `"Contact"` |
| **PUT email_address** | Passes full `email_address` object from contact | Expects object with `address` and optional `permission_to_send` | Matches |
| **POST sign_up_form** | Sends `email_address` as plain string | Expects `email_address` as string (max 50 chars) | Matches |
| **POST sign_up_form** | Sends `list_memberships` array | Requires at least 1 list, max 50 | Code may send empty `list_memberships` for newly created contacts before lists are assigned — this could fail at the CC API |
| **OAuth2 device flow** | Sends `response type: "code"` | API docs show `client_id` and `scope` as required | Minor: code sends extra `response type` and `state` params — likely ignored by server |
| **OAuth2 refresh** | POSTs `client_id` + `refresh_token` + `grant_type` as form data | Docs say to use `Authorization: Basic Base64(client_id:client_secret)` header | Code omits client secret; works because device flow clients are public (no secret required) |
| **Token validity** | Uses `datetime.datetime.now(datetime.timezone.utc)` for comparison | Tokens valid for 1440 min (24h) per docs; `expires_in` in response | Matches |

### 4.3 API Features NOT Used by Code

| CC V3 Feature | Endpoint | Notes |
|---|---|---|
| Delete contact | `DELETE /v3/contacts/{contact_id}` | Consumer has placeholder code for deletion but it's not yet implemented |
| Bulk import contacts | `POST /v3/activities/contacts_file_import` | Code creates/updates contacts one at a time |
| Bulk delete contacts | `POST /v3/activities/contact_delete` | Not used |
| Bulk list add/remove | `POST /v3/activities/add_list_memberships`, `POST /v3/activities/remove_list_memberships` | Code modifies lists via individual contact updates |
| Contact tags | `/v3/contact_tags` | Not used |
| Segments | `/v3/segments` | Not used |
| Email campaigns | `/v3/emails` | Not used (out of scope for sync module) |
| Contact consent counts | `GET /v3/contacts/counts` | Not used |

### 4.4 Rate Limits

The CC V3 API enforces:
- **4 requests per second** per API key
- **10,000 requests per day** per API key (resets at UTC 00:00:00)
- HTTP 429 "Too Many Requests" when exceeded

See Section 6.2 for rate limit handling.

---

## 5. Authentication Flow

The module uses the CC OAuth2 **Device Flow** (flow #3 of 4 available):

```
1. POST to auth endpoint → receive device_code + verification URL
2. User visits URL in browser, authenticates, grants permission
3. User confirms in terminal (interactive prompt)
4. POST to token endpoint with device_code → receive access_token + refresh_token
5. Save token to JSON file for reuse
```

**Token lifecycle**:
- Access tokens expire after ~24 hours (`expires_in` from API, typically 1440 minutes)
- Refresh tokens expire after 180 days if unused
- On expiry: attempt refresh → if that fails, re-run device flow (requires user interaction)

**Scopes requested**: `contact_data` (read/write contacts) and `offline_access` (enables refresh tokens)

---

## 6. Error Handling

All API operations (`api_get_all`, `api_put`, `api_post`) raise `CCAPIError` on non-2xx HTTP responses after retry exhaustion. Consumers are responsible for catching these exceptions and deciding how to handle them (e.g., abort, log and continue, etc.).

### 6.1 Retry Logic

API calls use `requests.Session` with an `HTTPAdapter` configured with `urllib3.util.Retry`:
- **Retries**: 3
- **Backoff factor**: 0.2 seconds
- **Retry on**: Connection errors, transient HTTP errors, and 429 (Too Many Requests) responses

This matches the retry strategy used by `ParishSoftv2.py`.

### 6.2 Rate Limit Handling

The CC V3 API enforces 4 requests/second and 10,000 requests/day (see Section 4.4). The module handles rate limiting reactively:

- HTTP 429 responses are retried automatically by the retry adapter
- The `Retry-After` header from 429 responses is respected for backoff timing
- There is no proactive request throttling; rate limiting is purely reactive

Note: For the current cron-based use case (running every 15 minutes with a moderate number of contacts), proactive throttling is not necessary.

---

## 7. Dependencies

- `requests` — HTTP client with `HTTPAdapter` configured with `urllib3.util.Retry` for automatic retry/backoff
- `urllib3` — Provides `Retry` and backoff functionality (included as a dependency of `requests`)
- `ParishSoftv2` (imported as `ParishSoft`) — used only for `salutation_for_members()` in `create_contact_dict()`
- Standard library: `os`, `json`, `copy`, `random`, `datetime`
- `pprint` — for debug logging


---

## 8. Consumer Usage Patterns

### 8.1 sync-constant-contact.py (legacy)

The original consumer script. See its source for details.

### 8.2 sync-ps-to-cc.py

The replacement consumer script (see `specs/sync-ps-to-cc/spec.md`). Usage pattern:

1. **Authenticates**: `load_client_id()` + `get_access_token()`
2. **Downloads CC data**: Two `api_get_all()` calls for lists and contacts (no custom fields)
3. **Links CC data**: `link_cc_data()` with empty custom fields to cross-reference contacts/lists
4. **Links to ParishSoft**: `link_contacts_to_ps_members()` to match by email
5. **Computes sync actions**: Determines which contacts need creating, subscribing, or unsubscribing
6. **Creates missing contacts**: `create_contact_dict()` for contacts that exist in PS but not CC
7. **Executes changes** (catching `CCAPIError` per-contact to log and continue):
   - `create_or_update_contact()` for new contacts and list subscriptions
   - `update_contact_full()` for list unsubscriptions and name updates

---

## 9. Pending Code Cleanup

The following item should be addressed:

1. **Consolidate `update_contact_full` and `create_or_update_contact`** — currently two separate functions as a workaround for CC API behavior; intended to be merged into a single function

---

## 10. Reconciliation Summary

**Reconciled**: 2026-03-01
**Updated**: 2026-03-01 (planned changes for retry logic, rate limiting, exception-based error handling)
**API docs cross-referenced**: 2026-03-01 (CC V3 API guide at developer.constantcontact.com)

This document was originally created to reflect the actual implementation of `python/ConstantContact.py`.
The specification was derived from reading the source code, analyzing usage by its consumer scripts, and cross-referencing against the Constant Contact V3 API documentation.

Sections 2.2, 6, and 7 were updated on 2026-03-01 to specify planned changes:
- `CCAPIError` exception class (replacing `exit(1)` calls)
- Retry logic via `urllib3.util.Retry`
- Reactive rate limit handling (429 + Retry-After)
- Updated consumer usage patterns for `sync-ps-to-cc.py`

These changes have not yet been implemented in code.
