#!/usr/bin/env python3

import sys
sys.path.insert(0, '../../python')

import ECC
import PDSChurch

import re
import os
import csv
import typing
import pathlib
import sqlite3
import argparse

from typing import List, Dict

from pprint import pprint
from pprint import pformat

addr_fields = [ 'StreetAddress1',
                'StreetAddress2',
                'city_state',
                'StreetZip' ]

verbose = True
debug   = False
logfile = None

old_member_base = r'Z:\\2015-Pictorial-Directory-Photos'
new_member_base = "G:\\Shared drives\\ECC Public (Z)\\PICTURES\\2015 Pictorial Directory"

####################################################################
#
# Setup functions
#
####################################################################

def setup_cli_args():
    parser = argparse.ArgumentParser(description='Look for bad picture files')
    parser.add_argument('--sqlite3',
                        required=True,
                        help='SQLite filename with PDS data')

    parser.add_argument('--picture-dir',
                        required=True,
                        help='Directory where picture files are located')

    parser.add_argument('--outfile',
                        default='changes.csv',
                        help='Name of CSV output file')

    global verbose
    parser.add_argument('--verbose',
                        action='store_true',
                        default=verbose,
                        help='If enabled, emit extra status messages during run')
    global debug
    parser.add_argument('--debug',
                        action='store_true',
                        default=debug,
                        help='If enabled, emit even more extra status messages during run')
    global logfile
    parser.add_argument('--logfile',
                        default=logfile,
                        help='Store verbose/debug logging to the specified file')

    args = parser.parse_args()

    # --debug implies --verbose
    if args.debug:
        args.verbose = True

    # Make sure the files exist
    if not os.path.exists(args.sqlite3):
        print("ERROR: File not found: {f}".format(f=f))
        exit(1)

    return args

####################################################################

def read_pds(filename: str, log):
    log.info("Reading {f}...".format(f=filename))

    # We only care about parishioners, but we do want *all* Members --
    # even if they're inactive (because we need to compare
    # active-vs.-inactive, and inactive includes deceased).
    (pds, families,
     members) = PDSChurch.load_families_and_members(filename,
                                                    active_only=False,
                                                    parishioners_only=True,
                                                    log=log)

    pds.connection.close()

    return families, members

#-------------------------------------------------------------------

def check_member_picturefiles(members, args, log):
    to_fix = list()
    skipped = list()

    match_str = r'^{base}\\(.+)$'.format(base=old_member_base)
    prog = re.compile(r'^Z:\\2015-Pictorial-Directory-Photos\\(.+)$')
    field = 'PictureFile'

    for m in members.values():
        if field not in m:
            continue

        record = {
            'mid' : m['MemRecNum'],
            'name' : m['full_name'],
            'filename' : str(m[field])
        }

        # Low hanging fruit: just look for files starting with:
        # Z:\2015-Pictorial-Directory-Photos
        # and replace them with a prefix of:
        # G:\Shared drives\ECC Public (Z)\PICTURES\2015 Pictorial Directory
        print("Checking: {file}".format(file=m[field]))
        parts = prog.match(str(m[field]))
        if not parts:
            skipped.append(record)
            continue

        filename = parts.group(1)
        print("Found filename: " + filename)

        # If the file exists in the picture dir, update it
        local_filename = os.path.join(args.picture_dir, filename)
        print("Checking local filename: " + local_filename)
        if os.path.exists(local_filename):
            print("==> Good filename.  Will update.")
            record['filename'] = os.path.join(new_member_base, filename)
            to_fix.append(record)
        else:
            print("--> Bad filename.  Skipped")
            skipped.append(record)

    return to_fix, skipped

####################################################################

def output_results(to_fix, skipped, log):
    def _do_write(filename, items):
        with open(filename, 'w') as csvfile:
            fieldnames = ['MID', 'Name', 'Filename']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for item in items:
                mid      = item['mid']
                name     = item['name']
                filename = item['filename']
                log.info("New filename: {mid} {name}: {filename}"
                        .format(mid=mid,
                                name=name,
                                filename=filename))

                writer.writerow({
                    'MID'          : mid,
                    'Name'         : name,
                    'Filename' : filename,
                })

    _do_write("to_fix.csv", to_fix)
    _do_write("skipped.csv", skipped)

####################################################################

def main() -> None:
    args = setup_cli_args()

    log = ECC.setup_logging(info=args.verbose,
                            debug=args.debug,
                            logfile=args.logfile,
                            log_millisecond=False)

    families, members = read_pds(args.sqlite3, log)

    #---------------------------------------------------------------

    to_fix, skipped = check_member_picturefiles(members, args, log)
    output_results(to_fix, skipped, log)

    log.info("All done")

if __name__ == '__main__':
    main()
