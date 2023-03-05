#!/usr/bin/env python3

import sqlite3
import sys
import csv
import os

# Load the ECC python modules.  There will be a sym link off this directory.
moddir = os.path.join(os.path.dirname(sys.argv[0]), 'ecc-python-modules')
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)

sys.path.insert(0, moddir)

import ECC
import PDSChurch

from pprint import pprint

#------------------------------------------------------------------------

log = ECC.setup_logging(debug=False)

log.info("Reading SQLite3 database...")
(pds, families,
 members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                parishioners_only=True,
                                                log=log)

log.info("Comparing business logistics / spouse+hoh family emails...")
diffs = list()
for family in families.values():
    addrs1 = sorted(PDSChurch.family_business_logistics_emails(family))

    temp = dict()
    spouse, hoh, _ = PDSChurch.filter_members_on_hohspouse(family['members'])
    for member in [spouse, hoh]:
        if member:
            for addr in PDSChurch.find_any_email(member):
                temp[addr] = True
    addrs2 = sorted(list(temp.keys()))

    if addrs1 != addrs2:
        diffs.append({
            'buslog' : addrs1,
            'sh' : addrs2,
        })

print(f"Found {len(diffs)} differences")
for diff in diffs:
    pprint(diff)

filename = "diff.csv"
with open(filename, "w") as fp:
    writer = csv.writer(fp)

    # Write all the cases with zero business logistics keywords
    for diff in diffs:
        if len(diff['buslog']) == 0:
            val = ', '.join(diff['sh'])
            writer.writerow(['', val])

    # Write all the cases with zero HoH/spouse email address
    for diff in diffs:
        if len(diff['sh']) == 0:
            val = ', '.join(diff['buslog'])
            writer.writerow([val, ''])

    # Write all the rest of the cases
    for diff in diffs:
        if len(diff['sh']) > 0 and len(diff['buslog']) > 0:
            val1 = ', '.join(diff['buslog'])
            val2 = ', '.join(diff['sh'])
            writer.writerow([val1, val2])

print(f"Wrote {filename}")
