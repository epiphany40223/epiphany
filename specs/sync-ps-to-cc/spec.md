# sync-ps-to-cc.py Specification

**Script**: `media/linux/ps-queries/sync-ps-to-cc.py`
**Purpose**: Synchronize ParishSoft Member Workgroups to Constant Contact Lists. PS is the source of truth; CC data is updated to match.

---

## 1. Overview

This script replaces `sync-constant-contact.py` with a cleaner, more robust implementation. It:

1. Loads active PS Members (including non-parishioners)
2. Downloads CC Contacts and Lists
3. Correlates PS Members to CC Contacts by email address
4. Computes a de-duplicated set of sync actions (create, subscribe, unsubscribe, delete candidates)
5. Executes those actions against the CC API (with retry and rate-limit handling)
6. Sends per-list HTML notification emails detailing the actions performed
7. Supports a dry-run mode that logs actions without executing them

**Key design principles**:

- Multiple PS Members may share a single email address and therefore map to a single CC Contact. All logic must handle this correctly.
- Downloaded data (CC contacts, PS members) is treated as **read-only** after loading and indexing. Sync logic produces an **action list** — a separate list of dicts describing what needs to happen — rather than mutating contact data in place. The action list is the single source of truth for execution, dry-run logging, and notification emails.

---

## 2. Synchronization Configuration

### 2.1 Config Module

The synchronization mappings are extracted to a standalone Python module that can be imported by multiple scripts.

**File**: `media/linux/ps-queries/cc_sync_config.py`

```python
SYNCHRONIZATIONS = [
    {
        'source ps member wg': 'Daily Gospel Reflections',
        'target cc list':      'SYNC Daily Gospel Reflections',
        'notifications':       [
            'ps-constantcontact-sync@epiphanycatholicchurch.org,'
            'director-communications@epiphanycatholicchurch.org',
        ],
    },
    {
        'source ps member wg': 'Parish-wide Email',
        'target cc list':      'SYNC Parish-wide Email',
        'notifications':       [
            'ps-constantcontact-sync@epiphanycatholicchurch.org,'
            'director-communications@epiphanycatholicchurch.org',
        ],
    },
]
```

Each entry maps:
- `source ps member wg`: Name of a PS Member Workgroup (the source of truth)
- `target cc list`: Name of a CC List to synchronize
- `notifications`: List of comma-delimited email address strings to notify when actions are performed on this CC List

### 2.2 Config Resolution

At runtime, the script resolves each synchronization entry:
1. Finds the PS Member Workgroup by name and extracts its members (with email addresses)
2. Finds the CC List by name and its current contacts
3. Logs an error and exits if either is not found

---

## 3. Execution Flow

### 3.1 High-Level Flow

```
1. Parse CLI arguments
2. Set up logging
3. Authenticate with CC (load_client_id + get_access_token); exit if --cc-auth-only
4. Set up email
5. Load PS data (families, members, workgroups)
6. Download CC Contacts and Lists, build read-only indexes
7. Resolve synchronization config → desired state per list
8. Filter out CC-unsubscribed emails from desired state
9. Compute action list (subscribe, unsubscribe, create, name updates)
10. Log deletion candidates
11. Execute action list (unless --dry-run or --no-sync)
12. Send notification emails (unless --dry-run or --no-sync)
13. Send unsubscribed-contacts report (if --unsubscribed-report; log-only if --dry-run)
```

### 3.2 Architecture: Immutable Data + Action List

Downloaded CC contacts and PS members are treated as **read-only** after the indexing step. All sync logic produces an **action list** — a plain Python list of action dicts — without mutating any downloaded data. This replaces the legacy pattern of attaching action flags to contact dicts and mutating `list_memberships` in place.

The action list is the single source of truth for:
- **Execution**: grouped by email to minimize API calls
- **Dry-run logging**: printed without executing
- **Notification emails**: filtered by sync index

#### 3.2.1 Action Dict Structure

Each action in the action list is a dict:

```python
{
    'type':       str,   # 'create', 'subscribe', 'unsubscribe', or 'update_name'
    'email':      str,   # contact email address
    'list_name':  str,   # CC list name (for subscribe/unsubscribe; None for others)
    'list_uuid':  str,   # CC list UUID (for subscribe/unsubscribe; None for others)
    'detail':     str,   # human-readable description for logging and email
    'sync_index': int,   # index into SYNCHRONIZATIONS (for grouping notifications)
}
```

Name update actions additionally carry:

```python
{
    'new_first':  str,   # new first name
    'new_last':   str,   # new last name
    'old_first':  str,   # previous first name (for logging)
    'old_last':   str,   # previous last name (for logging)
}
```

### 3.3 Step Details

#### 3.3.1 Load PS Data

Call `ParishSoft.load_families_and_members()` with:
- `active_only=True`
- `parishioners_only=False`
- Other parameters from CLI arguments (api_key, cache_dir)

Returns: families, members, family_workgroups, member_workgroups, ministries

#### 3.3.2 Authenticate and Load CC Data

Authenticate using `ConstantContact.load_client_id()` and `ConstantContact.get_access_token()`. If `--cc-auth-only` is set, log a message and exit. Authentication runs early in `main()` (before PS data loading) so that `--cc-auth-only` does not require PS credentials.

Download (after PS data loading):
- **Contacts**: `api_get_all('contacts', 'contacts', include='list_memberships', status='all')`
- **Lists**: `api_get_all('contact_lists', 'lists')`

Normalize all CC contact email addresses to lowercase.

#### 3.3.3 Build Read-Only Indexes

After loading, build these lookup structures (all derived from the loaded data, treated as read-only from this point forward):

1. Call `ConstantContact.link_cc_data(cc_contacts, [], cc_lists, log)`. This populates:
   - `contact['LIST MEMBERSHIPS']`: list of human-readable list names
   - `list['CONTACTS']`: dict of `{email: contact}` for each list

2. Call `ConstantContact.link_contacts_to_ps_members(cc_contacts, members, log)`. This populates:
   - `contact['PS MEMBERS']`: list of PS member dicts matching by email
   - `member['CONTACT']`: back-reference to CC contact

3. Build script-level indexes:
   - `cc_contacts_by_email`: `{email: contact}` for quick contact lookup
   - `ps_members_by_email`: `{email.lower(): [member, ...]}` for all PS members sharing that email (lowercase keys to match CC email normalization)

These structures are **not modified** by any subsequent step.

#### 3.3.4 Resolve Synchronization Config → Desired State

For each entry in `SYNCHRONIZATIONS`:
1. Find the PS Member Workgroup by name; extract members with email addresses into `desired_emails[i]` (a set of lowercase email strings). For each workgroup membership entry with a `'py member duid'` key, look up the full member from `ps_members[duid]` and include their first email if `member['emailAddress']` is truthy. Log a warning for members with no email.
2. Find the CC List by name; store the list object in `sync['TARGET CC LIST']`.

Log error and exit if a workgroup or list is not found.

The result is a set of desired emails per sync entry: `desired_emails[i] = {email1, email2, ...}`.

#### 3.3.5 Filter Out CC-Unsubscribed Emails

For each CC Contact whose `email_address.permission_to_send` is `'unsubscribed'`:
- Remove that email from every `desired_emails[i]` set
- Record the removal for notification email reporting: for each sync where the email was present, store `(email, [PS member names], [PS member DUIDs])` in `unsubscribed_per_sync[i]`

This prevents the script from re-subscribing contacts who manually opted out.

#### 3.3.6 Compute Action List

Compute all actions in a single pass, producing a flat action list without mutating any loaded data.

**Step 1: Identify emails needing new contacts**

```
all_desired_emails = union of all desired_emails[i]
emails_needing_contacts = all_desired_emails - set(cc_contacts_by_email.keys())
```

For each email needing a contact:
- Collect all PS Members with that email from `ps_members_by_email`
- Add a `create` action to the action list

**Step 2: Per-list subscribe/unsubscribe**

For each synchronization entry `i`:
- `current_emails` = set of emails in `sync['TARGET CC LIST']['CONTACTS']`
- `to_subscribe = desired_emails[i] - current_emails`
- `to_unsubscribe = current_emails - desired_emails[i]`
- Add `subscribe` actions and `unsubscribe` actions to the action list, each with `sync_index=i`

**Step 3: Name mismatches**

For each CC Contact in `cc_contacts_by_email` that has `'PS MEMBERS'`:
1. Recompute the expected name using `ParishSoft.salutation_for_members(contact['PS MEMBERS'])`
2. Strip periods from the expected first name (CC rejects periods)
3. Compare with `contact.get('first_name', '')` and `contact.get('last_name', '')`
4. Always log differences
5. If `--update-names` is set, add an `update_name` action to the action list

**Step 4: Deletion candidates (log only)**

Log (but do NOT add to action list) any CC Contact meeting either condition:
- `'PS MEMBERS'` key is absent or empty
- The contact's current list memberships minus all `unsubscribe` actions for that email would be empty

#### 3.3.7 Execute Action List

Group actions by email to minimize API calls. For each email with actions:

**POST call** (create + subscribe, or subscribe existing contact):
- Collect all `create` and `subscribe` actions for this email
- If the email needs a new contact: call `CC.create_contact_dict(email, ps_members, log)` to build the contact dict, set `list_memberships` to the list UUIDs from all subscribe actions
- If the email has an existing contact: build a dict with `email_address`, `first_name`, `last_name` from the existing contact, and `list_memberships` = [only the NEW list UUIDs from subscribe actions]
- Call `CC.create_or_update_contact(contact_dict, ...)` — the CC sign_up_form API **adds** to list memberships
- One POST per contact

**PUT call** (unsubscribe + name update):
- Collect all `unsubscribe` and `update_name` actions for this email
- Build a dict from the existing contact's fields: `contact_id`, `email_address` (full object), `first_name`, `last_name`, `list_memberships`
- Set `list_memberships` = original contact's `list_memberships` minus all unsubscribe list UUIDs
- If there's an `update_name` action: set `first_name` and `last_name` to the new values
- Call `CC.update_contact_full(contact_dict, ...)` — the CC PUT API **replaces** list memberships with exactly what's sent
- One PUT per contact

**Error handling**: Wrap each CC API call in `try/except CCAPIError`. On failure, log the error and continue processing remaining contacts. Record failures `(email, action_type, error_message)` for inclusion in notification emails.

**Dry-run mode** (`--dry-run`): Log all actions that would be performed, but do not make any CC API calls.

**No-sync mode** (`--no-sync`): Same as dry-run for this step — log all actions that would be performed, but do not make any CC API calls. The difference from `--dry-run` is that `--no-sync` allows the unsubscribed-contacts report (Section 3.3.9) to send emails.

#### 3.3.8 Send Notification Emails

For each synchronization entry `i`, filter the action list by `sync_index == i`. If any actions exist for that list:

1. Collect action descriptions for the list
2. Collect unsubscribed contacts from `unsubscribed_per_sync[i]`
3. Collect any failed actions for this list
4. Build an HTML email (see Section 5)
5. Send to each address in the sync's `notifications` list using `ECC.send_email()` with `content_type='text/html'`

Do NOT send sync notification emails in dry-run mode or no-sync mode.

#### 3.3.9 Send Unsubscribed-Contacts Report

Only runs if `--unsubscribed-report` is set. This step runs **after** all normal sync actions and notification emails have completed.

For each synchronization entry `i` where `unsubscribed_per_sync[i]` is non-empty:

1. Build a standalone HTML email (see Section 5.4) listing the PS Members who are in the sync's PS Member Workgroup but whose CC Contact has `permission_to_send = 'unsubscribed'`
2. Include the PS Member Workgroup name (`SYNCHRONIZATIONS[i]['source ps member wg']`) so recipients know which workgroup to update
3. If `--dry-run`: log a warning that no email will be sent, then log the subject and the effective report contents (CC list name, PS workgroup name, and each unsubscribed member's name, DUID, and email) at info level. Do NOT send the email.
4. Otherwise (including `--no-sync` without `--dry-run`): send to each address in `SYNCHRONIZATIONS[i]['notifications']` using `ECC.send_email()` with `content_type='text/html'`

This email is **separate** from the sync update notification (Section 3.3.8). Its purpose is to inform administrators which PS Members should be removed from the PS Member Workgroup because they have manually unsubscribed from Constant Contact.

---

## 4. CLI Arguments

Use standard `argparse`. Required and optional arguments:

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--ps-api-keyfile` | Yes | — | File containing the ParishSoft API key |
| `--cc-client-id` | No | `constant-contact-client-id.json` | File containing the CC Client ID |
| `--cc-access-token` | No | `constant-contact-access-token.json` | File containing the CC access token |
| `--service-account-json` | No | `ecc-emailer-service-account.json` | Google service account JSON key file |
| `--impersonated-user` | No | `no-reply@epiphanycatholicchurch.org` | Google Workspace user to impersonate via DWD |
| `--ps-cache-dir` | No | `datacache` | Directory to cache PS data |
| `--cc-auth-only` | No | `False` | Only authenticate to CC, then exit |
| `--update-names` | No | `False` | Update CC Contact names from PS data when they differ |
| `--unsubscribed-report` | No | `False` | Generate and send standalone report of PS Members whose CC Contacts have unsubscribed |
| `--no-sync` | No | `False` | Skip sync execution and sync notification emails. All computation still runs. Unlike `--dry-run`, allows `--unsubscribed-report` to send emails |
| `--dry-run` | No | `False` | Log actions without executing. No emails sent. Implies `--verbose` |
| `--verbose` | No | `False` | Emit extra status messages |
| `--debug` | No | `False` | Emit debug-level messages. Implies `--verbose` |
| `--logfile` | No | `log.txt` | File for verbose/debug log output |

---

## 5. Notification Email Format

Each notification email is clean, professional HTML. One email is sent per CC List per notification address when actions occur.

### 5.1 Email Structure

```
Subject: Constant Contact sync update: {CC List Name}

Body:
  1. Header with CC List name and timestamp
  2. ParishSoft Member Workgroup name and Constant Contact List name
  3. Summary counts (contacts subscribed, contacts unsubscribed, update failures)
  4. "Actions Performed" table grouped by action type (subscribe, unsubscribe)
     with blue separator rows between groups; sorted by last name then first
     name within each group
     - Columns: Action, Contact Name(s), ParishSoft Member DUID(s), Email
     - "create" and "update_name" actions are suppressed from this table
       (create actions always have a corresponding subscribe action;
       name updates are logged but not emailed)
  5. "Failed Actions" section (only if failures occurred)
     - Columns: Contact Name(s), ParishSoft Member DUID(s), Email, Action,
       Update error
     - Sorted by last name then first name
  6. Footer noting this is an automated message
```

### 5.2 Styling

- Clean, professional HTML suitable for email clients
- Use inline CSS (email clients strip `<style>` blocks)
- Tables: auto-width (sized to content), left-justified, bordered, alternating row colors for readability
- Table column headings: centered, blue background (`#4472C4`) with white text
- Table cells: `white-space: nowrap` to prevent wrapping
- Clear section headings
- No images or external resources (for email deliverability)

### 5.3 Failed Actions

If any individual contact updates failed during execution, include a "Failed Actions" section (with red heading) listing: Contact Name(s), ParishSoft Member DUID(s), Email, Action, and Update error. Sorted by last name then first name.

### 5.4 Unsubscribed-Contacts Report Email

A standalone email sent when `--unsubscribed-report` is set. One email per CC List per notification address, only for lists that have unsubscribed PS Members. This is a separate email from the sync notification in Section 5.1.

```
Subject: Constant Contact unsubscribed contacts report: {CC List Name}

Body:
  1. Header with CC List name and timestamp
  2. Explanation paragraph:
     "The following ParishSoft Members are in the '{PS Workgroup Name}'
     workgroup but have manually unsubscribed from Constant Contact."
  3. Bold red warning paragraph (16px):
     "These ParishSoft Members should be removed from the
     '{PS Workgroup Name}' workgroup in ParishSoft."
  4. Table: PS Member name(s), PS Member DUID(s), email address
     - Sorted by last name then first name
  5. Footer noting this is an automated message
```

Follows the same styling guidelines as Section 5.2 (inline CSS, bordered tables with alternating row colors, auto-width, no images).

---

## 6. Error Handling

### 6.1 CC API Errors

The updated `ConstantContact.py` module raises `CCAPIError` exceptions on non-2xx responses (see ConstantContact spec).

**Bulk data loading** (GET all contacts, GET all lists): If these fail, the script cannot proceed. Let the exception propagate and terminate the script.

**Individual contact updates** (PUT/POST): Catch `CCAPIError`, log the failure, and continue processing remaining contacts. Accumulate failures for the notification email.

### 6.2 PS Data Loading

If PS data loading fails, let the exception propagate and terminate the script (same as current behavior).

### 6.3 Configuration Errors

If a PS Member Workgroup or CC List from `SYNCHRONIZATIONS` is not found, log an error and exit.

---

## 7. Corner Cases

### 7.1 Multiple PS Members Sharing an Email

Multiple PS Members may have the same email address (e.g., a married couple sharing `family@example.com`). This means:

- A single CC Contact maps to multiple PS Members
- The contact's name is derived from all linked members via `salutation_for_members()`
- If any of those members is in a synced workgroup, the contact should be on the corresponding CC List

The `ps_members_by_email` index (Section 3.3.3) naturally collects all members sharing an email, making it straightforward to collect them when creating a new contact.

### 7.2 Email Address Changes

**Members who used to share an email but now have different emails**:
- The old CC Contact retains one or more members; the other members now need a new CC Contact
- The old contact's name may need updating (if `--update-names`)
- The new contact needs creating

**Members who didn't share an email but now do**:
- One of the old CC Contacts now maps to multiple members
- That contact's name may need updating
- The other old CC Contact may become a deletion candidate (no PS Members linked)

Both scenarios are handled naturally by the set-diff computation: the diff between desired and current state produces the correct subscribe/unsubscribe/create actions without special-case code.

### 7.3 CC-Unsubscribed Contacts

Contacts who have globally unsubscribed from CC (`permission_to_send = 'unsubscribed'`) must NOT be re-subscribed. They are removed from the desired email sets before computing the diff.

### 7.4 Period in First Names

CC rejects contact names containing periods (e.g., `"T.J."`). Strip periods from `first_name` before comparison and before sending to the CC API. Note that `ConstantContact.py` also strips periods in `update_contact_full()` and `create_or_update_contact()`, but the script should strip them during comparison to avoid false-positive name mismatch detections.

---

## 8. Dependencies

### 8.1 Internal Modules

| Module | Import | Usage |
|--------|--------|-------|
| `ConstantContact` | `import ConstantContact as CC` | CC API operations |
| `ParishSoftv2` | `import ParishSoftv2 as ParishSoft` | PS data loading and member queries |
| `ECC` | `import ECC` | Logging setup, email sending |

### 8.2 External Dependencies

| Package | Usage |
|---------|-------|
| `argparse` | CLI argument parsing (stdlib) |
| `logging` | Logging (stdlib) |

### 8.3 Module Path

The script uses the same `moddir` pattern as `sync-constant-contact.py` to add the `python/` directory to `sys.path`:
```python
moddir = '../../../python'
```

---

## 9. Relationship to Existing Code

### 9.1 ConstantContact.py Functions Used

| Function | Purpose |
|----------|---------|
| `load_client_id()` | Load CC client ID config |
| `get_access_token()` | Obtain/refresh CC OAuth2 token |
| `api_get_all()` | Download all CC Contacts and Lists |
| `link_cc_data()` | Cross-link contacts with lists |
| `link_contacts_to_ps_members()` | Correlate CC Contacts to PS Members by email |
| `create_contact_dict()` | Create in-memory CC Contact from PS Members |
| `create_or_update_contact()` | POST to sign_up_form (create/subscribe) |
| `update_contact_full()` | PUT to contacts/{id} (unsubscribe/update) |

### 9.2 ParishSoftv2.py Functions Used

| Function | Purpose |
|----------|---------|
| `load_families_and_members()` | Load all PS data |
| `salutation_for_members()` | Compute contact name from PS Members |
| `member_is_active()` | Check member active status (used indirectly) |
| `family_is_active()` | Check family active status (used indirectly) |

### 9.3 ECC.py Functions Used

| Function | Purpose |
|----------|---------|
| `setup_logging()` | Configure logging |
| `setup_email()` | Configure Gmail SMTP credentials |
| `send_email()` | Send notification emails |

---

## 10. What This Script Does NOT Do

- **Delete CC Contacts**: Deletion candidates are logged but never deleted
- **Modify PS data**: PS is read-only source of truth
- **Handle CC email campaigns**: Out of scope
- **Proactively throttle requests**: Rate limiting is reactive (via 429 handling in ConstantContact.py)
- **Mutate downloaded data**: CC contacts and PS members are read-only after indexing; sync logic produces an action list instead

---

## 11. Reconciliation Summary

**Created**: 2026-03-01
**Revised**: 2026-03-01 (adopted declarative diff architecture with immutable data + action list)
**Derived from**: Analysis of `sync-constant-contact.py`, `ConstantContact.py` spec, `ParishSoftv2.py` spec, and requirements interview.

This specification describes a new script. It has not yet been implemented.
