#!/usr/bin/env python3

# Basic script to create a list of families which have not responded to the
# 2020 spring census. This version is based on a CSV file import, so you will
# need to retrieve the latest file.

import sys
sys.path.insert(1, '../../python/')

import os
import re
import csv
import sqlite3
import datetime

import ECC
import PDSChurch

from helpers import jotform_date_to_date
from helpers import None_date

from pprint import pprint
from pprint import pformat

##############################################################################

masses = [ ('5:30pm Sat.'  , '0530'),
           ('9:00am Sun.'  , '0900'),
           ('11:30am Sun.' , '1130'),
           ('Spanish'      , 'spanish'),
           ('Weekly'       , 'weekday') ]

def convertAttendance(extracted_row, pds_family):
    def _prepare(output_list, mass, extracted_row, pds_family):
        pds_keyword_prefix   = mass[0]
        extracted_field_name = mass[1]

        value = extracted_row[extracted_field_name]

        if value != '' and value != None:
            output_list.append({
                'FID'         : pds_family['FamRecNum'],
                'Envelope ID' : "'" + pds_family['ParKey'].strip(),
                'Name from Jotform' : extracted_row['name'],
                'PDS Family Name' : pds_family['Name'],
                'PDS Keyword' : pds_keyword_prefix + ' Mass - ' + value,
            })

    csvlog = list()
    for mass in masses:
        _prepare(csvlog, mass, extracted_row, pds_family)

    # Save all changes (if there were any)
    return csvlog if len(csvlog) > 0 else None

##############################################################################

def load_input_csv():
    # Hard-coded filename; good enough for this script.
    filename = 'ECC census update - Sheet1.csv'
    csv_rows = list()

    with open(filename, encoding='utf-8') as csvfile:
        csvreader = csv.DictReader(csvfile)
        for row in csvreader:
            csv_rows.append(row)

    print(f"== Loaded {len(csv_rows)} families from CSV")
    return csv_rows

#############################################################################

def extract_csv_data(csv_rows):
    # Use dictionaries to store the extracted results so that later rows will
    # overwrite extracted results from previous rows.  I.e., if a Family
    # submitted more than once, we want their *last* submission).
    csv_families = dict()

    for row in csv_rows:
        fid = int(row['fid'])
        this_family = {
            'fid'     : fid,
            'name'    : row['Household name'].strip(),
            'weekday' : row["How often does any member of your household attend Epiphany's WEEKDAY Mass?"].strip(),
            'spanish' : row["How often does any member of your household attend Epiphany's SPANISH Mass on Thursdays?"].strip(),
            '0530'    : row["How often do MOST members of your household attend Epiphany's WEEKEND Mass(es) as listed i... >> Saturday at 5:30pm   "].strip(),
            '0900'    : row["How often do MOST members of your household attend Epiphany's WEEKEND Mass(es) as listed i... >> <span style=\"font-size: 11.004px; display: inline !important;\">Sunday at 9:00am</span>"].strip(),
            '1130'    : row["How often do MOST members of your household attend Epiphany's WEEKEND Mass(es) as listed i... >> <span style=\"font-size: 11.004px; display: inline !important;\">Sunday at 11:30am</span>"].strip(),
        }
        csv_families[fid] = this_family

    print(f"== Extracted {len(csv_families)} Families  from CSV")
    return csv_families

#----------------------------------------------------------------------------

def generate_family_changelog(csv_family_list, pds_families):
    family_changelog = dict()

    for fid, row in csv_family_list.items():
        if fid in pds_families:
            family_masses = convertAttendance(row, pds_families[fid])
            if family_masses:
                family_changelog[fid] = family_masses

    print(f"== Found {len(family_changelog)} Mass attendees")
    return family_changelog

#----------------------------------------------------------------------------

def write_changelog(pds_families, family_changelog):
    first_fid  = next(iter(family_changelog))
    fieldnames = [ f for f in family_changelog[first_fid][0] ]
    filename   = 'attendancelog.csv'

    num_rows = 0
    with open(filename, "w+", encoding="utf-8", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        num_rows = 1

        # Write the families in a deterministic order
        for fid in sorted(family_changelog):
            family = pds_families[fid]

            for mass in family_changelog[fid]:
                writer.writerow(mass)
                num_rows += 1

    print(f"== Wrote {filename} with {num_rows} data rows")

#############################################################################

# Count each response for each mass
def generate_mass_stats(pds_families, csv_families):
    masses = dict()

    total = 'total'
    for fid in csv_families:
        for key in csv_families[fid]:
            if key == 'name' or key == 'fid':
                continue

            mass_time = key
            if mass_time not in masses:
                masses[mass_time] = dict()

            frequency = csv_families[fid][mass_time]
            if frequency not in masses[mass_time]:
                masses[mass_time][frequency] = 0
            if total not in masses[mass_time]:
                masses[mass_time][total] = 0

            masses[mass_time][frequency] += 1
            masses[mass_time][total]     += 1

    # Emit stats to a file
    filename = 'mass_stats.csv'
    with open(filename, 'w') as f:
        first_key  = next(iter(masses))
        fieldnames = [ k for k in masses[first_key] ]
        fieldnames.append("Mass")
        writer     = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for mass in masses:
            output         = masses[mass]
            output['Mass'] = mass
            writer.writerow(output)

    print(f"== Wrote mass stats to {filename}")

#############################################################################

def main():
    log = ECC.setup_logging(debug=False)

    (_, pds_families,
    pds_members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    log=log)

    csv_rows         = load_input_csv()
    csv_families     = extract_csv_data(csv_rows)
    family_changelog = generate_family_changelog(csv_families, pds_families)
    write_changelog(pds_families, family_changelog)

    generate_mass_stats(pds_families, csv_families)

if __name__ == '__main__':
    main()
