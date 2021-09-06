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

def print_keywords(name, entities, sql_keywords):
    keywords = dict()
    for sql_keyword in sql_keywords.values():
        keywords[sql_keyword['Description']] = False

    for entity in entities.values():
        key = 'keywords'
        if key not in entity:
            continue

        for keyword in entity[key]:
            keywords[keyword] = True

    print(f"{name} keywords:")
    for name in sorted(keywords):
        active = keywords[name]
        print(f"{name} {'(no Members)' if not active else ''}")

def main():
    log = ECC.setup_logging(debug=False)

    (pds, families,
     members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    log=log)

    # This gets *all* the keywords -- even keywords which aren't
    # attached to any Member or Family.
    sql_data = PDSChurch.get_raw_sql_data();

    print_keywords("Member", members, sql_data['member keywords'])
    print("")
    print_keywords("Family", families, sql_data['family keywords'])

main()
