#!/usr/bin/env python3

import sys
sys.path.insert(0, '../../../python')

import ECC
import PDSChurch

import os
import csv
import sqlite3
import argparse

from pprint import pprint
from pprint import pformat

addr_fields = [ 'StreetAddress1',
                'StreetAddress2',
                'city_state',
                'StreetZip' ]

verbose = True
debug   = False
logfile = None

####################################################################
#
# Setup functions
#
####################################################################

def setup_cli_args():
    parser = argparse.ArgumentParser(description='Compare two PDS SQLite files')
    parser.add_argument('files',
                        nargs=2,
                        help='SQLite filenames of PDS data')

    parser.add_argument('--outfile',
                        default='changes.csv',
                        help='Name of CSV output file')

    global verbose
    parser.add_argument('--verbose',
                        action='store_true',
                        default=verbose,
                        help='If enabled, emit extra status messages during run')
    global debug
    parser.add_argument('--debug',
                        action='store_true',
                        default=debug,
                        help='If enabled, emit even more extra status messages during run')
    global logfile
    parser.add_argument('--logfile',
                        default=logfile,
                        help='Store verbose/debug logging to the specified file')

    args = parser.parse_args()

    # --debug implies --verbose
    if args.debug:
        args.verbose = True

    # Make sure the files exist
    for f in args.files:
        if not os.path.exists(f):
            print("ERROR: File not found: {f}".format(f=f))
            exit(1)

    return args

####################################################################

def read_pds(filename, log):
    log.info("Reading {f}...".format(f=filename))

    # We only care about parishioners, but we do want *all* Members --
    # even if they're inactive (because we need to compare
    # active-vs.-inactive, and inactive includes deceased).
    (pds, families,
     members) = PDSChurch.load_families_and_members(filename,
                                                    active_only=False,
                                                    parishioners_only=True,
                                                    log=log)

    pds.connection.close()

    return families, members

####################################################################

# Fields: name, status change (married etc), address, emails
# DONE
# new adds, deaths, deactivations, (maybe more)
def record_change(changes, member, field, value = None) -> None:
    mid = member['MemRecNum']
    if mid not in changes:
        changes[mid] = {
            'mid'    : mid,
            'dob'    : member['DateOfBirth'],
            'name'   : member['full_name'],
            'member' : member,
            'items'  : list()
        }

    changes[mid]['items'].append({
        'description' : field,
        'value'       : value,
    })

#-------------------------------------------------------------------

def make_street_address(family) -> str:
    addr = ''
    global addr_fields
    for field in addr_fields:
        if field in family:
            v = family[field].strip()
        if v == '':
            continue

        if addr:
            addr += ', '
        addr += family[field]

    return addr.strip()

#-------------------------------------------------------------------

def find_now_deceased_members(old_members, cur_members, changes, log) -> None:
    for id, old in old_members.items():
        if id in cur_members:
            cur = cur_members[id]
            if (not old['Inactive'] and not old['Deceased'] and
                cur['Deceased']):
                record_change(changes, cur, 'Now deceased', None)

#-------------------------------------------------------------------

def find_now_inactive_members(old_members, cur_members, changes, log) -> None:
    for id, old in old_members.items():
        if id in cur_members:
            cur = cur_members[id]
            if (not old['Inactive'] and not old['Deceased'] and
                cur['Inactive'] and not cur['Deceased']):
                record_change(changes, cur,
                            'No longer an active member', None)

#-------------------------------------------------------------------

def find_new_members(old_members, cur_members, changes, log) -> None:
    # Look for this two ways:
    # 1. MIDs in current members that aren't in old members
    # 2. Current members that were previously inactive

    for id, cur in cur_members.items():
        if not cur['Inactive']:
            if id not in old_members or old_members[id]['Inactive']:
                record_change(changes, cur, 'New member to the parish', None)

                addr = make_street_address(cur['family'])
                if addr:
                    record_change(changes, cur, 'Address', addr)

                field = 'marital_status'
                if field in cur:
                    record_change(changes, cur, 'Marital status',
                                  cur[field])

                field = 'phones'
                if field in cur:
                    for p in cur[field].values():
                        record_change(changes, cur, 'Phone',
                                    '{num} / {type}'.format(num=p['number'],
                                                    type=p['type']))

                field = 'preferred_emails'
                f2    = 'EMailAddress'
                if field in cur:
                    for pe in cur[field]:
                        record_change(changes, cur, 'Email address',
                                      pe[f2])

#-------------------------------------------------------------------

def _compare_member_phones(old, cur, changes) -> None:
    field      = 'phones'
    old_phones = old[field] if field in old else dict()
    cur_phones = cur[field] if field in cur else dict()

    # For simplicity of the code here, split the checks into three loops (it is
    # probably possible to combine these all into a single pass loop, but the
    # resulting complexity does not seem worth it).

    # Only check to see if a phone number was removed
    for op in old_phones.values():
        old_number = op['number']

        found = False
        for cp in cur_phones.values():
            if old_number == cp['number']:
                found = True
                break

        if not found:
            record_change(changes, cur, 'Phone number removed',
                          old_number)

    # Only check to see if a phone number was added
    for cp in cur_phones.values():
        cur_number = cp['number']

        found = False
        for op in old_phones.values():
            if cur_number == op['number']:
                found = True
                break

        if not found:
            record_change(changes, cur, 'Phone number added',
                          '{num} / {type}'.format(num=cur_number,
                                            type=cp['type']))

    # Only check to see if a phone number changed type
    for op in old_phones.values():
        old_number = op['number']
        for cp in cur_phones.values():
            if old_number == cp['number']:
                # We found the number; see if it changed type
                if op['type'] != cp['type']:
                    record_change(changes, cur, 'Phone type changed from',
                        '{num} -> {type}'.format(num=old_number, type=op['type']))
                    record_change(changes, cur, 'Phone type changed to',
                        '{num} -> {type}'.format(num=old_number, type=cp['type']))

                break

# The email addresses may be in any order between the old and the current
def _compare_member_emails(old, cur, changes) -> None:
    field      = 'preferred_emails'
    old_emails = old[field] if field in old else list()
    cur_emails = cur[field] if field in cur else list()

    field          = 'EMailAddress'
    for oe in old_emails:
        addr = oe[field]

        found = False
        for ce in cur_emails:
            if addr == ce[field]:
                found = True
                break

        if not found:
            record_change(changes, cur, 'Email address removed',
                          addr)

    for ce in cur_emails:
        addr = ce[field]

        found = False
        for oe in old_emails:
            if addr == oe[field]:
                found = True
                break

        if not found:
            record_change(changes, cur, 'Email address added',
                          addr)

# If the member is active in both old and current, look for changes
# in:
#
# - Name
# - Marital status
# - Address
# - Phone
# - Email
#
def find_changed_members(old_members, cur_members, changes, log) -> None:
    for id, cur in cur_members.items():
        if cur['Inactive']:
            continue

        if id not in old_members:
            continue

        old = old_members[id]
        if old['Inactive']:
            continue

        # Compare name
        field = 'full_name'
        if cur[field] != old[field]:
            record_change(changes, cur, 'Old name', old[field])

        # Compare address fields (on the family)
        cur_fam = cur['family']
        old_fam = old['family']

        changed = False
        for field in addr_fields:
            if field not in cur_fam and field not in old_fam:
                continue
            if field in cur_fam and field not in old_fam:
                changed = True
            elif field not in cur_fam and field in old_fam:
                changed = True
            elif cur_fam[field].lower() != old_fam[field].lower():
                changed = True
            if changed:
                break

        if changed:
            old_addr = make_street_address(old_fam)
            cur_addr = make_street_address(cur_fam)
            record_change(changes, cur, 'Address changed from',
                          old_addr)
            record_change(changes, cur, 'to',
                          cur_addr)

        _compare_member_phones(old, cur, changes)
        _compare_member_emails(old, cur, changes)

        # Compare marital status
        field = 'marital_status'
        if field in cur and field in old and cur[field] != old[field]:
            record_change(changes, cur, 'Marital status changed from',
                          old[field])
            record_change(changes, cur, 'to',
                          cur[field])

#-------------------------------------------------------------------

def compare_members(old_members, current_members, log):
    # This could be made to be a single pass through the data,
    # checking for lots of cases in a single loop.  But the code reads
    # significantly simpler if we make multiple passes through the
    # data, looking for each thing we want to report.  The processing
    # overhead is negligible, so let's favor clear code over
    # efficiency.

    changes = dict()
    find_now_deceased_members(old_members, current_members,
                      changes, log)
    find_now_inactive_members(old_members, current_members,
                      changes, log)
    find_new_members(old_members, current_members,
             changes, log)
    find_changed_members(old_members, current_members,
                 changes, log)

    return changes

####################################################################

def output_changes(filename, changes, log):
    with open(filename, 'w') as csvfile:

        fieldnames = ['Unique ID', 'DOB', 'Name',
                      'Description', 'Value' ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for change in changes.values():
            mid    = change['mid']
            dob    = change['dob']
            name   = change['name']
            member = change['member']
            log.info("Changes for {name} (ID {mid}, DOB {dob}):"
                     .format(mid=mid, name=name, dob=dob))

            writer.writerow({
                'Name'     : name,
                'Unique ID': mid,
                'DOB'      : dob,
            })

            for item in change['items']:
                s = '    ' + item['description']
                if 'value' in item and item['value'] is not None:
                    s += ': ' + item['value']
                log.info(s)

                writer.writerow({
                    'Description' : item['description'],
                    'Value'       : item['value'],
                })

####################################################################

def main() -> None:
    args = setup_cli_args()

    log = ECC.setup_logging(info=args.verbose,
                            debug=args.debug,
                            logfile=args.logfile,
                            log_millisecond=False)

    old_families, old_members = read_pds(args.files[0], log)
    cur_families, cur_members = read_pds(args.files[1], log)

    #---------------------------------------------------------------
    # Debug
    for m in cur_members.values():
        if 'Squyres,Jeff' in m['Name']:
            log.debug("**** DEBUG: Jeff Squyres member")
            log.debug(pformat(m))

    log.debug("**** Looking for family...")
    for fid, f in cur_families.items():
        if False and 26561 == fid:
            log.debug("**** DEBUG: Family")
            log.debug(pformat(f))
    #---------------------------------------------------------------

    changes = compare_members(old_members, cur_members, log)
    output_changes(args.outfile, changes, log)

    log.info("All done")

if __name__ == '__main__':
    main()
