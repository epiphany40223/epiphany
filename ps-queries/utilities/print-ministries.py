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
    families, members, family_workgroups, member_worksgroups, ministries = \
        ParishSoft.load_families_and_members(api_key=args.api_key,
                                             cache_dir=args.ps_cache_dir,
                                             active_only=False,
                                             parishioners_only=False,
                                             log=log)

    # Get a de-duplicated list of names (it should be de-duplicated
    # already, but we can do it too, just to be sure).  Then sort them
    # so that they're easy to find / read.
    names = dict()
    for duid, ministry in ministries.items():
        names[ministry['name']] = True

    n = sorted(names.keys())
    for name in n:
        print(name)

main()
