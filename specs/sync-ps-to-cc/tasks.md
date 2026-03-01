# sync-ps-to-cc.py - Implementation Tasks

> Auto-generated from `specs/sync-ps-to-cc/spec.md`. Each task maps to a spec section.
> Mark tasks: `[ ]` pending, `[~]` in progress, `[x]` done, `[-]` skipped, `[!]` blocked.

---

## Phase 1: Configuration Module and Script Scaffolding

- [x] **1.1** Create `cc_sync_config.py` with `SYNCHRONIZATIONS` list
  - Create file at `media/linux/ps-queries/cc_sync_config.py`.
  - Define a module-level `SYNCHRONIZATIONS` list of dicts. Each dict has three keys:
    - `'source ps member wg'`: string — PS Member Workgroup name (e.g., `'Daily Gospel Reflections'`, `'Parish-wide Email'`)
    - `'target cc list'`: string — CC List name (e.g., `'SYNC Daily Gospel Reflections'`, `'SYNC Parish-wide Email'`)
    - `'notifications'`: list of comma-delimited email address strings (e.g., `['ps-constantcontact-sync@epiphanycatholicchurch.org,director-communications@epiphanycatholicchurch.org']`)
  - Populate with the two synchronization entries from the existing `get_synchronizations()` function in `sync-constant-contact.py` (lines 81-92).
  - No imports needed; this is a pure-data module.
  - _Spec: section 2.1_

- [x] **1.2** Create `sync-ps-to-cc.py` with module path handling and imports
  - Create file at `media/linux/ps-queries/sync-ps-to-cc.py`.
  - Add shebang `#!/usr/bin/env python3`.
  - Replicate the `moddir` pattern from `sync-constant-contact.py` (lines 20-32): resolve `'../../../python'`, handle the MS Windows symlink-as-file quirk (read the file contents as the path), insert into `sys.path`.
  - Import modules:
    - `import ECC`
    - `import ParishSoftv2 as ParishSoft`
    - `import ConstantContact as CC`
    - `from ConstantContact import CCAPIError`
    - `from cc_sync_config import SYNCHRONIZATIONS`
  - Import stdlib: `os`, `sys`, `argparse`, `logging`, `datetime`.
  - Import `pprint.pformat` for debug logging.
  - Add `if __name__ == '__main__': main()` at the bottom.
  - _Spec: sections 8.1, 8.2, 8.3_

- [x] **1.3** Implement CLI argument parsing with `argparse`
  - Create a `setup_cli_args()` function that uses standard `argparse.ArgumentParser` (NOT `oauth2client.tools.argparser`).
  - Define arguments:
    - `--ps-api-keyfile` (required): ParishSoft API key file
    - `--cc-client-id` (default `'constant-contact-client-id.json'`): CC Client ID file
    - `--cc-access-token` (default `'constant-contact-access-token.json'`): CC access token file
    - `--service-account-json` (default `'ecc-emailer-service-account.json'`): Google service account JSON key file
    - `--impersonated-user` (default `'no-reply@epiphanycatholicchurch.org'`): Google Workspace user to impersonate via DWD
    - `--ps-cache-dir` (default `'datacache'`): directory to cache PS data
    - `--cc-auth-only` (default `False`, `action='store_true'`): only authenticate to CC, then exit
    - `--update-names` (default `False`, `action='store_true'`): update CC Contact names from PS data when they differ
    - `--unsubscribed-report` (default `False`, `action='store_true'`): generate and send standalone report of PS Members whose CC Contacts have unsubscribed
    - `--no-sync` (default `False`, `action='store_true'`): skip sync execution and sync notification emails; all computation still runs; unlike `--dry-run`, allows `--unsubscribed-report` to send emails
    - `--dry-run` (default `False`, `action='store_true'`): log actions without executing; no emails sent; implies `--verbose`
    - `--verbose` (default `False`, `action='store_true'`): emit extra status messages
    - `--debug` (default `False`, `action='store_true'`): emit debug-level messages; implies `--verbose`
    - `--logfile` (default `'log.txt'`): file for verbose/debug log output
  - After parsing: `--dry-run` implies `--verbose`; `--debug` implies `--verbose`.
  - Read the PS API key from the file specified by `--ps-api-keyfile`: check file exists (exit with error if not), read and `.strip()` the contents, store in `args.api_key`.
  - Return the `args` namespace.
  - _Spec: section 4_

---

## Phase 2: Data Loading and Indexing

- [x] **2.1** Implement PS data loading
  - Create a function (or inline in `main()`) that calls `ParishSoft.load_families_and_members()` with:
    - `api_key=args.api_key`
    - `active_only=True`
    - `parishioners_only=False`
    - `cache_dir=args.ps_cache_dir`
    - `log=log`
  - Unpack the 5-tuple return: `families, members, family_workgroups, member_workgroups, ministries`.
  - Log that PS data is being loaded (info level).
  - _Spec: section 3.3.1_

- [x] **2.2** Implement CC authentication and data loading
  - **Authentication** (runs early in `main()`, before PS data loading):
    - Call `CC.load_client_id(args.cc_client_id, log)` and `CC.get_access_token(args.cc_access_token, cc_client_id, log)`.
    - If `args.cc_auth_only` is set, log a message and `exit(0)`.
  - **Download** (runs after PS data loading):
    - Let `CCAPIError` propagate on failure — do NOT catch it here.
    - Lists: `CC.api_get_all(cc_client_id, cc_access_token, 'contact_lists', 'lists', log)`
    - Contacts: `CC.api_get_all(cc_client_id, cc_access_token, 'contacts', 'contacts', log, include='list_memberships', status='all')`
  - _Spec: section 3.3.2, 6.1_

- [x] **2.3** Normalize CC contact emails to lowercase
  - After downloading contacts, iterate all contacts and lowercase `contact['email_address']['address']`.
  - _Depends: 2.2_
  - _Spec: section 3.3.2_

- [x] **2.4** Link CC data and correlate with PS Members
  - Call `CC.link_cc_data(cc_contacts, [], cc_lists, log)`. This populates `contact['LIST MEMBERSHIPS']` and `list['CONTACTS']`.
  - Call `CC.link_contacts_to_ps_members(cc_contacts, members, log)`. This populates `contact['PS MEMBERS']` and `member['CONTACT']`.
  - These calls mutate the downloaded data to add cross-references, but the cross-referenced data is treated as **read-only** from this point forward.
  - _Depends: 2.1, 2.2, 2.3_
  - _Spec: section 3.3.3_

- [x] **2.5** Build script-level read-only indexes
  - Build `cc_contacts_by_email`: `{email: contact}` dict for quick contact lookup by email address.
  - Build `ps_members_by_email`: `{email: [member, ...]}` dict collecting ALL PS members sharing each email. Iterate `members.values()`, skip members with no `emailAddress`, use `member['py emailAddresses'][0].lower()` as the key (lowercase to match CC email normalization).
  - These indexes are **not modified** by any subsequent step.
  - _Depends: 2.4_
  - _Spec: section 3.3.3_

---

## Phase 3: Desired State and Filtering

- [ ] **3.1** Resolve synchronization config to desired email sets
  - Create a `resolve_desired_state()` function (or similar).
  - For each entry `i` in `SYNCHRONIZATIONS`:
    1. **Resolve PS Member Workgroup**: search `member_workgroups` (dict of dicts) by `wg['name'] == sync['source ps member wg']`. For each workgroup membership entry with a `'py member duid'` key, look up the full member from `members[duid]`. If `member['emailAddress']` is truthy, add `member['py emailAddresses'][0].lower()` to `desired_emails[i]` (a set). Log a warning for members in the workgroup with no email. Log info with member count on success.
    2. **Resolve CC List**: search `cc_lists` (list of dicts) by `l['name'] == sync['target cc list']`. Store the list dict in `sync['TARGET CC LIST']`.
    3. If either the workgroup or list is not found, log an error and `exit(1)`.
  - Return `desired_emails` (a list of sets, one per sync entry) and the resolved synchronizations.
  - _Spec: section 3.3.4, 6.3_

- [ ] **3.2** Filter out CC-unsubscribed emails from desired state
  - Create a `filter_unsubscribed()` function.
  - Initialize `unsubscribed_per_sync`: a list of lists (one per sync entry), each holding `(email, member_names_str, member_duids_str)` tuples for notification email reporting.
  - Iterate all `cc_contacts`. For each contact where `contact['email_address']['permission_to_send'] == 'unsubscribed'`:
    - Get the contact's email.
    - For each `desired_emails[i]` set that contains this email:
      - Remove the email from `desired_emails[i]`.
      - Look up PS members for this email (from `ps_members_by_email` or `contact['PS MEMBERS']`).
      - Record `(email, member names, member DUIDs)` in `unsubscribed_per_sync[i]`.
    - Log each removal at info level.
  - Return `unsubscribed_per_sync` for later use in notification emails.
  - _Depends: 2.5, 3.1_
  - _Spec: section 3.3.5_

---

## Phase 4: Compute Action List

- [ ] **4.1** Identify emails needing new contacts and add `create` actions
  - Compute `all_desired_emails = union(desired_emails[0], desired_emails[1], ...)`.
  - Compute `emails_needing_contacts = all_desired_emails - set(cc_contacts_by_email.keys())`.
  - For each email in `emails_needing_contacts`:
    - Add a `create` action to the action list: `{'type': 'create', 'email': email, 'list_name': None, 'list_uuid': None, 'detail': f'Create contact for {email}', 'sync_index': <first matching index>}`.
    - Set `sync_index` to the index of the first `desired_emails[i]` set containing this email so the create action appears in that sync's notification email.
  - **Corner case**: Multiple PS Members may share an email. The `ps_members_by_email` index naturally collects all such members, which will be used at execution time when calling `CC.create_contact_dict()`.
  - _Depends: 2.5, 3.2_
  - _Spec: section 3.3.6 (step 1)_

- [ ] **4.2** Compute per-list subscribe and unsubscribe actions
  - For each synchronization entry `i`:
    - Get the CC list object from `sync['TARGET CC LIST']`, its UUID from `list['list_id']`, and its name from `sync['target cc list']`.
    - `current_emails = set(sync['TARGET CC LIST']['CONTACTS'].keys())`
    - `to_subscribe = desired_emails[i] - current_emails`
    - `to_unsubscribe = current_emails - desired_emails[i]`
    - For each email in `to_subscribe`: add `{'type': 'subscribe', 'email': email, 'list_name': list_name, 'list_uuid': list_uuid, 'detail': f'Subscribe {email} to {list_name}', 'sync_index': i}`.
    - For each email in `to_unsubscribe`: add `{'type': 'unsubscribe', 'email': email, 'list_name': list_name, 'list_uuid': list_uuid, 'detail': f'Unsubscribe {email} from {list_name}', 'sync_index': i}`.
  - No data is mutated — the action list is the only output.
  - _Depends: 3.1, 4.1_
  - _Spec: section 3.3.6 (step 2)_

- [ ] **4.3** Detect name mismatches and add optional `update_name` actions
  - For each email in `cc_contacts_by_email` where the contact has `'PS MEMBERS'`:
    1. Call `ParishSoft.salutation_for_members(contact['PS MEMBERS'])` to get `(expected_first, expected_last)`.
    2. Strip periods from `expected_first` (e.g., `"T.J."` → `"TJ"`).
    3. Compare `expected_first` with `contact.get('first_name', '')` and `expected_last` with `contact.get('last_name', '')`.
    4. Always log differences at info level (email, old name, expected name).
    5. If `args.update_names` is `True` and a difference exists: add `{'type': 'update_name', 'email': email, 'list_name': None, 'list_uuid': None, 'detail': f'Update name for {email}: ...', 'sync_index': None, 'new_first': expected_first, 'new_last': expected_last, 'old_first': contact.get('first_name', ''), 'old_last': contact.get('last_name', '')}`.
  - For notification purposes, `sync_index` is `None` for name updates (they are not list-specific). Name update actions are logged but not included in per-list notification emails.
  - _Depends: 2.5_
  - _Spec: section 3.3.6 (step 3), 7.4_

- [ ] **4.4** Log deletion candidates
  - For each CC Contact in `cc_contacts_by_email.values()`:
    - Check if `'PS MEMBERS'` is absent or empty → log as deletion candidate.
    - Compute the contact's post-sync list count: `len(contact['list_memberships'])` minus the number of `unsubscribe` actions in the action list for this email. If zero → log as deletion candidate.
  - Log each candidate at info level with email and contact name (`contact.get('first_name', '')`, `contact.get('last_name', '')`).
  - Do NOT add to the action list. Do NOT delete anything.
  - _Depends: 4.2_
  - _Spec: section 3.3.6 (step 4)_

---

## Phase 5: Execute Action List

- [ ] **5.1** Group actions by email and build contact dicts for CC API calls
  - Create an `execute_actions()` function that takes the action list, `cc_contacts_by_email`, `ps_members_by_email`, CC credentials, and `log`.
  - Group actions by email: `actions_by_email = defaultdict(list); for a in actions: actions_by_email[a['email']].append(a)`.
  - For each email:
    - Separate actions into: `creates`, `subscribes`, `unsubscribes`, `name_updates`.
    - **POST dict** (if any creates or subscribes):
      - If email needs a new contact (`creates` non-empty): call `CC.create_contact_dict(email, ps_members_by_email[email], log)`. Set `list_memberships` to the list UUIDs from all `subscribe` actions for this email.
      - If email has an existing contact (`creates` empty, `subscribes` non-empty): build a dict with `email_address` (as `{'address': email}`), `first_name`, `last_name` copied from the existing contact, and `list_memberships` = [UUIDs from subscribe actions only — the CC sign_up_form API adds to existing memberships].
    - **PUT dict** (if any unsubscribes or name_updates):
      - Copy relevant fields from the existing contact: `contact_id`, `email_address` (full object), `first_name`, `last_name`, `list_memberships` (as a copy — do NOT modify the original).
      - Remove all unsubscribe list UUIDs from the copied `list_memberships`.
      - If `name_updates` exist: set `first_name` and `last_name` to the new values from the action.
  - _Depends: 4.1, 4.2, 4.3_
  - _Spec: section 3.3.7_

- [ ] **5.2** Execute API calls with error handling and dry-run support
  - For each email's POST dict (if built): call `CC.create_or_update_contact(post_dict, cc_client_id, cc_access_token, log)`.
  - For each email's PUT dict (if built): call `CC.update_contact_full(put_dict, cc_client_id, cc_access_token, log)`.
  - Wrap each CC API call in `try/except CCAPIError`. On failure:
    - Log the error (including contact email, intended action, HTTP status code, response text from `e.status_code`, `e.response_text`).
    - Continue processing remaining contacts (do NOT exit).
    - Record the failure as `{'email': email, 'action': 'POST'|'PUT', 'error': str(e)}` in a failures list.
  - **Dry-run / no-sync mode**: if `args.dry_run` or `args.no_sync`, log every action that WOULD be performed at info level but do NOT make any CC API calls. Do NOT record failures (there are none).
  - Return the failures list.
  - _Depends: 5.1_
  - _Spec: section 3.3.7, 6.1_

---

## Phase 6: HTML Notification Emails

- [ ] **6.1** Implement HTML email builder function
  - Create a `build_notification_email()` function that takes:
    - CC List name
    - List of actions for this list (each with type, email, detail)
    - List of failed actions for this list (each with email, action, error)
    - List of manually unsubscribed contacts (each with email, PS Member names, PS Member DUIDs) — from `unsubscribed_per_sync[i]`
    - List of contacts removed from this list — `unsubscribe` actions filtered for this list
  - Build a complete HTML email with:
    - **Subject**: `Constant Contact sync update: {CC List Name}`
    - **Header**: CC List name and current timestamp
    - **Summary counts**: contacts created, subscribed, unsubscribed, failures
    - **Actions table**: columns: action type, contact email, contact name
    - **"Manually Unsubscribed Contacts" section**: table with columns: email, PS Member name(s), PS Member DUID(s)
    - **"Contacts Removed from List (in ParishSoft)" section**: table with columns: email, contact name, reason
    - **"Failed Actions" section** (only if failures occurred): table with columns: contact email, intended action, error message
    - **Footer**: "This is an automated message" note
  - Use inline CSS only (email clients strip `<style>` blocks).
  - Tables with borders, alternating row colors (`#f2f2f2` / `#ffffff` or similar).
  - Clear section headings with appropriate font sizes.
  - No images or external resources.
  - Return the (subject, html_body) tuple.
  - _Spec: sections 5.1, 5.2, 5.3_

- [ ] **6.2** Implement per-list notification email sending
  - Create a `send_notification_emails()` function that takes the action list, failures list, `unsubscribed_per_sync`, syncs, and `log`.
  - For each synchronization entry `i`:
    - Filter the action list by `sync_index == i` to get actions for this CC list.
    - If no actions exist for this list, skip it.
    - Filter the failures list for emails that have actions in this sync.
    - Call `build_notification_email()` with the filtered data.
    - For each comma-delimited address string in `sync['notifications']`, split by comma and send to each address using `ECC.send_email(to_addr=addr.strip(), subject=subject, body=html, content_type='text/html', log=log)`.
  - Skip entirely if `args.dry_run` is `True` or `args.no_sync` is `True`.
  - _Depends: 6.1, 5.2_
  - _Spec: section 3.3.8_

- [ ] **6.3** Implement unsubscribed-contacts report email builder
  - Create a `build_unsubscribed_report_email()` function that takes:
    - CC List name
    - PS Member Workgroup name (from `SYNCHRONIZATIONS[i]['source ps member wg']`)
    - List of unsubscribed contact tuples `(email, member_names_str, member_duids_str)` from `unsubscribed_per_sync[i]`
  - Build a complete HTML email with:
    - **Subject**: `Constant Contact unsubscribed contacts report: {CC List Name}`
    - **Header**: CC List name and current timestamp
    - **Explanation paragraph**: "The following ParishSoft Members are in the '{PS Workgroup Name}' workgroup but have manually unsubscribed from Constant Contact. They should be removed from the '{PS Workgroup Name}' workgroup in ParishSoft."
    - **Table**: columns: PS Member name(s), PS Member DUID(s), email address
    - **Footer**: "This is an automated message" note
  - Use the same inline CSS styling as `build_notification_email()` (bordered tables, alternating row colors, clear headings, no images).
  - Return the `(subject, html_body)` tuple.
  - _Spec: sections 3.3.9, 5.4_

- [ ] **6.4** Implement unsubscribed-contacts report sending
  - Create a `send_unsubscribed_report()` function that takes `unsubscribed_per_sync`, syncs, and `log`.
  - Only runs if `args.unsubscribed_report` is `True`.
  - For each synchronization entry `i` where `unsubscribed_per_sync[i]` is non-empty:
    - Call `build_unsubscribed_report_email()` with the CC list name, PS workgroup name, and unsubscribed tuples.
    - If `args.dry_run`:
      - Log a warning that `--unsubscribed-report` was requested but no email will be sent due to `--dry-run`.
      - Log the effective report contents at info level: subject line, CC list name, PS workgroup name, and each unsubscribed member's name, DUID, and email.
      - Do NOT send the email.
    - Otherwise (including `--no-sync` without `--dry-run`): for each comma-delimited address string in `syncs[i]['notifications']`, split by comma and send to each address using `ECC.send_email(to_addr=addr.strip(), subject=subject, body=html, content_type='text/html', log=log)`.
  - This runs **after** all normal sync actions and notification emails have completed.
  - _Depends: 3.2, 6.3_
  - _Spec: section 3.3.9_

---

## Phase 7: Main Orchestration

- [ ] **7.1** Implement `main()` function
  - Wire all components together in the correct order:
    1. `args = setup_cli_args()`
    2. `log = ECC.setup_logging(info=args.verbose, debug=args.debug, logfile=args.logfile, rotate=True, slack_token_filename=None)`
    3. Authenticate CC (task 2.2: `load_client_id` + `get_access_token`); exit early if `--cc-auth-only`
    4. `ECC.setup_email(service_account_json=args.service_account_json, impersonated_user=args.impersonated_user, log=log)`
    5. Load PS data (task 2.1)
    6. Download CC Contacts and Lists (task 2.2, download portion)
    7. Normalize CC emails (task 2.3)
    8. Link CC data and correlate with PS members (task 2.4)
    9. Build script-level indexes (task 2.5)
    10. Resolve desired state (task 3.1)
    11. Filter out unsubscribed (task 3.2)
    12. Compute action list: create actions (4.1), subscribe/unsubscribe (4.2), name mismatches (4.3), deletion candidates (4.4)
    13. Execute action list — skip if `--dry-run` or `--no-sync` (tasks 5.1, 5.2)
    14. Send notification emails — skip if `--dry-run` or `--no-sync` (task 6.2)
    15. Send unsubscribed-contacts report — if `--unsubscribed-report`; log-only if `--dry-run` (task 6.4)
  - _Depends: 1.2, 1.3, 2.1-2.5, 3.1, 3.2, 4.1-4.4, 5.1, 5.2, 6.1-6.4_
  - _Spec: section 3.1_

---

## Phase 8: Edge Cases and Error Handling

- [ ] **8.1** Verify shared-email handling throughout the pipeline
  - The `ps_members_by_email` index (task 2.5) naturally collects all PS members sharing an email. Verify:
    - `execute_actions()` passes the full list from `ps_members_by_email[email]` to `CC.create_contact_dict()` so the contact name is derived from ALL members.
    - Set-diff in task 4.2: if ANY member sharing an email is in a workgroup, that email is in `desired_emails[i]`, so the contact is subscribed. This works because `desired_emails` is built from workgroup membership, not from individual members.
    - `detect_name_mismatches()` uses `contact['PS MEMBERS']` (populated by `link_contacts_to_ps_members`), which already contains all members for that email.
  - _Spec: section 7.1_

- [ ] **8.2** Verify email-change scenarios are handled by the diff
  - Confirm that the set-diff architecture handles these without special code:
    - **Members split emails**: old contact retains some members; new email appears in `emails_needing_contacts` → gets a `create` action. Old contact may get `update_name` action.
    - **Members merge emails**: one contact now maps to multiple members; the other contact loses its PS members → logged as deletion candidate.
  - If any scenario is not handled, add corrective logic. Otherwise, add a comment in the code documenting why it works.
  - _Spec: section 7.2_

- [ ] **8.3** Handle contacts with missing name fields
  - Ensure `detect_name_mismatches()` (task 4.3) and any name-display code use `contact.get('first_name', '')` and `contact.get('last_name', '')` since CC contacts can lack these fields.
  - Ensure the `detail` string in actions handles missing names gracefully.
  - _Depends: 4.3_
  - _Spec: section 3.3.6 (step 3)_

- [ ] **8.4** Ensure bulk data loading failures terminate the script
  - Verify that `CCAPIError` from `CC.api_get_all()` calls (contacts and lists) is NOT caught — it should propagate and terminate the script. Only the `execute_actions()` function catches `CCAPIError` (for individual contact updates).
  - _Depends: 2.2, 5.2_
  - _Spec: section 6.1_

- [ ] **8.5** Ensure config resolution failures terminate the script
  - Verify that if a PS Member Workgroup name or CC List name from `SYNCHRONIZATIONS` is not found, the script logs an error and calls `exit(1)`.
  - _Depends: 3.1_
  - _Spec: section 6.3_
