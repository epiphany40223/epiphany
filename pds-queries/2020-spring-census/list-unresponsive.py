#!/usr/bin/env python3

# Basic script to create a list of families which have not responded to the
# 2020 spring census. This version is based on a CSV file import, so you will
# need to retrieve the latest file.

import sys
sys.path.insert(0, '../../python')

import csv

import ECC
import PDSChurch

import helpers

from constants import jotform_member_fields

from pprint import pprint
from pprint import pformat

#############################################################################

def read_jotform_results(filename, log):
    log.info("Reading results spreadsheet...")

    fids = dict()
    with open(filename, encoding='utf-8') as csvfile:
        csvreader = csv.DictReader(csvfile)
        for row in csvreader:
            fids[int(row['fid'])] = True

    l = len(fids.keys())
    log.info(f"Found {l} unique Familes in the Jotform results")
    return fids.keys()

#############################################################################

# Of the families in the PDS database, find the ones with:
# - a spouse with a valid email address, or
# - a head of household with a valid email address, or
# - a Famile with a valid email address
def find_pds_census_families(log):
    log.info("Loading PDS database...")

    # Load the PDS database
    (pds, families,
    members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    log=log)

    # Search for Families that match the desired criteria
    # Do it in FID order, just for repeatability
    output_families = list()
    family_only_emails = dict()
    fids = sorted(families)
    for fid in fids:
        f = families[fid]

        # We skipped some Families with too many Members
        if len(f['members']) > len(jotform_member_fields):
            log.debug(f"--- Skipping Familiy {f['Name']} because they have too many Members")
            continue

        have_email = False
        for m in f['members']:
            if helpers.member_is_hoh_or_spouse(m):
                em = PDSChurch.find_any_email(m)
                if em:
                    have_email = True
                    break

        # If we have no email, check the Family record itself for an email
        if not have_email:
            em = PDSChurch.find_any_email(f)
            if f:
                # Sadness.  This looks like a bug in make-and-send-emails.py :-(
                #have_email = True
                log.info(f"Family-only email: {f['Name']} / fid {fid} / env {f['ParKey']}")
                family_only_emails[fid] = f

        # We have no email for the Family.  Get phone numbers.
        if not have_email:
            log.debug(f"--- Have no HoH/Spouse/Family emails for Family {f['Name']} -- skipping")
            continue

        log.debug(f"+++ Family {f['Name']} has an email address")
        output_families.append(f)

    l = len(output_families)
    log.info(f"Found {l} PDS Families with emails")
    l = len(family_only_emails)
    log.info(F"Found {l} PDS Familes with Family-only email")
    return output_families, family_only_emails

#############################################################################

def check_families_only_email_results(families_only_email, fids_replied, log):
    for fid, family in families_only_email.items():
        if fid in fids_replied:
            log.info(f"Happy day! Family-only email FID {fid} has Jotform results!")

#############################################################################

def cross_reference(families_with_email, fids_replied, log):
    not_replied_envelope_ids = list()
    not_replied_fids = list()
    for family in families_with_email:
        fid = family['FamRecNum']

        if fid not in fids_replied:
            log.debug(f"Family did NOT reply: {family['Name']} ({fid} / {family['FamRecNum']})")
            not_replied_envelope_ids.append(family['ParKey'].strip())
            not_replied_fids.append(fid)
        else:
            log.debug(f"Family did reply: {family['Name']} ({fid} / {family['FamRecNum']})")

    # JMS DOUBLE CHECK
    for fid in not_replied_fids:
        if fid in fids_replied:
            log.error(f"ERROR: Found double FID! {fid}")

    return not_replied_envelope_ids

#############################################################################

def write_output_files(not_replied_envelope_ids, filename_base, num_per_file, log):
    ids         = not_replied_envelope_ids.copy()
    file_number = 1
    while len(ids) > 0:
        ids_to_write = ids[:num_per_file]
        if len(ids_to_write) <= 0:
            break

        filename = f'{filename_base}.{file_number}.txt'
        with open(filename, 'w') as f:
            f.write(','.join(ids_to_write) + '\n')
        l = len(ids_to_write)
        log.info(f"Wrote {l} envelope IDs to {filename}")

        ids          = ids[num_per_file:]
        file_number += 1

#############################################################################

def main():
    log = ECC.setup_logging(debug=False)

    # Read in the Jotform results
    filename = 'ECC census update - Sheet1.csv'
    fids_replied = read_jotform_results(filename, log)

    # Read in PDS Families with emails
    families_with_email, families_only_email = find_pds_census_families(log)

    # Check for Family-only emails in the results
    check_families_only_email_results(families_only_email, fids_replied, log)

    # Cross reference the two lists and see what PDS Families with emails
    # did not respond to the census
    not_replied_envelope_ids = cross_reference(families_with_email, fids_replied, log)

    # Write output files
    filename_base = 'unresponsives'
    write_output_files(not_replied_envelope_ids, filename_base, 100, log)

main()
