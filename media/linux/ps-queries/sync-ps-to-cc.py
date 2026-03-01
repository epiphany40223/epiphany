#!/usr/bin/env python3

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

    # Phases 5-7 will be implemented in subsequent tasks

if __name__ == '__main__':
    main()
