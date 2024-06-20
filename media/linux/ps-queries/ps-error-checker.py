#!/usr/bin/env python3

# This script is really just for debugging / reference.  It didn't
# play a part in the sending of emails, etc.  It was edited and run on
# demand just as a help for writing / debugging the other scripts.

import os
import sys
import argparse

# We assume that there is a "ecc-python-modules" sym link in this
# directory that points to the directory with ECC.py and friends.
moddir = os.path.join(os.getcwd(), 'ecc-python-modules')
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)

sys.path.insert(0, moddir)

import ECC
import ParishSoftv2 as ParishSoft

from pprint import pprint
from pprint import pformat

##############################################################################

def _family_in_inactive_group(family):
    key = 'py family group'
    if key in family and family[key] == 'Inactive':
        return True
    return False

##############################################################################

def check_for_families_without_members(families, log):
    key = 'py members'
    for duid, family in families.items():
        if key not in family:
            log.error(f'Family without Members: {family["firstName"]} {family["lastName"]} (DUID: {duid})')

def check_for_active_families_with_inactive_members(families, log):
    key = 'py members'
    for duid, family in families.items():
        if key not in family:
            continue
        if _family_in_inactive_group(family):
            continue

        all_inactive = True
        for member in family[key]:
            if ParishSoft.member_is_active(member):
                all_inactive = False
                break

        if all_inactive:
            log.error(f'Active Family without Active Members: {family["firstName"]} {family["lastName"]} (DUID: {duid})')

def check_for_inactive_families_with_active_members(families, log):
    key = 'py members'
    for duid, family in families.items():
        if key not in family:
            continue
        if not _family_in_inactive_group(family):
            continue

        any_active = False
        for member in family[key]:
            if ParishSoft.member_is_active(member):
                any_active = True
                break

        if any_active:
            log.error(f'Inactive Family with Active Members: {family["firstName"]} {family["lastName"]} (DUID: {duid})')

def check_for_whitespace_data(members, families, log):
    def _check(name, item):
        for key, value in family.items():
            if type(value) is not str:
                continue

            svalue = value.strip()
            if len(svalue) != len(value):
                description = None
                if value[0] == ' ' and value[-1] == ' ':
                    description = 'both prefix and suffix'
                elif value[0] == ' ':
                    description = 'prefix'
                else:
                    description = 'suffix'

                log.error(f'{name}: field {key} has {description} whitespace')

    key = 'py members'
    for duid, family in families.items():
        name = f'Family {family["firstName"]} {family["lastName"]} (DUID: {duid})'
        _check(name, family)

        if key in family:
            for member in family[key]:
                duid = member['memberDUID']
                name = f'Member {member["py friendly name FL"]} (DUID: {duid})'
                _check(name, member)

##############################################################################

def setup_cli():
    parser = argparse.ArgumentParser(description='Do some ParishSoft data consistency checks')

    parser.add_argument('--smtp-auth-file',
                        required=True,
                        help='File containing SMTP AUTH username:password')
    parser.add_argument('--slack-token-filename',
                        help='File containing the Slack bot authorization token')

    parser.add_argument('--ps-api-keyfile',
                        required=True,
                        help='File containing the ParishSoft API key')
    parser.add_argument('--ps-cache-dir',
                        default='.',
                        help='Directory to cache the ParishSoft data')

    parser.add_argument('--debug',
                        action='store_true',
                        default=False,
                        help='If enabled, emit even more extra status messages during run')

    args = parser.parse_args()

    # Read the PS API key
    if not os.path.exists(args.ps_api_keyfile):
        print(f"ERROR: ParishSoft API keyfile does not exist: {args.ps_api_keyfile}")
        exit(1)
    with open(args.ps_api_keyfile) as fp:
        args.api_key = fp.read().strip()

    return args

##############################################################################

def main():
    args = setup_cli()
    log = ECC.setup_logging(debug=args.debug)

    log.info("Loading ParishSoft data...")
    families, members, family_workgroups, member_worksgroups, ministries = \
        ParishSoft.load_families_and_members(api_key=args.api_key,
                                             cache_dir=args.ps_cache_dir,
                                             active_only=False,
                                             parishioners_only=False,
                                             log=log)

    check_for_families_without_members(families, log)
    check_for_active_families_with_inactive_members(families, log)
    check_for_inactive_families_with_active_members(families, log)
    check_for_whitespace_data(members, families, log)

main()
