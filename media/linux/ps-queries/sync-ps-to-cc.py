#!/usr/bin/env python3

import html
import os
import sys
import argparse
import logging
import datetime

from collections import defaultdict
from pprint import pformat

# We assume that there is a "ecc-python-modules" sym link in this
# directory that points to the directory with ECC.py and friends.
moddir = '../../../python'
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)
# On MS Windows, git checks out sym links as a file with a single-line
# string containing the name of the file that the sym link points to.
if os.path.isfile(moddir):
    with open(moddir) as fp:
        dir = fp.readlines()
    moddir = os.path.join(os.getcwd(), dir[0])

sys.path.insert(0, moddir)

import ECC
import ParishSoftv2 as ParishSoft
import ConstantContact as CC
from ConstantContact import CCAPIError
from cc_sync_config import SYNCHRONIZATIONS

####################################################################

def setup_cli_args():
    parser = argparse.ArgumentParser(
        description='Synchronize ParishSoft Member Workgroups to Constant Contact Lists')

    parser.add_argument('--ps-api-keyfile',
                        help='File containing the ParishSoft API key')

    parser.add_argument('--cc-client-id',
                        default='constant-contact-client-id.json',
                        help='File containing the Constant Contact Client ID')

    parser.add_argument('--cc-access-token',
                        default='constant-contact-access-token.json',
                        help='File containing the Constant Contact access token')

    parser.add_argument('--service-account-json',
                        default='ecc-emailer-service-account.json',
                        help='File containing the Google service account JSON key')

    parser.add_argument('--impersonated-user',
                        default='no-reply@epiphanycatholicchurch.org',
                        help='Google Workspace user to impersonate via DWD')

    parser.add_argument('--ps-cache-dir',
                        default='datacache',
                        help='Directory to cache ParishSoft data')

    parser.add_argument('--cc-auth-only',
                        default=False,
                        action='store_true',
                        help='Only authenticate to Constant Contact, then exit')

    parser.add_argument('--update-names',
                        default=False,
                        action='store_true',
                        help='Update CC Contact names from PS data when they differ')

    parser.add_argument('--unsubscribed-report',
                        default=False,
                        action='store_true',
                        help='Generate and send standalone report of PS Members whose CC Contacts have unsubscribed')

    parser.add_argument('--no-sync',
                        default=False,
                        action='store_true',
                        help='Skip sync execution and sync notification emails; '
                             'all computation still runs; unlike --dry-run, '
                             'allows --unsubscribed-report to send emails')

    parser.add_argument('--dry-run',
                        default=False,
                        action='store_true',
                        help='Log actions without executing; no emails sent; '
                             'implies --verbose')

    parser.add_argument('--verbose',
                        default=False,
                        action='store_true',
                        help='Emit extra status messages during run')

    parser.add_argument('--debug',
                        default=False,
                        action='store_true',
                        help='Emit debug-level messages; implies --verbose')

    parser.add_argument('--logfile',
                        default='log.txt',
                        help='File for verbose/debug log output')

    args = parser.parse_args()

    # --dry-run implies --verbose
    if args.dry_run:
        args.verbose = True

    # --debug implies --verbose
    if args.debug:
        args.verbose = True

    return args

####################################################################

def resolve_desired_state(member_workgroups, members, cc_lists, log):
    desired_emails = []

    for i, sync in enumerate(SYNCHRONIZATIONS):
        # Resolve PS Member Workgroup
        wg_name = sync['source ps member wg']
        found_wg = False
        for wg in member_workgroups.values():
            if wg['name'] != wg_name:
                continue

            found_wg = True
            emails = set()
            for item in wg['membership']:
                if 'py member duid' not in item:
                    continue

                duid = item['py member duid']
                member = members[duid]
                if member['emailAddress']:
                    emails.add(member['py emailAddresses'][0].lower())
                else:
                    log.warning(f"PS Member {member['py friendly name FL']} "
                                f"(DUID: {member['memberDUID']}) is in WG "
                                f'"{wg_name}" but has no email address')

            log.info(f'Resolved PS Member Workgroup "{wg_name}": '
                     f'{len(emails)} members with email')
            desired_emails.append(emails)
            break

        if not found_wg:
            log.error(f'PS Member Workgroup not found: "{wg_name}"')
            exit(1)

        # Resolve CC List
        list_name = sync['target cc list']
        found_list = False
        for cc_list in cc_lists:
            if cc_list['name'] == list_name:
                sync['TARGET CC LIST'] = cc_list
                log.info(f'Resolved CC List: "{list_name}"')
                found_list = True
                break

        if not found_list:
            log.error(f'CC List not found: "{list_name}"')
            exit(1)

    return desired_emails

####################################################################

def filter_unsubscribed(cc_contacts, desired_emails, ps_members_by_email,
                        log):
    unsubscribed_per_sync = [[] for _ in SYNCHRONIZATIONS]

    for contact in cc_contacts:
        if contact['email_address'].get('permission_to_send') != 'unsubscribed':
            continue

        email = contact['email_address']['address']
        for i in range(len(SYNCHRONIZATIONS)):
            if email not in desired_emails[i]:
                continue

            desired_emails[i].discard(email)

            # Collect PS member info for reporting
            ps_members = ps_members_by_email.get(email, [])
            names = ', '.join(m['py friendly name FL'] for m in ps_members)
            duids = ', '.join(str(m['memberDUID']) for m in ps_members)

            unsubscribed_per_sync[i].append((email, names, duids))
            log.info(f'Filtered unsubscribed contact {email} '
                     f'from desired set for '
                     f'"{SYNCHRONIZATIONS[i]["target cc list"]}"')

    return unsubscribed_per_sync

####################################################################

def compute_create_actions(desired_emails, cc_contacts_by_email):
    actions = []

    all_desired = set()
    for emails in desired_emails:
        all_desired |= emails

    emails_needing_contacts = all_desired - set(cc_contacts_by_email.keys())

    for email in sorted(emails_needing_contacts):
        # Find the first sync entry that wants this email
        sync_index = next(i for i, emails in enumerate(desired_emails)
                         if email in emails)
        actions.append({
            'type':       'create',
            'email':      email,
            'list_name':  None,
            'list_uuid':  None,
            'detail':     f'Create contact for {email}',
            'sync_index': sync_index,
        })

    return actions

####################################################################

def compute_subscribe_unsubscribe_actions(desired_emails):
    actions = []

    for i, sync in enumerate(SYNCHRONIZATIONS):
        cc_list = sync['TARGET CC LIST']
        list_uuid = cc_list['list_id']
        list_name = sync['target cc list']

        current_emails = set(cc_list['CONTACTS'].keys())
        to_subscribe = desired_emails[i] - current_emails
        to_unsubscribe = current_emails - desired_emails[i]

        for email in sorted(to_subscribe):
            actions.append({
                'type':       'subscribe',
                'email':      email,
                'list_name':  list_name,
                'list_uuid':  list_uuid,
                'detail':     f'Subscribe {email} to {list_name}',
                'sync_index': i,
            })

        for email in sorted(to_unsubscribe):
            actions.append({
                'type':       'unsubscribe',
                'email':      email,
                'list_name':  list_name,
                'list_uuid':  list_uuid,
                'detail':     f'Unsubscribe {email} from {list_name}',
                'sync_index': i,
            })

    return actions

####################################################################

def detect_name_mismatches(cc_contacts_by_email, update_names, log):
    actions = []

    for email, contact in cc_contacts_by_email.items():
        if not contact.get('PS MEMBERS'):
            continue

        expected_first, expected_last = \
            ParishSoft.salutation_for_members(contact['PS MEMBERS'])
        # CC rejects periods in names
        expected_first = expected_first.replace('.', '')

        old_first = contact.get('first_name', '')
        old_last = contact.get('last_name', '')

        if expected_first == old_first and expected_last == old_last:
            continue

        log.info(f'Name mismatch for {email}: '
                 f'CC has "{old_first} {old_last}", '
                 f'PS expects "{expected_first} {expected_last}"')

        if update_names:
            actions.append({
                'type':       'update_name',
                'email':      email,
                'list_name':  None,
                'list_uuid':  None,
                'detail':     f'Update name for {email}: '
                              f'"{old_first} {old_last}" -> '
                              f'"{expected_first} {expected_last}"',
                'sync_index': None,
                'new_first':  expected_first,
                'new_last':   expected_last,
                'old_first':  old_first,
                'old_last':   old_last,
            })

    return actions

####################################################################

def log_deletion_candidates(cc_contacts_by_email, actions, log):
    # Count unsubscribe actions per email
    unsub_counts = defaultdict(int)
    for action in actions:
        if action['type'] == 'unsubscribe':
            unsub_counts[action['email']] += 1

    for email, contact in cc_contacts_by_email.items():
        first = contact.get('first_name', '')
        last = contact.get('last_name', '')

        # No PS Members linked
        if not contact.get('PS MEMBERS'):
            log.info(f'Deletion candidate (no PS Members): '
                     f'{email} ({first} {last})')

        # Would have zero list memberships after sync
        current_count = len(contact.get('list_memberships', []))
        post_sync_count = current_count - unsub_counts.get(email, 0)
        if post_sync_count == 0:
            log.info(f'Deletion candidate (no lists after sync): '
                     f'{email} ({first} {last})')

####################################################################

def execute_actions(actions, cc_contacts_by_email, ps_members_by_email,
                    cc_client_id, cc_access_token, dry_run, no_sync, log):
    failures = []

    # Group actions by email
    actions_by_email = defaultdict(list)
    for action in actions:
        actions_by_email[action['email']].append(action)

    for email in sorted(actions_by_email.keys()):
        email_actions = actions_by_email[email]

        creates = [a for a in email_actions if a['type'] == 'create']
        subscribes = [a for a in email_actions if a['type'] == 'subscribe']
        unsubscribes = [a for a in email_actions if a['type'] == 'unsubscribe']
        name_updates = [a for a in email_actions if a['type'] == 'update_name']

        # Build POST dict (create or subscribe via sign_up_form endpoint)
        post_dict = None
        if creates or subscribes:
            if creates:
                post_dict = CC.create_contact_dict(
                    email, ps_members_by_email[email], log)
                post_dict['list_memberships'] = [
                    a['list_uuid'] for a in subscribes
                ]
            else:
                existing = cc_contacts_by_email[email]
                post_dict = {
                    'email_address': {'address': email},
                    'first_name': existing.get('first_name', ''),
                    'last_name': existing.get('last_name', ''),
                    'list_memberships': [
                        a['list_uuid'] for a in subscribes
                    ],
                }

        # Build PUT dict (unsubscribe or name update)
        put_dict = None
        if unsubscribes or name_updates:
            existing = cc_contacts_by_email[email]
            put_dict = {
                'contact_id': existing['contact_id'],
                'email_address': existing['email_address'],
                'first_name': existing.get('first_name', ''),
                'last_name': existing.get('last_name', ''),
                'list_memberships': list(existing.get('list_memberships', [])),
            }

            for a in unsubscribes:
                if a['list_uuid'] in put_dict['list_memberships']:
                    put_dict['list_memberships'].remove(a['list_uuid'])

            if name_updates:
                nu = name_updates[-1]
                put_dict['first_name'] = nu['new_first']
                put_dict['last_name'] = nu['new_last']

        # If both POST and PUT exist, merge newly subscribed lists into
        # the PUT payload so the PUT (which replaces full memberships)
        # does not clobber what the POST just added.
        if post_dict and put_dict:
            for uuid in post_dict.get('list_memberships', []):
                if uuid not in put_dict['list_memberships']:
                    put_dict['list_memberships'].append(uuid)

        # Execute or log
        if dry_run or no_sync:
            for a in email_actions:
                log.info(f"Dry-run/no-sync: {a['detail']}")
            continue

        if post_dict:
            try:
                CC.create_or_update_contact(post_dict, cc_client_id,
                                            cc_access_token, log)
            except CCAPIError as e:
                log.error(f"POST failed for {email}: "
                          f"HTTP {e.status_code}: {e.response_text}")
                failures.append({
                    'email': email,
                    'action': 'POST',
                    'error': str(e),
                })

        if put_dict:
            try:
                CC.update_contact_full(put_dict, cc_client_id,
                                       cc_access_token, log)
            except CCAPIError as e:
                log.error(f"PUT failed for {email}: "
                          f"HTTP {e.status_code}: {e.response_text}")
                failures.append({
                    'email': email,
                    'action': 'PUT',
                    'error': str(e),
                })

    return failures

####################################################################

def build_notification_email(list_name, list_actions, list_failures,
                             unsubscribed, cc_contacts_by_email):
    esc = html.escape
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    subject = f'Constant Contact sync update: {list_name}'

    creates = [a for a in list_actions if a['type'] == 'create']
    subscribes = [a for a in list_actions if a['type'] == 'subscribe']
    unsubscribes = [a for a in list_actions if a['type'] == 'unsubscribe']
    name_updates = [a for a in list_actions if a['type'] == 'update_name']

    tbl = 'border-collapse: collapse; width: 100%; margin-bottom: 20px;'
    th = ('border: 1px solid #dddddd; padding: 8px; text-align: left; '
          'background-color: #4472C4; color: white;')

    def td(row):
        bg = '#f2f2f2' if row % 2 == 0 else '#ffffff'
        return f'border: 1px solid #dddddd; padding: 8px; background-color: {bg};'

    body = (f'<html><body style="font-family: Arial, sans-serif; font-size: 14px;">'
            f'<h2 style="color: #333333;">Constant Contact Sync Update: '
            f'{esc(list_name)}</h2>'
            f'<p style="color: #666666;">Generated: {now}</p>'
            f'<h3>Summary</h3><ul>'
            f'<li>Contacts created: {len(creates)}</li>'
            f'<li>Contacts subscribed: {len(subscribes)}</li>'
            f'<li>Contacts unsubscribed: {len(unsubscribes)}</li>'
            f'<li>Name updates: {len(name_updates)}</li>'
            f'<li>Failures: {len(list_failures)}</li>'
            f'</ul>')

    # Actions table
    if list_actions:
        body += (f'<h3>Actions Performed</h3>'
                 f'<table style="{tbl}"><tr>'
                 f'<th style="{th}">Action</th>'
                 f'<th style="{th}">Email</th>'
                 f'<th style="{th}">Contact Name</th></tr>')
        for idx, action in enumerate(list_actions):
            contact = cc_contacts_by_email.get(action['email'], {})
            first = contact.get('first_name', '')
            last = contact.get('last_name', '')
            name = f'{first} {last}'.strip()
            body += (f'<tr><td style="{td(idx)}">{esc(action["type"])}</td>'
                     f'<td style="{td(idx)}">{esc(action["email"])}</td>'
                     f'<td style="{td(idx)}">{esc(name)}</td></tr>')
        body += '</table>'

    # Manually unsubscribed contacts
    if unsubscribed:
        body += (f'<h3>Manually Unsubscribed Contacts</h3>'
                 f'<p>These contacts have globally unsubscribed from '
                 f'Constant Contact but are still in the corresponding '
                 f'ParishSoft workgroup.</p>'
                 f'<table style="{tbl}"><tr>'
                 f'<th style="{th}">Email</th>'
                 f'<th style="{th}">PS Member Name(s)</th>'
                 f'<th style="{th}">PS Member DUID(s)</th></tr>')
        for idx, (email, names, duids) in enumerate(unsubscribed):
            body += (f'<tr><td style="{td(idx)}">{esc(email)}</td>'
                     f'<td style="{td(idx)}">{esc(names)}</td>'
                     f'<td style="{td(idx)}">{esc(duids)}</td></tr>')
        body += '</table>'

    # Contacts removed from list
    if unsubscribes:
        body += (f'<h3>Contacts Removed from List (in ParishSoft)</h3>'
                 f'<table style="{tbl}"><tr>'
                 f'<th style="{th}">Email</th>'
                 f'<th style="{th}">Contact Name</th>'
                 f'<th style="{th}">Reason</th></tr>')
        for idx, action in enumerate(unsubscribes):
            contact = cc_contacts_by_email.get(action['email'], {})
            first = contact.get('first_name', '')
            last = contact.get('last_name', '')
            name = f'{first} {last}'.strip()
            body += (f'<tr><td style="{td(idx)}">{esc(action["email"])}</td>'
                     f'<td style="{td(idx)}">{esc(name)}</td>'
                     f'<td style="{td(idx)}">Not in PS workgroup</td></tr>')
        body += '</table>'

    # Failed actions
    if list_failures:
        body += (f'<h3 style="color: #cc0000;">Failed Actions</h3>'
                 f'<table style="{tbl}"><tr>'
                 f'<th style="{th}">Email</th>'
                 f'<th style="{th}">Action</th>'
                 f'<th style="{th}">Error</th></tr>')
        for idx, failure in enumerate(list_failures):
            body += (f'<tr><td style="{td(idx)}">{esc(failure["email"])}</td>'
                     f'<td style="{td(idx)}">{esc(failure["action"])}</td>'
                     f'<td style="{td(idx)}">{esc(failure["error"])}</td></tr>')
        body += '</table>'

    body += ('<hr style="border: 1px solid #dddddd; margin-top: 30px;">'
             '<p style="color: #999999; font-size: 12px;">'
             'This is an automated message from the ParishSoft to '
             'Constant Contact synchronization script.</p>'
             '</body></html>')

    return subject, body

####################################################################

def send_notification_emails(actions, failures, unsubscribed_per_sync,
                             cc_contacts_by_email, dry_run, no_sync, log):
    if dry_run or no_sync:
        return

    for i, sync in enumerate(SYNCHRONIZATIONS):
        list_actions = [a for a in actions if a['sync_index'] == i]
        if not list_actions:
            continue

        action_emails = {a['email'] for a in list_actions}
        list_failures = [f for f in failures if f['email'] in action_emails]

        subject, body = build_notification_email(
            sync['target cc list'], list_actions, list_failures,
            unsubscribed_per_sync[i], cc_contacts_by_email)

        for addr_string in sync['notifications']:
            for addr in addr_string.split(','):
                addr = addr.strip()
                if addr:
                    ECC.send_email(to_addr=addr, subject=subject,
                                   body=body, content_type='text/html',
                                   log=log)

####################################################################

def build_unsubscribed_report_email(list_name, wg_name, unsubscribed):
    esc = html.escape
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    subject = f'Constant Contact unsubscribed contacts report: {list_name}'

    tbl = 'border-collapse: collapse; width: 100%; margin-bottom: 20px;'
    th = ('border: 1px solid #dddddd; padding: 8px; text-align: left; '
          'background-color: #4472C4; color: white;')

    def td(row):
        bg = '#f2f2f2' if row % 2 == 0 else '#ffffff'
        return f'border: 1px solid #dddddd; padding: 8px; background-color: {bg};'

    body = (f'<html><body style="font-family: Arial, sans-serif; font-size: 14px;">'
            f'<h2 style="color: #333333;">Constant Contact Unsubscribed '
            f'Contacts Report: {esc(list_name)}</h2>'
            f'<p style="color: #666666;">Generated: {now}</p>'
            f'<p>The following ParishSoft Members are in the '
            f"'{esc(wg_name)}' workgroup but have manually unsubscribed "
            f'from Constant Contact. They should be removed from the '
            f"'{esc(wg_name)}' workgroup in ParishSoft.</p>"
            f'<table style="{tbl}"><tr>'
            f'<th style="{th}">PS Member Name(s)</th>'
            f'<th style="{th}">PS Member DUID(s)</th>'
            f'<th style="{th}">Email</th></tr>')

    for idx, (email, names, duids) in enumerate(unsubscribed):
        body += (f'<tr><td style="{td(idx)}">{esc(names)}</td>'
                 f'<td style="{td(idx)}">{esc(duids)}</td>'
                 f'<td style="{td(idx)}">{esc(email)}</td></tr>')

    body += ('</table>'
             '<hr style="border: 1px solid #dddddd; margin-top: 30px;">'
             '<p style="color: #999999; font-size: 12px;">'
             'This is an automated message from the ParishSoft to '
             'Constant Contact synchronization script.</p>'
             '</body></html>')

    return subject, body

####################################################################

def send_unsubscribed_report(unsubscribed_per_sync, dry_run,
                             unsubscribed_report, log):
    if not unsubscribed_report:
        return

    for i, sync in enumerate(SYNCHRONIZATIONS):
        if not unsubscribed_per_sync[i]:
            continue

        subject, body = build_unsubscribed_report_email(
            sync['target cc list'],
            sync['source ps member wg'],
            unsubscribed_per_sync[i])

        if dry_run:
            log.warning(f'--unsubscribed-report requested but --dry-run '
                        f'is active; not sending email for '
                        f'"{sync["target cc list"]}"')
            log.info(f'Unsubscribed report subject: {subject}')
            log.info(f'CC List: {sync["target cc list"]}')
            log.info(f'PS Workgroup: {sync["source ps member wg"]}')
            for email, names, duids in unsubscribed_per_sync[i]:
                log.info(f'  {names} (DUID: {duids}): {email}')
            continue

        for addr_string in sync['notifications']:
            for addr in addr_string.split(','):
                addr = addr.strip()
                if addr:
                    ECC.send_email(to_addr=addr, subject=subject,
                                   body=body, content_type='text/html',
                                   log=log)

####################################################################

def main():
    args = setup_cli_args()

    log = ECC.setup_logging(info=args.verbose,
                            debug=args.debug,
                            logfile=args.logfile, rotate=True,
                            slack_token_filename=None)

    # Authenticate with Constant Contact (early, so --cc-auth-only
    # does not require PS credentials)
    log.info("Authenticating with Constant Contact...")
    cc_client_id = CC.load_client_id(args.cc_client_id, log)
    cc_access_token = CC.get_access_token(args.cc_access_token,
                                          cc_client_id, log)
    if args.cc_auth_only:
        log.info("Only authenticating to Constant Contact; exiting")
        exit(0)

    # Read the PS API key (deferred until after --cc-auth-only so that
    # --cc-auth-only does not require PS credentials)
    if not args.ps_api_keyfile:
        log.error("--ps-api-keyfile is required")
        exit(1)
    if not os.path.exists(args.ps_api_keyfile):
        log.error(f"ParishSoft API keyfile does not exist: {args.ps_api_keyfile}")
        exit(1)
    with open(args.ps_api_keyfile) as fp:
        args.api_key = fp.read().strip()

    # Set up email
    ECC.setup_email(service_account_json=args.service_account_json,
                    impersonated_user=args.impersonated_user,
                    log=log)

    # Load PS data
    log.info("Loading ParishSoft data...")
    families, members, family_workgroups, member_workgroups, ministries = \
        ParishSoft.load_families_and_members(api_key=args.api_key,
                                             active_only=True,
                                             parishioners_only=False,
                                             cache_dir=args.ps_cache_dir,
                                             log=log)

    # Download CC data (let CCAPIError propagate on failure)
    log.info("Downloading Constant Contact lists...")
    cc_lists = CC.api_get_all(cc_client_id, cc_access_token,
                              'contact_lists', 'lists', log)
    log.info("Downloading Constant Contact contacts...")
    cc_contacts = CC.api_get_all(cc_client_id, cc_access_token,
                                 'contacts', 'contacts', log,
                                 include='list_memberships',
                                 status='all')

    # Normalize CC contact emails to lowercase
    for contact in cc_contacts:
        contact['email_address']['address'] = \
            contact['email_address']['address'].lower()

    # Link CC data structures and correlate with PS Members
    CC.link_cc_data(cc_contacts, [], cc_lists, log)
    CC.link_contacts_to_ps_members(cc_contacts, members, log)

    # Build read-only indexes
    cc_contacts_by_email = {
        contact['email_address']['address']: contact
        for contact in cc_contacts
    }

    ps_members_by_email = defaultdict(list)
    for member in members.values():
        if not member['emailAddress']:
            continue
        email = member['py emailAddresses'][0].lower()
        ps_members_by_email[email].append(member)

    # Resolve desired state per sync entry
    desired_emails = resolve_desired_state(member_workgroups, members,
                                           cc_lists, log)

    # Filter out CC-unsubscribed emails
    unsubscribed_per_sync = filter_unsubscribed(cc_contacts, desired_emails,
                                                ps_members_by_email, log)

    # Compute action list
    actions = []
    actions.extend(compute_create_actions(desired_emails,
                                          cc_contacts_by_email))
    actions.extend(compute_subscribe_unsubscribe_actions(desired_emails))
    actions.extend(detect_name_mismatches(cc_contacts_by_email,
                                          args.update_names, log))

    # Log deletion candidates (not added to action list)
    log_deletion_candidates(cc_contacts_by_email, actions, log)

    # Execute action list
    failures = execute_actions(actions, cc_contacts_by_email,
                               ps_members_by_email,
                               cc_client_id, cc_access_token,
                               args.dry_run, args.no_sync, log)

    # Send notification emails
    send_notification_emails(actions, failures, unsubscribed_per_sync,
                             cc_contacts_by_email,
                             args.dry_run, args.no_sync, log)

    # Send unsubscribed-contacts report
    send_unsubscribed_report(unsubscribed_per_sync,
                             args.dry_run, args.unsubscribed_report, log)

if __name__ == '__main__':
    main()
