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

family_bases = [
{ 'old': r'Z:\\2015-Pictorial-Directory-Photos\\',
  'new' : 'G:\\Shared drives\\ECC Public (Z)\\PICTURES\\2015 Pictorial Directory',
  'local_prefix' : '2015 Pictorial Directory' },
{ 'old': r'Z:\\PSA submitted photos\\',
  'new' : 'G:\\Shared drives\\ECC Public (Z)\\PICTURES\\PSA submitted photos',
  'local_prefix' : 'PSA submitted photos' },
{ 'old': r'Z:\\Pictures\\Newcomer\'s Brunch Jan 2012\\',
  'new' : 'G:\\Shared drives\\ECC Public (Z)\\PICTURES\\Newcomer\'s Brunch Jan 2012',
  'local_prefix' : 'Newcomer\'s Brunch Jan 2012' },
{ 'old': r'Z:\\Pictures\\Newcomer\'s brunch 4-2011\\',
  'new' : 'G:\\Shared drives\\ECC Public (Z)\\PICTURES\\Newcomer\'s brunch 4-2011',
  'local_prefix' : 'Newcomer\'s brunch 4-2011' },
{ 'old': r'Z:\\Pictures\\Newcomer\'s brunch 7-2011\\',
  'new' : 'G:\\Shared drives\\ECC Public (Z)\\PICTURES\\Newcomer\'s brunch 7-2011',
  'local_prefix' : 'Newcomer\'s brunch 7-2011' },
{ 'old': r'',
  'new' : 'G:\\Shared drives\\ECC Public (Z)\\PICTURES\\2007 Pictorial Directory',
  'local_prefix' : '2007 Pictorial Directory' },
]

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

def check_family_picturefiles(families, args, log):
    def _doit(old, new, local_prefix):
        print("Checking: {file}".format(file=f[field]))
        match_str = r'^{base}(.+)$'.format(base=old)
        parts = re.match(match_str, str(f[field]))
        if not parts:
            return False

        filename = parts.group(1)
        print("Found filename: " + filename)

        # If the file exists in the picture dir, update it
        local_filename = filename.replace('\\', '/')
        local_abs_filename = os.path.join(args.picture_dir, local_prefix, local_filename)
        print("Checking local filename: " + local_abs_filename)
        if os.path.exists(local_abs_filename):
            print("==> Good filename.  Will update.")
            record['filename'] = "{new}\\{filename}".format(new=new, filename=filename)
            return True
        else:
            print("--> Bad filename.  Skipped")
            return False

    to_fix = list()
    skipped = list()
    field = 'PictureFile'

    for f in families.values():
        if field not in f:
            continue

        record = {
            'fid' : f['FamRecNum'],
            'name' : f['Name'],
            'filename' : str(f[field])
        }

        for base in family_bases:
            ret = _doit(base['old'], base['new'], base['local_prefix'])
            if ret:
                to_fix.append(record)
                break
        if not ret:
            skipped.append(record)

    return to_fix, skipped

####################################################################

def output_results(to_fix, skipped, log):
    def _do_write(filename, items):
        with open(filename, 'w') as csvfile:
            fieldnames = ['FID', 'Name', 'Filename']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for item in items:
                fid      = item['fid']
                name     = item['name']
                filename = item['filename']
                log.info("New filename: {fid} {name}: {filename}"
                        .format(fid=fid,
                                name=name,
                                filename=filename))

                writer.writerow({
                    'FID'          : fid,
                    'Name'         : name,
                    'Filename'     : filename,
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

    to_fix, skipped = check_family_picturefiles(families, args, log)
    output_results(to_fix, skipped, log)

    log.info("All done")

if __name__ == '__main__':
    main()
