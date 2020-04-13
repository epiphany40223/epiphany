#!/usr/bin/env python3

# Basic script to create a list of families which have not responded to the
# 2020 spring census. This version is based on a CSV file import, so you will
# need to retrieve the latest file.

import sys
sys.path.insert(0, '../../python')

import os
import csv
import re
import sqlite3

import ECC
import PDSChurch

from pprint import pprint
from pprint import pformat

#############################################################################

def main():
    log = ECC.setup_logging(debug=False)

    (pds, families,
    members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    log=log)

    families_replied = list()
    with open('ECC census update - Sheet1.csv', encoding='utf-8') as csvfile:
        csvreader = csv.DictReader(csvfile)
        for row in csvreader:
            families_replied.append(int(row['fid']))

    #pprint(families_replied)

    n=0

    not_replied = list()
    for family in families.values():
        fid = family['FamRecNum']

        if fid not in families_replied:
            log.info(f"Family did NOT reply: {family['Name']} ({fid} / {family['FamRecNum']})")
            not_replied.append(family['ParKey'].strip())
            n = n+1
        else:
            log.info(f"Family did reply: {family['Name']} ({fid} / {family['FamRecNum']})")
    log.info(f"Number of unresponsives: {n}")

    with open("unresponsives.txt", "w+") as f:
        i = 0
        for fid in not_replied:
            if(i<100):
                f.write(f"{fid},")
                i=i+1
            else:
                f.write(f"{fid}\n")
                i=0 
main()
