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

def compute_funding_sum(year, family):
    sum   = 0
    funds = family['funds'][year]
    for fund in funds:
        for item in funds[fund]['history']:
            sum += item['item']['FEAmt']

    return sum

##############################################################################

def main():
    log = ECC.setup_logging(debug=False)

    (pds, families,
     members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    active_only=False,
                                                    parishioners_only=False,
                                                    log=log)

    num_fam = len(families)
    num_mem = len(members)
    log.info(f"There are {num_fam} families and {num_mem} members")

    #b = PDSChurch.filter_members_on_keywords(members, ['ECC Sheet Music access'])
    #a = PDSChurch.filter_members_on_ministries(members, ['207-Technology Committee'])
    #c = PDSChurch.union_of_member_dicts(a, b)
    #for member in c.values():
    #    print(f"member: {member['Name']}")
    #exit(0)

    mid = 709804 # lucas_osborne
    mid = 547739 # desiree_hoette
    mid = 549105 # ann_hall
    mid = 43689 # carl_working
    mid = 117745 # bill carlisle
    mid = 89818 # rosemary fledkamp
    mid = 646362 # andrew test
    mid = 119356 # jeff squyres
    mid = 6536 # robert adams (1)
    mid = 157822 # robert adams (2)
    mid = 681316 # sarah abel
    pprint(members[mid])
    exit(0)

    fid = 205632 # peariso
    fid = 119353 # squyres
    pprint(families[fid])
    exit(0)

    for year in families[mid]['funds']:
        sum = compute_funding_sum(year=year, family=families[squyres])
        print("MID funding in {year}: ${sum}"
                .format(year=year, sum=sum))

main()
