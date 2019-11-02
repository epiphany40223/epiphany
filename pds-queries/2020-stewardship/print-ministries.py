#!/usr/bin/env python3

# This script was just used to print out the ministries in PDS.  It
# was helpful in creating the Jotform listing all the ministries.

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
import PDS
import PDSChurch

from pprint import pprint
from pprint import pformat

##############################################################################

def main():
    log = ECC.setup_logging(debug=False)

    (pds, families,
     members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    log=log)

    ministries  = PDS.read_table(pds, 'MinType_DB', 'MinDescRec',
                                 columns=['Description'], log=log)

    flipped = dict()
    for key, item in ministries.items():
        flipped[item['Description']] = item

    for key in sorted(flipped):
        print(key)

main()
