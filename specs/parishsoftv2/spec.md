# ParishSoftv2 Module Specification

**Module**: `python/ParishSoftv2.py`
**Purpose**: Helper module for applications that interact with the ParishSoft Family Suite v2 cloud API. Loads, caches, cross-links, and filters parish data (families, members, workgroups, ministries, contributions).

---

## 1. Overview

ParishSoftv2 is a data-access layer that:

1. Authenticates with the ParishSoft v2 REST API using an API key
2. Downloads parish data via paginated GET/POST endpoints
3. Caches responses as JSON files to avoid redundant API calls
4. Cross-links families, members, workgroups, ministries, and contributions into an interconnected in-memory data model
5. Filters the data based on active status, parishioner status, and deceased status
6. Exposes public query functions for common operations (email lookup, phone lookup, salutations, etc.)

**API Base URL**: `https://ps-fs-external-api-prod.azurewebsites.net/api/v2`

---

## 2. Public API

### 2.1 `load_families_and_members()`

**Primary entry point.** Downloads all parish data, cross-links it, filters it, and returns five dictionaries.

```python
def load_families_and_members(
    api_key=None,              # Required. ParishSoft API key
    active_only=True,          # Filter out inactive families/members
    parishioners_only=True,    # Filter to registered org members only
    load_contributions=False,  # False, True (last year), or date string
    include_deceased=False,    # Include deceased members
    log=None,                  # Logger instance
    cache_dir="ps-data",       # Directory for cache files
    expected_org='Epiphany Catholic Church',  # Org name sanity check
    cache_limit="14m",         # Cache freshness ("14m", "1d", "24s", "7h")
) -> tuple:
```

**Returns**: `(families, members, family_workgroup_memberships, member_workgroup_memberships, ministry_type_memberships)`

- `families`: `dict[int, dict]` keyed by Family DUID
- `members`: `dict[int, dict]` keyed by Member DUID
- `family_workgroup_memberships`: `dict[int, dict]` keyed by Family Workgroup DUID
- `member_workgroup_memberships`: `dict[int, dict]` keyed by Member Workgroup DUID
- `ministry_type_memberships`: `dict[int, dict]` keyed by Ministry Type ID

**Load sequence**:

1. Parse `cache_limit` and set global cache freshness threshold
2. Create `cache_dir` if it doesn't exist
3. Set up HTTP session with API key header and retry logic (3 retries, 0.2s backoff)
4. Verify organization (POST `organizations/search`, expect exactly one matching `expected_org`)
5. Optionally load financial data: funds, pledges, contributions
6. Load family data: families, family groups, family workgroups + memberships
7. Load member data: members, statuses, types, contact info, workgroups + memberships
8. Load ministry data: ministry types + memberships
9. Save all accumulated keyed caches
10. Cross-link all data (see Section 4)
11. Filter data per `active_only`, `parishioners_only`, `include_deceased`
12. Return the five dictionaries

### 2.2 Family Query Functions

#### `family_is_active(family) -> bool`

A family is active if:
- It is NOT in the "Inactive" family group, AND
- At least one member is active (via `member_is_active`)

Returns `False` if all members are deceased/inactive or no members exist.

#### `family_is_parishioner(family, org_id=None) -> bool`

Returns `True` if the family's `registeredOrganizationID` matches the org ID. Uses the global `_org_id` if `org_id` is not provided.

#### `get_family_heads(family) -> dict`

Returns a dict of members (keyed by member DUID) whose `memberType` is one of: `Head`, `Husband`, `Wife`.

#### `family_business_logistics_emails(family, member_workgroups, log) -> list[str]`

Returns a list of email addresses for sending business logistics communications. Uses a 4-tier fallback:

1. Members of the family who are in the "Business Logistics Email" member workgroup
2. Members with Head/Husband/Wife role
3. All family members with email addresses
4. The family-level email address

#### `family_business_logistics_emails_members(family, member_workgroups, log) -> list[dict]`

Same logic as above but returns the member objects instead of email strings.

### 2.3 Member Query Functions

#### `member_is_deceased(member) -> bool`

Returns `True` if `memberStatus` is `"Deceased"`.

#### `member_is_active(member) -> bool`

Returns `True` unless `memberStatus` is `"Inactive"` or `"Deceased"`.

#### `get_member_public_phones(member) -> list[dict]`

Returns a list of `{'number': str, 'type': str}` dicts for mobile and home phones, but only if `family_PublishPhone` is truthy. Types are `"cell"` and `"home"`.

#### `get_member_private_phones(member)`

**Stub** - not implemented (body is `pass`).

#### `get_member_public_email(member) -> str | None`

Returns the first email from `py emailAddresses` if `family_PublishEMail` is truthy. Returns `None` otherwise.

#### `get_member_preferred_first(member) -> str`

Returns the member's nickname (from `py contactInfo.nickName`) if available, otherwise `firstName`.

### 2.4 Salutation Function

#### `salutation_for_members(members) -> tuple[str, str]`

Returns `(first_part, last_name)` for addressing a group of members.

**Rules**:
- 1 member: `("PreferredFirst", "Last")`
- 2 members, same last name: `("First1 and First2", "Last")`
- 3+ members, same last name: `("First1, First2, and First3", "Last")`
- 2 members, different last names: `("First1 Last1 and First2", "Last2")`
- 3+ members, different last names: `("First1 Last1, First2 Last2, and First3", "Last3")`

---

## 3. Caching System

### 3.1 Cache Limit

The `cache_limit` parameter accepts humanized time strings:
- `s` = seconds, `m` = minutes, `h` = hours, `d` = days
- Examples: `"24s"`, `"15m"`, `"7h"`, `"2d"`
- Default: `"14m"` (designed for 15-minute cron intervals)

Cache files older than the limit are re-fetched from the API.

**Note**: There is a hardcoded debug override at module level that sets the cache limit to 1 day. The `cache_limit` parameter in `load_families_and_members` overrides this.

### 3.2 Simple Cache

Files stored as `cache-v2-{endpoint}.json` (with `/` replaced by `-`) in `cache_dir`.

- `_save_cache(endpoint, elements, cache_dir, log)`: Writes elements as JSON
- `_load_cache(endpoint, cache_dir, log)`: Returns elements if file exists and is fresh, else `None`

### 3.3 Keyed Cache

For endpoints that return per-key data (e.g., workgroup membership per workgroup ID). Multiple keys share a single JSON file.

- `_save_keyed_cache()`: Stores in-memory; actual file write deferred
- `_load_keyed_cache()`: Loads entire file on first access, then reads from memory
- `_save_all_keyed_caches()`: Writes all accumulated keyed caches to disk at end of load

**Known issue**: `json.dump()` converts integer keys to strings; `_load_keyed_cache` compensates by casting the lookup key to `str`.

---

## 4. Data Cross-Linking

After loading, the following cross-references are created (all prefixed with `py ` to distinguish from raw API fields):

### Family enrichments:
- `py members`: list of member dicts in this family
- `py family group`: string name of the family group (e.g., "Inactive")
- `py workgroups`: dict of family workgroup memberships keyed by workgroup name
- `py pledges`: list of pledge dicts
- `py contributions`: list of contribution dicts
- `py emailAddresses` (via `eMailAddress`): list of emails split on `;`

### Member enrichments:
- `py family`: back-reference to the containing family dict
- `py contactInfo`: contact info dict (includes `nickName`)
- `py workgroups`: dict of member workgroup memberships keyed by workgroup name
- `py ministries`: dict of current ministry memberships keyed by ministry name
- `py emailAddresses` (via `emailAddress`): list of emails split on `;`
- `py friendly name FL`: "First Last" using nickname if available
- `py friendly name LF`: "Last, First" using nickname if available
- `py active`: boolean, set during filtering

### Workgroup/Ministry membership enrichments:
- `py member duid`: back-reference to the member
- `py family duid`: back-reference to the family

---

## 5. Filtering

Filtering happens after all cross-linking is complete. Controlled by three flags:

### Member filtering:
- `active_only=True`: removes members where `member_is_active()` returns `False`
- `include_deceased=False`: removes deceased members

### Family filtering:
- `active_only=True`: removes families where `family_is_active()` returns `False`
- `parishioners_only=True`: removes families where `family_is_parishioner()` returns `False`
- Families with no remaining active members are removed

### Cascade deletions:
When a member is removed:
- Removed from all member workgroup memberships
- Removed from all ministry type memberships
- Removed from their family's `py members` list
- Removed from the members dict

When a family is removed:
- Removed from all family workgroup memberships
- Removed from all ministry type memberships
- All remaining members in the family are removed from the members dict
- Removed from the families dict

---

## 6. API Interaction

### 6.1 HTTP Session

- Uses `requests.Session` with `x-api-key` header
- Retry policy: 3 retries, 0.2s backoff factor, allowed on POST and GET
- All requests use `Accept: application/json` and `Content-Type: application/json`

### 6.2 Endpoint Types

| Function | Method | Pagination |
|----------|--------|------------|
| `_get_endpoint` | GET | No |
| `_get_paginated_endpoint` | GET | Yes |
| `_post_endpoint` | POST | No |
| `_post_paginated_endpoint` | POST | Yes |

### 6.3 Pagination

Two offset types supported:
- `index`: offset = number of elements already fetched
- `page`: offset = page number (1-based)

Two response formats handled:
- **List**: empty list signals end of data
- **Dict**: contains `pagingInfo.pageNumber` and `pagingInfo.totalPages`

Default page size is 100; some endpoints use 500 (contributions, pledges, members).

### 6.4 Endpoints Used

| Endpoint | Method | Pagination | Data |
|----------|--------|------------|------|
| `organizations/search` | POST | No | Organization lookup |
| `offering/{org_id}/funds` | GET | No | Fund definitions |
| `offering/pledge/list` | GET | Page (500) | Pledges |
| `offering/contributiondetail/list` | GET | Page (500) | Contributions |
| `families/search` | POST | Page (100) | Family records |
| `families/group/lookup/list` | GET | No | Family group lookups |
| `families/workgroup/list` | GET | Page (100) | Family workgroups |
| `families/workgroup/{duid}/list` | GET | Page (100) | Family workgroup members |
| `members/search` | POST | Page (100) | Member records |
| `members/memberstatus/list` | GET | No | Member status lookups |
| `members/membertype/list` | GET | No | Member type lookups |
| `members/contact/list` | POST | Page (100) | Member contact info |
| `members/workgroup/lookup/list` | GET | Page (100) | Member workgroup lookups |
| `members/workgroup/{duid}/list` | GET | Page (100) | Member workgroup members |
| `ministry/type/list` | GET | Page (100) | Ministry type lookups |
| `ministry/{id}/minister/list` | GET | Page (100) | Ministry members |

### 6.5 Cross-Reference with REST API Documentation

**Source**: Swagger/OpenAPI spec at `https://ps-fs-external-api-prod.azurewebsites.net/swagger/v2/swagger.json`

#### Endpoints: Code vs API Documentation

| Endpoint (code) | API Doc Match | Discrepancies |
|---|---|---|
| `organizations/search` (POST) | **NOT IN SWAGGER** | Endpoint is not documented in the v2 OpenAPI spec. May be undocumented or from an earlier API version. |
| `offering/{org_id}/funds` (GET) | `/api/v2/offering/{organizationId}/funds` | Matches. No pagination needed. |
| `offering/pledge/list` (GET) | `/api/v2/offering/pledge/list` | Matches. API uses `PageSize`/`PageNumber`; code correctly uses these names with limit=500. |
| `offering/contributiondetail/list` (GET) | `/api/v2/offering/contributiondetail/list` | Matches. Code passes `startDate` (camelCase) as query param; API documents `StartDate` (PascalCase) — works because server is case-insensitive. API also supports `EndDate`, `FundId`, `FamilyId`, `MemberId`, `StartAmount`, `GivingSourceId`, `OrganizationId` filters that the code does not use. |
| `families/search` (POST) | `/api/v2/families/search` | **Pagination mismatch**: API returns `Array of FamilySearchResponseDto` (a simple list with no pagingInfo). Code uses `_post_paginated_endpoint` with `PageNumber`/page offset, paging via empty-array detection. The body param `organizationIDs` is not documented in swagger but works. |
| `families/group/lookup/list` (GET) | `/api/v2/families/group/lookup/list` | Matches. No pagination. |
| `families/workgroup/list` (GET) | `/api/v2/families/workgroup/list` | **Page size**: API allows max 500 (default 500) with `PageSize`/`PageNumber`. Code uses default limit=100. Could use 500 for fewer round-trips. |
| `families/workgroup/{duid}/list` (GET) | `/api/v2/families/workgroup/{workGroupId}/list` | **Page size**: API allows max 500. Code uses default limit=100. API response type is `ListPagingResponse` (dict with `pagingInfo`+`data`); code handles both list and dict formats in `_get_paginated_endpoint`. |
| `members/search` (POST) | `/api/v2/members/search` | **Pagination param mismatch**: Code uses `maximumRows`/`startRowIndex` (non-standard names), while swagger shows no explicit pagination params for this endpoint. These are passed in the POST body. API returns a simple array. |
| `members/memberstatus/list` (GET) | `/api/v2/members/memberstatus/list` | Matches. No pagination. |
| `members/membertype/list` (GET) | `/api/v2/members/membertype/list` | Matches. Returns array of strings. |
| `members/contact/list` (POST) | `/api/v2/members/contact/list` | Matches. Code uses default `Offset`/`Limit` param names with page-type offset. |
| `members/workgroup/lookup/list` (GET) | `/api/v2/members/workgroup/lookup/list` | **Page size**: API allows max 500 with `PageSize`/`PageNumber`. Code uses default limit=100. API response is `ListPagingResponse` type. Also supports optional `organizationId` query param that code doesn't use. |
| `members/workgroup/{duid}/list` (GET) | `/api/v2/members/workgroup/{workGroupId}/list` | **Page size**: API allows max 500. Code uses default limit=100. API response is `ListPagingResponse` type. |
| `ministry/type/list` (GET) | `/api/v2/ministry/type/list` | **Page size**: API allows max 500 with `PageSize`/`PageNumber`. Code uses default limit=100. Also supports optional `organizationId` query param that code doesn't use. |
| `ministry/{id}/minister/list` (GET) | `/api/v2/ministry/{ministryTypeId}/minister/list` | **Page size**: API allows max 500. Code uses default limit=100. |

#### API Endpoints NOT Used by Code

The following v2 API endpoints exist but are not used by `ParishSoftv2.py`:

| Endpoint | Method | Purpose |
|---|---|---|
| `constituents/search` | GET | Constituent search (separate from Family/Member model) |
| `constituents/detail/{sDioceseId}` | GET | Constituent detail lookup |
| `families/quick-search` | POST | Faster family search |
| `families/{familyId}` | GET | Single family detail |
| `families/{familyId}/member/list` | GET | Members of a specific family |
| `families/{familyId}/ministry/list` | GET | Ministries of a specific family |
| `families/{familyId}/contact` | PUT | Update family contact info |
| `families/{familyId}/autofill` | PUT | Update family autofill fields |
| `families/change/list` | GET | Family change log by date range |
| `members/quick-search` | POST | Faster member search |
| `members/{memberId}` | GET | Single member detail |
| `members/{memberId}/sacrament/{type}/list` | GET | Member sacrament records |
| `members/workgroup/list` | GET | **Deprecated** member workgroup list |
| `members/{memberId}/contact` | PUT | Update member contact info |
| `offering/{organizationId}/givers` | GET | Giver list |
| `offering/{organizationId}/contribution/summary/list` | POST | Family contribution summary |

#### Key Observations

1. **`organizations/search` is undocumented** — this endpoint is not in the swagger spec but is used as the first call to identify the org ID. It may be an older endpoint carried forward.

2. **Page size opportunity** — 8 endpoints use `limit=100` where the API allows `PageSize` up to 500. Increasing to 500 would reduce API round-trips by up to 5x for large datasets (e.g., ministry types, workgroup memberships).

3. **`members/search` uses non-standard pagination params** — `maximumRows`/`startRowIndex` are not in the swagger docs. These may be legacy body params that the API still accepts but doesn't document.

4. **`contributiondetail/list` has unused filters** — the API supports filtering by `EndDate`, `FundId`, `FamilyId`, `MemberId`, `StartAmount`, `GivingSourceId`, and `OrganizationId` that the code doesn't expose.

5. **Response format ambiguity** — some endpoints return `ListPagingResponse` (dict with `pagingInfo` and `data`) while others return plain arrays. The code's `_get_paginated_endpoint` handles both formats, which is correct.

6. **No write operations** — the code only reads data. The API offers PUT endpoints for updating family and member contact info that are not used.

---

## 7. Ministry Filtering

Ministry types are filtered by an allowlist during loading. Only types matching these patterns are retained:
- Names starting with three digits followed by `-` (e.g., `"100-Lectors"`)
- Specifically named: `"E-Soul Life"` or `"E-Taize Prayer"`

Ministry membership records are further filtered to only include records that are current (today falls between `startDate` and `endDate`).

---

## 8. Date Normalization

All date fields from the API are converted from ISO format strings to `datetime.date` objects using `_normalize_dates()`. Fields normalized include:
- Pledges: `pledgeDate`, `pledgeStartDate`
- Contributions: `contributionDate`
- Families: `dateModified`
- Members: `birthdate`, `dateModified`, `dateOfDeath`
- Member contact info: `dateOfBirth`, `dateOfDeath`
- Ministry memberships: `startDate`, `endDate`

---

## 9. Email Normalization

All email addresses are normalized to lowercase. Multi-valued email fields (separated by `;`) are split into Python lists stored in `py` prefixed keys:
- Family: `eMailAddress` → `py eMailAddresses` (list)
- Member: `emailAddress` → `py emailAddresses` (list)
- Family workgroup members: `email` → `py emails` (list)
- Member workgroup members: `emailAddress` → `py emailAddresses` (list)

---

## 10. Dependencies

- `requests` + `urllib3` — HTTP client with retry logic
- `ECC` — imported but not directly used by public functions (used by callers for logging setup)
- Standard library: `os`, `re`, `sys`, `csv`, `json`, `time`, `datetime`

---

## 11. Reconciliation Summary

**Reconciled**: 2026-03-01
**API docs cross-referenced**: 2026-03-01 (swagger v2 spec)

This document was created to reflect the actual implementation of `python/ParishSoftv2.py`.
The specification was derived from reading the source code, analyzing usage across 14 consumer scripts,
and cross-referencing against the ParishSoft v2 OpenAPI/Swagger specification.
