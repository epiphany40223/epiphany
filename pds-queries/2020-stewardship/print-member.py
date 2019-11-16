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

def compute_funding_sum(year, family):
    sum   = 0
    funds = family['funds'][year]
    for fund in funds:
        for item in funds[fund]['history']:
            sum += item['item']['FEAmt']

    return sum

##############################################################################

def main():
    log = ECC.setup_logging(debug=True)

    (pds, families,
     members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    log=log)

    # JMS debug
    squyres = 119353
    print("******** Squyres family")
    pprint(families[squyres])
    print("********** Squyres funding done")
    exit(0)

    jeff_squyres = 119356
    pprint(members[jeff_squyres])

    for year in families[squyres]['funds']:
        sum = compute_funding_sum(year=year, family=families[squyres])
        print("Squyres funding in {year}: ${sum}"
                .format(year=year, sum=sum))

main()
