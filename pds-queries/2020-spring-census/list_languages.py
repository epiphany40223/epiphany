#!/usr/bin/env python3

# Basic script to create a list of families which have not responded to the
# 2020 spring census. This version is based on a CSV file import, so you will
# need to retrieve the latest file.

import sys
sys.path.insert(1, '../../python/')

import os
import re
import csv

import ECC
import PDSChurch

from pprint import pprint
from pprint import pformat

##############################################################################

def load_input_csv():
    filename = 'ECC census update - Sheet1.csv'
    csv_rows = list()

    with open(filename, encoding='utf-8') as csvfile:
        csvreader = csv.DictReader(csvfile)
        for row in csvreader:
            csv_rows.append(row)

    print(f"== Loaded {len(csv_rows)} families from CSV")
    return csv_rows

#############################################################################

# The Additional Language fields unfortunately got screwed up in Jotform.
# Just list them here in order for simplicity.
additional_language_fields = [
    'Additional communication languages',
    'Additional communication languages 2',
    'Additional communication languages 3',
    'Additional communication language',
    'Additional communication languages 4',
    'Additional communication languages 5',
    'Additional communication languages 6',
]

def extract_csv_data(csv_rows):
    def _extract_member(num, row):
        mid    = f'mid{num}'
        suffix = '' if num == 1 else f' {num}'

        return {
            'mid'        : row[mid].strip(),                                                                                    # Index, so no need for compare
            'title'      : row[f'Title{suffix}'].strip(),                                                                       # Simple string compare
            'first'      : row[f'Legal first name{suffix}'].strip(),                                                            # Simple
            'nickname'   : row[f'Nickname (only if different than legal first name){suffix}'].strip(),                          # Simple
            'middle'     : row[f'Middle name{suffix}'].strip(),                                                                 # Simple
            'last'       : row[f'Last name{suffix}'].strip(),                                                                   # Simple
            'suffix'     : row[f'Suffix (if applicable){suffix}'].strip(),                                                      # Simple
            'year'       : row[f'Year of birth{suffix}'].strip(),                                                               # _year_compare
            'email'      : row[f'Preferred email address{suffix}'].strip(),                                                     # _email_compare
            'phone'      : row[f'Cell phone number{suffix}'].strip(),                                                           # _phone_compare
            'sex'        : row[f'Sex{suffix}'].strip(),                                                                         # Simple
            'marital'    : row[f'Marital status{suffix}'].strip(),                                                              # _marital_compare TODO: NEEDS VALUES
            'wedding'    : row[f'Wedding date (if applicable){suffix}'].strip(),                                                # _wedding_compare
            'occupation' : row[f'Occupation (if retired, indicate previous occupation){suffix}'].strip(),                       # _occupation_compare
            'employer'   : row[f'Employer / School attending (Kindergarten thru College, if applicable){suffix}'].strip(),      # _employer_compare
            'primary language'    : row[f'Primary communication language{suffix}'].strip(),
            'secondary languages' : row[additional_language_fields[num - 1]].strip(),
        }

    #------------------------------------------------------------------------

    # Use dictionaries to store the extracted results so that later rows will
    # overwrite extracted results from previous rows.  I.e., if a Family
    # submitted more than once, we want their *last* submission).
    csv_families = dict()
    csv_members  = dict()

    for row in csv_rows:
        fid = int(row['fid'])
        this_family = {
            'fid'     : fid,
            'name'    : row['Household name'].strip(),
            'street'  : row['Street Address'].strip(),
            'street2' : row['Street Address Line 2'].strip(),
            'city'    : row['City'].strip() + ' ' + row['State'].strip(),
            'zip'     : row['Zip Code'].strip(),
            'phone'   : row['Land line phone number (leave blank if you have no land line)'].strip()
        }
        csv_families[fid] = this_family

        # We have up to 7 family members
        for x in range(1, 8):
            mid_field = f'mid{x}'
            if row[mid_field] != '':
                mid = int(row[mid_field])
                this_member = _extract_member(x, row)
                csv_members[mid] = this_member

    print(f"== Extracted {len(csv_families)} Families and {len(csv_members)} Members from CSV")
    return csv_families, csv_members

#############################################################################

def extract_language_hash(pds_language_value):
    # The first language is the primary, the others should be sorted.
    # Convert "Eng" to "English"
    # Convert "American Sign Language" to "ASL"
    languages = [ k.strip().lower() for k in pds_language_value.split('/') ]
    for i, language in enumerate(languages):
        if language == 'eng':
            languages[i] = 'english'
        elif language == 'american sign language':
            languages[i] = 'asl'

    ordered   = [ languages[0] ]
    ordered.extend(sorted(languages[1:]))
    hash      = ':'.join(ordered)

    return hash, languages

#----------------------------------------------------------------------------

# Go through each PDS Member and create the union of all language sets
def create_language_sets(pds_members, log):
    pds_to_ordered = dict()
    ordered        = dict()

    key = 'language'
    for member in pds_members.values():
        if key not in member:
            continue

        pds_language    = member[key]
        hash, languages = extract_language_hash(pds_language)

        # Save this on the Member for comparison later
        member['language_hash'] = hash

        if hash in ordered:
            ordered[hash]['pds_languages'][pds_language] = True
        else:
            ordered[hash] = {
                'hash'          : hash,
                'languages'     : languages,
                'pds_languages' : { pds_language : True }
            }

        pds_to_ordered[pds_language] = {
            'hash'      : hash,
            'languages' : languages,
        }

    return ordered, pds_to_ordered

#############################################################################

def compare_member_languages(csv_members, pds_members,
                            ordered_languages, pds_to_ordered_languages, log):
    output = dict()

    pds_key       = 'language_hash'
    primary_key   = 'primary language'
    secondary_key = 'secondary languages'
    for mid, member in csv_members.items():
        primary_original = member[primary_key].strip()
        primary          = primary_original.lower()

        # Hueristic: split the secondary up by whitespace, slashes, and commas.
        all = list()
        secondary_original = member[secondary_key].strip()
        for a in secondary_original.split():
            for b in a.split('/'):
                for c in b.split(','):
                    val = c.lower()
                    if val != '':
                        all.append(val)
        secondary = ':'.join(all).strip()

        # Assmeble the CSV languages into a hash that we can compare
        csv_hash  = primary
        if secondary != '':
            csv_hash += f":{secondary}"
        if csv_hash == '':
            csv_hash = None

        # Compare to the PDS member
        if mid not in pds_members:
            log.warn(f"MID {mid} for CSV member {member['first']} {member['last']} not in active parishioners; skipping")
            continue

        log.debug(f"CSV Member {member['first']} {member['last']}: CSV hash {csv_hash}")

        pds_member        = pds_members[mid]
        pds_language_hash = None
        pds_language      = ''
        if pds_key in pds_member:
            pds_language_hash = pds_member[pds_key]
            pds_language      = pds_member['language']

        log.debug(f"CSV Member {member['first']} {member['last']}: PDS language hash {pds_language_hash} / {pds_language}")

        # Compare
        if csv_hash != pds_language_hash:
            new_pds_key     = 'New PDS language value'
            new_unknown_key = 'New unknown language value'
            record = {
                'MID'                    : mid,
                'Name'                   : pds_member['email_name'],
                'Old PDS language value' : pds_language,
                new_pds_key              : '',
                new_unknown_key          : '',
            }

            # We have a new set of languages from the CSV data.  Do we have a
            # corresponding PDS value for it?
            if csv_hash in ordered_languages:
                languages = ordered_languages[csv_hash]['pds_languages']
                val       = sorted(languages.keys())[0]
                record[new_pds_key]     = val
            else:
                # Just use the CSV hash; this is going to be human reviewed, so
                # it's probably good enough here
                record[new_unknown_key] = f"{primary_original} {secondary_original}"

            output[mid] = record

    return output

#############################################################################

def write_language_changes(output):
    filename = 'language_changes.csv'
    with open(filename, 'w') as f:
        first      = next(iter(output.keys()))
        fieldnames = [ field for field in output[first] ]
        writer     = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        num_rows   = 1

        # Write the Members in a deterministic order
        for mid in sorted(output):
            member = output[mid]
            writer.writerow(member)
            num_rows += 1

    print(f"== Wrote {filename} with {num_rows} data rows")

#############################################################################

def main():
    log = ECC.setup_logging(debug=False)

    (_, pds_families,
    pds_members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    log=log)

    csv_rows = load_input_csv()
    csv_families, csv_members = extract_csv_data(csv_rows)

    ordered_languages, pds_to_ordered_languages = create_language_sets(pds_members, log)
    output = compare_member_languages(csv_members, pds_members,
                                      ordered_languages, pds_to_ordered_languages, log)

    write_language_changes(output)

if __name__ == '__main__':
    main()
