#!/usr/bin/env python3

# This script is really just for debugging / reference.  It didn't
# play a part in the sending of emails, etc.  It was edited and run on
# demand just as a help for writing / debugging the other scripts.

import sys
import os

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

def main():
    log = ECC.setup_logging(debug=False)

    (pds, families,
     members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    log=log)

    # This gets *all* the ministries -- even ministries which aren't
    # attached to any Member.
    sql_data = PDSChurch.get_raw_sql_data();
    sql_ministries = sql_data['ministries']

    # Make a dictionary with all the ministry names, and set each
    # entry to False (i.e., no Members found [yet] that are active in
    # this ministry).
    ministries = dict()
    for minid, ministry in sql_ministries.items():
        ministries[ministry['Description']] = False

    for member in members.values():
        key = 'active_ministries'
        if key not in member:
            continue

        for ministry in member[key]:
            if not ministry['active']:
                continue

            desc = ministry['Description']
            ministries[desc] = True

    for name in sorted(ministries):
        active = ministries[name]

        print(f"{name} {'(no active Members)' if not active else ''}")

main()
