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

    ministries = dict()
    for member in members.values():
        key = 'active_ministries'
        if key not in member:
            continue

        for ministry in member[key]:
            desc   = ministry['Description']
            active = ministry['active']

            if desc in ministries:
                continue

            ministries[desc] = {
                'desc'   : desc,
                'active' : active,
            }

    for name in sorted(ministries):
        ministry = ministries[name]
        active   = ministry['active']

        print(f"{name} {'(inactive)' if not active else ''}")

main()
