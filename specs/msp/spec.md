# MSP Module Specification

**Module**: `python/MSP.py`
**Purpose**: Helper module for applications that interact with the Ministry Scheduler Pro (MSP) REST API v2. Loads, caches, cross-links, and filters MSP data (volunteers, masses, ministries, services). Optionally cross-links MSP volunteers with ParishSoft member/family data.

---

## 1. Overview

MSP.py is a data-access layer that:

1. Wraps the MSP REST API v2 for CRUD-like operations (authenticate, read, create, update, delete)
2. Downloads and caches MSP data as JSON files to avoid redundant API calls
3. Cross-links MSP objects (volunteers, masses, ministries, services) into an interconnected in-memory data model
4. Optionally cross-links MSP volunteers to ParishSoft members and families
5. Filters data based on active status and date ranges
6. Exposes public query functions for ministry membership lookups

**Data ownership**: ParishSoft is the source of truth for member data. All synchronization flows from ParishSoft to MSP — never the reverse. MSP volunteers are created, updated, deactivated, or deleted based on ParishSoft member status.

**Design principle**: MSP.py is strictly a data-access and cross-linking layer. Higher-level business logic — such as determining which MSP volunteers need to be created, deactivated, or reactivated based on ParishSoft member status — belongs in separate Python scripts that use MSP.py.

**API Base URL**: `https://api.ministryschedulerpro.com/2`

**API Documentation**: [MSP REST API v2 Reference](https://docs.google.com/document/u/0/d/e/2PACX-1vRO7Mg0gcBV8Id0X4ecc4vHJHFzV8r9f5o-cprqLHZu7REbKO1YWiUI0wk6Ko_DdbBEGxBeYZ81XCet/pub?pli=1)

---

## 2. Public API

### 2.1 `load_msp_data()`

**Primary entry point.** Downloads all MSP data, cross-links it, optionally links to ParishSoft data, filters it, and returns four dictionaries.

```python
def load_msp_data(
    api_key=None,              # Required. MSP API key (already base64-encoded)
    active_only=True,          # Filter out inactive volunteers/services
    mass_start_date=None,      # Start date for mass loading (default: today)
    mass_end_date=None,        # End date for mass loading (default: 3 months from today)
    ps_members=None,           # Optional ParishSoft members dict (from ParishSoftv2)
    ps_families=None,          # Optional ParishSoft families dict (from ParishSoftv2)
    log=None,                  # Logger instance
    cache_dir="msp-data",      # Directory for cache files
    cache_limit="14m",         # Cache freshness ("14m", "1d", "24s", "7h")
    timezone="America/Kentucky/Louisville",  # IANA timezone for MSP license
) -> tuple:
```

**Returns**: `(volunteers, masses, ministries, services)`

- `volunteers`: `dict[str|int, dict]` keyed by Volunteer ID
- `masses`: `dict[str, dict]` keyed by Mass ID (composite `scheduleId_localMassId`)
- `ministries`: `dict[str|int, dict]` keyed by Ministry ID
- `services`: `dict[str|int, dict]` keyed by Service ID

**Load sequence**:

1. Parse `cache_limit` and set global cache freshness threshold
2. Create `cache_dir` if it doesn't exist
3. Set up HTTP session with Bearer token auth and retry logic (3 retries, 0.2s backoff)
4. Load ministry data
5. Load service data
6. Load volunteer data
7. Load mass data (filtered by date range)
8. Cross-link all data (see Section 5)
9. If ParishSoft data provided, cross-link volunteers to PS members (see Section 6)
10. Filter data per `active_only` (see Section 7)
11. Return the four dictionaries

### 2.2 Volunteer Query Functions

#### `get_ministry_volunteers(ministry, volunteers) -> dict`

Returns a dict of volunteers (keyed by volunteer ID) who are qualified for the given ministry. Includes both standard and substitute volunteers.

#### `get_ministry_subs(ministry, volunteers) -> dict`

Returns a dict of volunteers (keyed by volunteer ID) who are substitutes (`"SUB"`) for the given ministry.

#### `get_ministry_non_subs(ministry, volunteers) -> dict`

Returns a dict of volunteers (keyed by volunteer ID) who are standard members (`"NONE"` or title-qualified) for the given ministry, excluding substitutes.

#### `get_volunteer_ministries(volunteer) -> dict`

Returns a dict of ministries (keyed by ministry ID) that the volunteer is qualified for, with their qualification level (`"NONE"`, `"SUB"`, or title ID).

#### `volunteer_is_active(volunteer) -> bool`

Returns `True` if the volunteer's `inactive` field is `False` (or absent).

#### `volunteer_is_group(volunteer) -> bool`

Returns `True` if the volunteer's `isGroup` field is `True`.

### 2.3 CRUD Functions (Write Operations)

Thin wrappers around the MSP REST API write endpoints. These functions handle authentication, HTTP mechanics, and cache invalidation. They do **not** contain business logic — callers are responsible for deciding what to create, update, or delete.

#### `create_volunteer(api_key, fields, log, cache_dir="msp-data") -> dict`

Creates a new volunteer. `fields` must include at minimum `firstName` and `lastName` (unless `isGroup` is `True`).

- Sends `POST /volunteers` with the provided fields
- Invalidates the volunteer cache on success
- Returns the created volunteer dict from the API response

#### `update_volunteer(api_key, volunteer_id, fields, log, cache_dir="msp-data") -> dict`

Updates a single volunteer. `fields` is a dict of MSP volunteer properties to set.

- Sends `PUT /volunteers/{volunteer_id}` with the provided fields
- Invalidates the volunteer cache on success
- Returns the updated volunteer dict from the API response

#### `delete_volunteer(api_key, volunteer_id, log, cache_dir="msp-data") -> bool`

Deletes a volunteer by ID.

- Sends `DELETE /volunteers/{volunteer_id}`
- Invalidates the volunteer cache on success
- Returns `True` on success, calls `exit(1)` on critical failure

---

## 3. Caching System

### 3.1 Cache Limit

Uses the same humanized time string format as ParishSoftv2:
- `s` = seconds, `m` = minutes, `h` = hours, `d` = days
- Examples: `"24s"`, `"15m"`, `"7h"`, `"2d"`
- Default: `"14m"` (designed for 15-minute cron intervals)

Cache files older than the limit are re-fetched from the API.

### 3.2 Cache Files

Files stored as `cache-msp-{endpoint}.json` (with `/` and `:` replaced by `-`) in `cache_dir` (default: `msp-data`).

- `_save_cache(endpoint, elements, cache_dir, log)`: Writes elements as JSON
- `_load_cache(endpoint, cache_dir, log)`: Returns elements if file exists and is fresh, else `None`

### 3.3 Cache Invalidation

Write operations (create, update, delete) invalidate the relevant cache files by deleting them. This ensures subsequent reads fetch fresh data from the API.

### 3.4 Cache Bypass

When optional `where` clauses are provided to load functions, caching is bypassed entirely — the query is always sent to the API and the response is not cached. This is because filtered queries produce subsets that should not be confused with complete datasets.

---

## 4. API Interaction

### 4.1 Authentication

MSP uses HTTP Bearer token authentication:

```
Authorization: Bearer <api-key>
```

The API key is already base64-encoded as provided by MSP. No additional encoding is needed.

### 4.2 HTTP Session

- Uses `requests.Session` with `Authorization: Bearer <api-key>` header
- Retry policy: 3 retries, 0.2s backoff factor, allowed on POST, GET, PUT, DELETE
- All requests use `Accept: application/json` and `Content-Type: application/json`

### 4.3 Pagination Workaround

The MSP API supports pagination via `limit` and `startAt` parameters. However, there is a known behavior where setting `limit` to an arbitrarily large number (e.g., 1,000,000) returns all records in a single response without requiring pagination. MSP.py uses this approach for simplicity.

This should be documented with inline comments in the code explaining the workaround and why explicit pagination is not used.

### 4.4 Record ID Format

For legacy reasons, MSP uses two ID formats:
- **Integer IDs**: numeric (e.g., `374`)
- **String IDs**: 18-character strings that begin with a lowercase `a` (e.g., `"a5f887a8300aee6006"`). The API documentation describes these as "alphanumeric", but in practice they appear to always be hexadecimal.

Mass IDs are composite: `"{scheduleId}_{localMassId}"`.

Code must handle both integer and string IDs. Dictionary keys should preserve the original type from the API.

### 4.5 Date Format

- Dates: `YYYY-MM-DD`
- Timestamps: `YYYY-MM-DD HH:MM:SS` (in the license's local timezone)
- `dateCreated` and `dateModified` are in UTC

The MSP API returns non-UTC timestamps in the license's local timezone. The `timezone` parameter on `load_msp_data()` specifies the IANA timezone name for interpreting these timestamps. It defaults to `"America/Kentucky/Louisville"` (US Eastern, Louisville). This timezone is used when converting `dateTime` strings to timezone-aware `datetime` objects in cross-linking (e.g., `py datetime` on masses).

### 4.6 Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /volunteers/{id}` | GET | Single volunteer lookup |
| `POST /volunteers/list` | POST | Query/list all volunteers |
| `POST /volunteers` | POST | Create volunteer |
| `PUT /volunteers/{id}` | PUT | Update volunteer |
| `DELETE /volunteers/{id}` | DELETE | Delete volunteer |
| `GET /masses/{id}` | GET | Single mass lookup |
| `POST /masses/list` | POST | Query/list masses |
| `GET /ministries/{id}` | GET | Single ministry lookup |
| `POST /ministries/list` | POST | Query/list all ministries |
| `GET /services/{id}` | GET | Single service lookup |
| `POST /services/list` | POST | Query/list all services |

### 4.7 Query Format

List endpoints (`POST /collection/list`) accept a JSON body with:

```json
{
    "where": { ... },
    "fields": ["field1", "field2"],
    "limit": 1000000,
    "startAt": 0
}
```

- `where`: Optional filter conditions. Supports simple equality and operators like `isGreaterThan`, `isLessThan`.
- `fields`: Optional array of properties to return (ID is always included).
- `limit`: Set to a very large number to retrieve all records (see Section 4.3).
- `startAt`: **Known documentation bug**: the MSP docs describe this as a pagination offset, but it is actually the record ID to start from — not an index. A `startAt` of `0` starts at the first record. If pagination were used, the next page would require `startAt` set to the last record's ID + 1, not the count of records already fetched.

When `where` is not needed, pass `{"limit": 1000000}` to retrieve all records.

---

## 5. Data Cross-Linking

After loading, the following cross-references are created (all prefixed with `py ` to match ParishSoftv2 convention):

### Volunteer enrichments:
- `py ministries`: dict keyed by ministry ID, values are qualification level (`"NONE"`, `"SUB"`, or title ID). Derived from the volunteer's `ministries` field.
- `py ministry_objects`: dict keyed by ministry ID, values are the ministry dict objects
- `py family_members`: list of other volunteer dicts sharing the same `familyId` (empty list if no familyId)
- `py emails`: list of email addresses (split from comma-separated `email` field, lowercased)
- `py cells`: list of cell phone numbers (split from comma-separated `cell` field)
- `py phones`: list of phone numbers (split from comma-separated `phone` field)
- `py scheduled_duties`: the volunteer's `scheduledDuties` field (preserved for convenience)
- `py friendly name FL`: "First Last" using firstName/lastName
- `py friendly name LF`: "Last, First" using firstName/lastName

### Ministry enrichments:
- `py volunteers`: dict keyed by volunteer ID, values are volunteer dict objects (only those present in the loaded volunteers dict)
- `py subs`: dict keyed by volunteer ID, values are volunteer dict objects for substitute-qualified volunteers
- `py services`: dict keyed by service ID, values are service dict objects that require this ministry

### Service enrichments:
- `py ministries`: dict keyed by ministry ID, values are ministry dict objects for ministries required at this service
- `py masses`: list of mass dicts associated with this service (via `serviceId`)

### Mass enrichments:
- `py service`: the service dict object (via `serviceId`), or `None` if one-time mass
- `py positions_enriched`: dict keyed by ministry ID, values are lists of position dicts where each position's `volunteerId` is resolved to the volunteer dict object (as `py volunteer`), and the `ministryId` is resolved to the ministry dict object (as `py ministry`)
- `py date`: `datetime.date` object parsed from the `dateTime` field
- `py datetime`: `datetime.datetime` object parsed from the `dateTime` field

---

## 6. ParishSoft Cross-Linking

When `ps_members` and `ps_families` are provided to `load_msp_data()`, MSP volunteers are linked to ParishSoft members using a two-tier matching strategy. Since ParishSoft is the source of truth, this linkage enables downstream scripts to synchronize member data from ParishSoft into MSP.

### 6.1 Matching Strategy

1. **Primary match**: MSP volunteer `externalId` == ParishSoft Member DUID (converted to string for comparison)
2. **Fallback match**: MSP volunteer `firstName`+`lastName` == ParishSoft member `firstName`+`lastName` (case-insensitive). Only used when `externalId` is not set or does not match any PS member.

### 6.2 Volunteer Enrichments (when PS data is linked)

- `py ps_member`: the ParishSoft member dict, or `None` if unlinked
- `py ps_family`: the ParishSoft family dict (via the member's `py family` field), or `None` if unlinked
- `py ps_member_duid`: the ParishSoft Member DUID, or `None` if unlinked

### 6.3 PS Member Enrichments

When cross-linking succeeds, the ParishSoft member dict also receives:
- `py msp_volunteer`: the MSP volunteer dict, or `None` if no match

### 6.4 Unlinked Volunteers

Volunteers without a ParishSoft match have `py ps_member`, `py ps_family`, and `py ps_member_duid` set to `None`. The load function logs a warning for each unlinked volunteer to aid in data reconciliation.

---

## 7. Filtering

Filtering happens after all cross-linking is complete.

### Volunteer filtering:
- `active_only=True`: removes volunteers where `volunteer_is_active()` returns `False` (i.e., `inactive` is `True`)

### Service filtering:
- `active_only=True`: removes services where `inactive` is `True`

### Mass filtering:
- Masses are filtered by date range during loading (via `where` clause on the API query)
- `mass_start_date`: defaults to today
- `mass_end_date`: defaults to 3 months from today
- Only masses with `dateTime` within this range are loaded

### Cascade effects:
When a volunteer is removed:
- Removed from all ministry `py volunteers` and `py subs` dicts
- Removed from family cross-references (`py family_members` lists of other volunteers)

When a service is removed:
- Removed from ministry `py services` dicts
- Associated masses that reference this service are NOT removed (they may still be relevant as one-time overrides)

---

## 8. Email & Phone Normalization

All email addresses are normalized to lowercase. Comma-separated multi-value fields are split into Python lists:

- Volunteer `email` → `py emails` (list of strings, lowercased)
- Volunteer `cell` → `py cells` (list of strings)
- Volunteer `phone` → `py phones` (list of strings)

Empty or null source fields result in empty lists (not `None`), ensuring callers can always iterate without null checks.

---

## 9. MSP Family Cross-Linking

Volunteers sharing the same `familyId` are grouped together:

- Each volunteer receives a `py family_members` list containing the other volunteer dicts in the same family (excluding self)
- Volunteers with `familyId` of `None` or missing get an empty `py family_members` list
- Family binding flags (`bindPhoneAndAddress`, `bindEmail`, `bindServicePreferences`) are preserved on the volunteer dict but not acted upon by MSP.py

---

## 10. Error Handling

- Critical failures (authentication errors, malformed API responses) call `exit(1)` with a log message, matching ParishSoftv2's pattern
- HTTP 400 errors on write operations log the error and return `None`
- HTTP 401 errors call `exit(1)` — indicates invalid API key
- HTTP 500 errors are retried via the session retry policy; if all retries fail, `exit(1)` is called

---

## 11. Dependencies

- `requests` + `urllib3` — HTTP client with retry logic
- `ECC` — imported for logging setup (used by callers)
- Standard library: `os`, `re`, `sys`, `json`, `time`, `datetime`

---

## 12. MSP API Data Model Reference

### 12.1 Volunteer Properties (from API)

| Property | Type | Notes |
|----------|------|-------|
| `id` | string/int | Read-only |
| `firstName` | string | Required |
| `lastName` | string | Required unless `isGroup=True` |
| `title` | string | Optional (e.g., "Sr.") |
| `isGroup` | boolean | Group volunteers fill multiple positions |
| `contactName` | string | For group volunteers only |
| `familyId` | string/null | Family association |
| `email` | string | Comma-separated addresses |
| `emailUnlisted` | boolean | |
| `cell` | string | Comma-separated mobile numbers |
| `cellUnlisted` | boolean | |
| `phone` | string | Land-line numbers |
| `phoneUnlisted` | boolean | |
| `address` | string | Newline-separated mailing address |
| `ministries` | hash | Ministry ID → qualification (`"NONE"`, `"SUB"`, or title ID) |
| `servicePreferences` | array | Ordered preference objects |
| `cantServeTimes` | array | Unavailability blocks |
| `inactive` | boolean | Prevents scheduling |
| `substitute` | boolean | Read-only. True if SUB in all ministries |
| `preassignmentsOnly` | boolean | Manual/preassigned only |
| `scheduledDuties` | hash | By schedule ID, arrays of assignment records |
| `externalId` | string | External system identifier (used for PS linkage) |
| `dateCreated` | string | UTC timestamp (read-only) |
| `dateModified` | string | UTC timestamp (read-only) |
| `comments` | string | Free-form reference text |
| `customFieldValues` | hash | Custom field ID → value |

### 12.2 Mass Properties (from API)

| Property | Type | Notes |
|----------|------|-------|
| `id` | string | Composite: `scheduleId_localMassId` (read-only) |
| `description` | string | Optional |
| `serviceId` | string/null | Parent service, null if one-time |
| `dateTime` | string | Local timezone `YYYY-MM-DD HH:MM:SS` |
| `positions` | hash | Ministry ID → array of position assignments |
| `titleRules` | array | Title requirements per ministry |
| `openMinistries` | hash | Read-only: open positions per ministry |
| `kioskCheckins` | array | Check-in records |
| `kioskState` | string | Read-only: `inactive|active|reconciled` |
| `dontAutoSchedule` | boolean | |
| `overload` | boolean | |
| `choirs` | array | Choir ministry IDs |

### 12.3 Ministry Properties (from API)

| Property | Type | Notes |
|----------|------|-------|
| `id` | string/int | Read-only |
| `name` | string | Read-only |
| `description` | string | Optional |
| `order` | int | Read-only global position |
| `volunteers` | hash | Volunteer ID → qualification |
| `ministryGroupId` | string | Parent group ID |
| `numberAssignments` | boolean | Enable position numbering |
| `assignmentNumberLabels` | array | Custom position labels |
| `neverSplitFamilies` | boolean | |
| `blockSchedulingPattern` | string/null | `oneWeek|twoWeek|oneMonth` |
| `scheduleAutonomously` | boolean | |
| `choir` | boolean | |
| `compatibleMinistries` | hash | Ministry ID → combination rule |
| `rosterCode` | string | Short-hand identifier |
| `autoQualifyNewVolunteers` | boolean | |

### 12.4 Service Properties (from API)

| Property | Type | Notes |
|----------|------|-------|
| `id` | string/int | Read-only |
| `name` | string | |
| `label` | string | Read-only calculated display label |
| `description` | string | Optional location/details |
| `type` | string | `Weekly|Monthly|Yearly` |
| `inactive` | boolean | |
| `requiredMinistries` | hash | Ministry ID → position count |
| `timeOffset` | hash | Recurrence pattern definition |
| `titleRules` | array | Title requirements |
| `choirs` | array | Choir ministry IDs |

---

## 13. Reconciliation Summary

**Created**: 2026-03-01
**API docs cross-referenced**: 2026-03-01 (MSP REST API v2 reference)

This document was created based on requirements gathering with the project owner and cross-referencing the MSP REST API v2 documentation. The specification follows the same structural conventions as the ParishSoftv2 module specification.
