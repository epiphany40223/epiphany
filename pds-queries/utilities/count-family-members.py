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

def main():
    log = ECC.setup_logging(debug=False)

    (pds, families,
     members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    log=log)

    counts = dict()
    for fid, family in families.items():
        count = len(family['members'])
        if count not in counts:
            counts[count] = 0
        counts[count] += 1

        if count == 7:
            print(f"7-member family: {family['Name']}, fid {family['FamRecNum']}")

    max = 0
    for count in counts:
        if count > max:
            max = count

    for i in range(max + 1):
        if i in counts:
            print(f"Count {i}: {counts[i]}")

main()
