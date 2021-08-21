#!/usr/bin/env python3

# This script is really just for debugging / reference.  It didn't
# play a part in the sending of emails, etc.  It was edited and run on
# demand just as a help for writing / debugging the other scripts.

import traceback
import datetime
import calendar
import argparse
import smtplib
import sqlite3
import uuid
import time
import csv
import sys
import os
import re

# We assume that there is a "ecc-python-modules" sym link in this directory that points to the directory with ECC.py and friends.
moddir = os.path.join(os.getcwd(), 'ecc-python-modules')
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)

sys.path.insert(0, moddir)

import ECC
import PDSChurch

from pprint import pprint
from pprint import pformat

##############################################################################

def process_families(families, log):
    target_members = list()

    num_families_with_no_email  = 0
    num_families_with_no_adults = 0

    fids = sorted(families)
    for fid in fids:
        f = families[fid]

        log.info("=== Family: {name}".format(name=f['Name']))

        have_email = False
        for m in f['members']:
            if PDSChurch.is_member_hoh_or_spouse(m):
                em = PDSChurch.find_any_email(m)
                if em:
                    have_email = True
                    break

        # If we have an email address for this Family, move on
        if have_email:
            continue

        # We have no email for the Family.  Get phone numbers.
        log.info("    *** Have no HoH/Spouse emails for Family {family}"
                 .format(family=f['Name']))
        num_families_with_no_email += 1

        found = False
        for m in f['members']:
            if not PDSChurch.is_member_hoh_or_spouse(m):
                continue

            # Here's someone we want
            found = True
            target_members.append(m)

        if not found:
            log.warn("   *** NO SPOUSE/HoH FAMILY MEMBERS!!")
            num_families_with_no_adults += 1

    #######################################################################

    print(f"Number of Families with no Spouse/HoH email: {num_families_with_no_email}")
    print(f"Number of Families with no Spouse/HoH:       {num_families_with_no_adults}")
    print(f"Resulting number of Members:                 {len(target_members)}")

    #######################################################################

    # Private utility routine, used below
    def _get_phones(envid, phones, entity):
        key = 'phones'
        if key not in entity or len(entity[key]) == 0:
            return phones

        for ph in entity[key]:
            if ph['type'] in exclude_phone_types:
                continue

            row = {
                'EnvID' : envid,
                'First' : 'Family',
                'Last'  : family_last,
                'Phone' : ph['number'],
                'Type'  : ph['type'],
            }
            if fid not in phones:
                phones[fid] = dict()
            phones[fid][ph['number']] = row

        return phones

    #######################################################################

    filename = 'parishioner-families-with-no-emails.csv'
    if os.path.exists(filename):
        os.unlink(filename)

    fields              = ['EnvID', 'First', 'Last', 'Phone', 'Type']
    exclude_phone_types = ['Emergency', 'Work', 'Dig Page']
    phones              = dict()

    num_members_with_no_phones = 0
    families_with_no_phones    = dict()

    for m in target_members:
        fid = m['family']['FamRecNum']
        family_last = m['family']['Name'].split(',')[0]

        # Get phones from the Family
        family = families[fid]
        envid  = f"' {family['ParKey']}"
        phones = _get_phones(envid, phones, family)

        # Get phones from the Members
        phones = _get_phones(envid, phones, m)

    print(f"Resulting number of Families with usable phones: {len(phones)}")

    #######################################################################

    # Write out the resulting CSV
    with open(filename, 'w') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for fid, family_phones in phones.items():
            for data in family_phones.values():
                writer.writerow(data)

    print(f"Wrote filename {filename}")

##############################################################################

def main():
    log = ECC.setup_logging(debug=False)

    (pds, families,
     members) = PDSChurch.load_families_and_members(filename="pdschurch.sqlite3",
                                                    parishioners_only=True,
                                                    log=log)
    process_families(families, log)

main()
