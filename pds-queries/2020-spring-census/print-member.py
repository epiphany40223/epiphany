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
    log = ECC.setup_logging(debug=False)

    (_, families,
     members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    log=log)

    #test_family_fid = 646359
    #andrew_test_mid = 646362
    #pprint(members[andrew_test_mid])
    #exit(0)

    if False:
        squyres_fid = 119353
        print("******** Squyres Family")
        pprint(families[squyres_fid])
        exit(0)

    # HJC debug
    cabral_fid = 199783
    print("******** Cabral Family")
    pprint(families[cabral_fid])
    print("********** Cabral funding done")
    #exit(0)

    harrison_mid = 199805
    pprint(members[harrison_mid])
    exit(0)

main()
