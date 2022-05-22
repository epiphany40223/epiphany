#!/usr/bin/env python3

import argparse
import csv
import sys
import os
import re

# Load the ECC python modules.  There will be a sym link off this directory.
moddir = os.path.join(os.path.dirname(sys.argv[0]), 'ecc-python-modules')
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)

sys.path.insert(0, moddir)

import ECC
import PDSChurch

#################################################################################

def find_names(family, last, firsts, log):
    key = 'nickname'

    log.debug(f"Checking family {last} / {firsts}")

    for member in family['members']:
        if member['last'].lower() != last:
            continue

        for first in firsts:
            log.debug(f"FIRST: {member['first'].lower()}, NICK: {member['nickname']}")
            if member['first'].lower() == first:
                log.debug(f"Found first: {member['first']}")
                return True
            if key in member and member[key] and member[key].lower() == first:
                log.debug(f"Found nick: {member[key]}")
                return True

    return False

#################################################################################

def find_photo_filename(args, num):
    # Try 2 forms:
    # - dsc_9325.JPG
    #   and
    # - dsc_9325touchup.JPG
    def _look(filename):
        path = os.path.join(args.local_photos_dir,
                            filename)
        if os.path.exists(path):
            return filename
        return None

    num = int(num)
    out = _look(f'dsc_{num:04}.JPG')
    if out:
        return out
    out = _look(f'dsc_{num:04}touchup.JPG')
    return out

#################################################################################

def setup_args():
    parser = argparse.ArgumentParser(description='Process some photos')

    parser.add_argument('--logfile',
                        default='logfile.txt',
                        help='Output filename for logfile')
    parser.add_argument('--pds',
                        default='pdschurch.sqlite3',
                        help='Filename of PDS SQLite3 database')

    parser.add_argument('--tsv',
                        required=True,
                        help='tab-separated file of families/photo IDs')
    parser.add_argument('--windows-dir-base',
                        default=r'G:\Shared drives\ECC Public (Z)\2021 Pictorial Directory\PDS\Photos',
                        help='Windows base dir for all the photos')
    parser.add_argument('--local-photos-dir',
                        default='photos/DP Images resized',
                        help='Local dir where photos live')

    args = parser.parse_args()

    return args

#################################################################################

def main():
    global families, members

    args = setup_args()

    try:
        os.unlink(args.logfile)
    except:
        pass
    log = ECC.setup_logging(debug=False, logfile=args.logfile)

    # Read in all the PDS data
    log.info("Reading PDS data...")
    (pds, families,
     members) = PDSChurch.load_families_and_members(filename=args.pds,
                                                    parishioners_only=False,
                                                    log=log)

    # Read TSV
    log.info(f"Reading {args.tsv}...")
    photo_data = list()
    with open(args.tsv) as fp:
        reader = csv.DictReader(fp, dialect='excel-tab')

        for row in reader:
            photo_data.append(row)

    # Find the local and windows filenames
    for row in photo_data:
        num = int(row['@dp image reference number'])
        num = f'{num:04}'

        local_filename = find_photo_filename(args, num)
        if not local_filename:
            log.error("Could not find filename for photo {num} -- skipping")
            continue

        windows_filename = f'{args.windows_dir_base}\{local_filename}'
        row['pds filename'] = windows_filename

    # Match the family name with a FID
    fidkey = 'fid'
    lns = 'last_name_salutation'
    for row in photo_data:
        last = row['Last Name'].lower()
        firsts = row['husband wife'].lower()
        num = int(row['@dp image reference number'])
        env = row['envelope'].strip()
        notes = row['notes'].strip()

        num = f'{num:04}'

        # Manually put in the spreadsheet by JMS
        if notes == 'inactive':
            continue

        if '&' in firsts:
            firsts = [ x.strip() for x in firsts.split('&') ]
        elif ',' in firsts:
            firsts = [ x.strip() for x in firsts.split(',') ]
        else:
            firsts = [ firsts ]

        already_matched = False
        for fid, family in families.items():
            parts = family['Name'].split(",")
            family_last = parts[0].strip().lower()

            # See if we have an override in the "envelope" column
            # Manually put in spreadsheet by JMS
            if len(env) > 0:
                parkey = family['ParKey'].strip()
                if parkey == env:
                    log.debug("FOUND MATCH")
                    row[fidkey] = fid

                # Env ID's are unique; no need to continue looping
                # through the PDS families
                continue

            if family_last == last or lns in family and family[lns] and family[lns].lower() == last:
                pass
            else:
                continue

            log.debug(f"Found family with matching last name: {family_last}")

            if len(env) == 0:
                found = find_names(family, last, firsts, log)
                if not found:
                    continue

            if not already_matched:
                log.debug("FOUND MATCH")
                row[fidkey] = fid
            else:
                log.warning(f"Found match for \"{last} / {firsts}\" for more than one FID: photo {num}")
            already_matched = True

        if fidkey not in row:
            log.error(f"Did not find Family for {last} {firsts}, photo {num}")

    found = 0
    for row in photo_data:
        if fidkey in row:
            found += 1
    log.info(f"Matched {found} out of {len(photo_data)} families")

    filename = "pds-import-family-pictures.csv"
    with open(filename, "w") as fp:
        fields = [ 'FID', 'Envelope ID', 'Family name', 'Photo' ]
        writer = csv.DictWriter(fp, fields)
        writer.writeheader()

        for row in photo_data:
            if fidkey not in row:
                continue

            fid = row[fidkey]
            family = families[fid]

            out = {
                "FID" : fid,
                'Envelope ID' : "'" + family['ParKey'],
                'Family name' : family['Name'],
                'Photo' : row['pds filename'],
            }
            writer.writerow(out)

    log.info(f"Wrote output: {filename}")

main()
