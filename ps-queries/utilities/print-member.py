#!/usr/bin/env python3

# This script is really just for debugging / reference.  It didn't
# play a part in the sending of emails, etc.  It was edited and run on
# demand just as a help for writing / debugging the other scripts.

import os
import sys
import argparse

# We assume that there is a "ecc-python-modules" sym link in this
# directory that points to the directory with ECC.py and friends.
moddir = os.path.join(os.getcwd(), 'ecc-python-modules')
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)

sys.path.insert(0, moddir)

import ECC
import ParishSoftv2 as ParishSoft

from pprint import pprint
from pprint import pformat

##############################################################################

def setup_cli():
    parser = argparse.ArgumentParser(description='Print a ParishSoft Member')
    parser.add_argument('--debug',
                        action='store_true',
                        default=False,
                        help='If enabled, emit even more extra status messages during run')
    parser.add_argument('--ps-api-keyfile',
                        default='parishsoft-api-key.txt',
                        help='File containing the ParishSoft API key')
    parser.add_argument('--ps-cache-dir',
                        default='.',
                        help='Directory to cache the ParishSoft data')

    args = parser.parse_args()

    # Read the PS API key
    if not os.path.exists(args.ps_api_keyfile):
        print(f"ERROR: ParishSoft API keyfile does not exist: {args.ps_api_keyfile}")
        exit(1)
    with open(args.ps_api_keyfile) as fp:
        args.api_key = fp.read().strip()

    return args

##############################################################################

def main():
    args = setup_cli()
    log = ECC.setup_logging(debug=args.debug)

    log.info("Loading ParishSoft data...")
    families, members, family_workgroups, member_workgroups, ministries = \
        ParishSoft.load_families_and_members(api_key=args.api_key,
                                             cache_dir=args.ps_cache_dir,
                                             active_only=False,
                                             parishioners_only=False,
                                             load_contributions="1971-01-01",
                                             log=log)

    num_fam = len(families)
    num_mem = len(members)
    log.info(f"There are {num_fam} families and {num_mem} members")

    mid = 1137297 # tracy squyres
    mid = 1139348 # kathryn squyres
    mid = 1139349 # kaitlyn squyres
    mid = 1140048 # tracey zoeller
    mid = 1139251 # Jill Zamiska
    mid = 1141967 # Andrew Test
    mid = 1136734 # erin mchugh
    mid = 1137296 # jeff squyres

    pprint(members[mid], width=200)
    exit(0)

    fid = 156881 # squyres
    fid = 156657 # zoeller

    pprint(families[fid])
    exit(0)

main()
