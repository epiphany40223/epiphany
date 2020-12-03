#!/usr/bin/env python3

# This script is really just for debugging / reference.  It didn't
# play a part in the sending of emails, etc.  It was edited and run on
# demand just as a help for writing / debugging the other scripts.

import sys
sys.path.insert(0, '../../python')

import traceback
import datetime
import calendar
import argparse
import smtplib
import sqlite3
import uuid
import time
import csv
import os
import re

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
