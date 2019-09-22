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

old_member_base = "Z:\\2015-Pictorial-Directory-Photos\\"
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

def check_picturefiles(items: Dict, args: Dict, type: str, log) -> Dict:
    count_filenames = 0
    count_good      = 0
    count_bad       = 0

    bad = list()
    for item in items.values():
        field = 'PictureFile'
        if field not in item:
            continue

        count_filenames = count_filenames + 1

        # Filenames will be pathlib.PureWindowsPath objects
        f = item[field]
        log.debug("Got file: {}".format(f))

        # If there's a Z: in the front, remove it
        if f.drive == 'Z:':
            log.debug("Parts of file: {}".format(pformat(f.parts)))
            f = pathlib.PureWindowsPath(*f.parts[1:])
            log.debug("Stripped Z: {}".format(f))

        # Convert this to a file name on the local filesystem
        log.debug("Parts: {}".format(f.parts))
        native_filename = os.path.join(args.picture_dir, *list(f.parts))
        if os.path.exists(native_filename):
            log.debug("Exists! {}".format(native_filename))
            count_good = count_good + 1
        else:
            log.warn("Does not exist: {}".format(native_filename))
            bad.append(item)
            count_bad = count_bad + 1

    log.info("Results of scanning {type}:".format(type=type))
    log.info("Total items:               {n}".format(n=len(items)))
    log.info("Items with filenames:      {n}".format(n=count_filenames))
    log.info("Items with good filenames: {n}".format(n=count_good))
    log.info("Items with bad filenames:  {n}".format(n=count_bad))

    return bad

def check_member_picturefiles(members: Dict, args: Dict, bad: List,
        log) -> None:
    results = check_picturefiles(members, args, 'members', log)
    for item in results:
        bad.append({
            'type'     : 'Member',
            'id'       : item['MemRecNum'],
            'name'     : item['full_name'],
            'filename' : item['PictureFile'],
        })

def check_family_picturefiles(families: Dict, args: Dict, bad: List,
        log) -> None:
    results = check_picturefiles(families, args, 'families', log)
    for item in results:
        bad.append({
            'type'     : 'Family',
            'id'       : item['FamRecNum'],
            'name'     : item['Name'],
            'filename' : item['PictureFile'],
        })

####################################################################

def output_results(filename: str, bad: List, log):
    with open(filename, 'w') as csvfile:

        fieldnames = ['Type', 'Unique ID', 'Name',
                      'Bad filename']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for item in bad:
            type     = item['type']
            id       = item['id']
            name     = item['name']
            filename = item['filename']
            log.info("Bad filename: {type} {id} {name}: {filename}"
                    .format(type=type,
                            id=id,
                            name=name,
                            filename=filename))

            writer.writerow({
                'Type'         : type,
                'Unique ID'    : id,
                'Name'         : name,
                'Bad filename' : filename,
            })

####################################################################

def main() -> None:
    args = setup_cli_args()

    log = ECC.setup_logging(info=args.verbose,
                            debug=args.debug,
                            logfile=args.logfile,
                            log_millisecond=False)

    families, members = read_pds(args.sqlite3, log)

    #---------------------------------------------------------------

    bad = list()
    check_member_picturefiles(members,  args, bad, log)
    check_family_picturefiles(families, args, bad, log)

    output_results(args.outfile, bad, log)

    log.info("All done")

if __name__ == '__main__':
    main()
