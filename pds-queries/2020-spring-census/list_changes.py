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

def compare_strings(a, b):
    def _stripped_string(val):
        if val is None:
            return ''
        else:
            return val.strip()

    #-----------------------------------------------

    a = _stripped_string(a)
    b = _stripped_string(b)

    changed = False
    if a != '' and b != '' and a != b:
        changed = True
    if a != '' and b == '':
        changed = True
    if a == '' and b != '':
        changed = True

    return changed, a, b

def compare_ints(a, b):
    changed = False
    if a != None and b != None and a != b:
        changed = True
    if a != None and b == None:
        changed = True
    if a == None and b != None:
        changed = True

    return changed, a, b


#----------------------------------------------------------------------------

def get_phone_number(pds_entity, type):
    # Separate land line phone number into area code and phone number
    if 'phones' in pds_entity:
        for ph in pds_entity['phones']:
            if ph['type'] == type:
                match = re.search("(\(\d\d\d\) \d\d\d-\d\d\d\d)",
                                ph['number'])
                if match:
                    result = match.group(1).strip()
                    return result

    return ''

def get_wedding_date(csv, pds):
    csv_result = jotform_date_to_date(csv)

    key = 'marriage_date'
    if key in pds:
        pds_result = pds[key]
    else:
        pds_result = None_date

    return csv_result, pds_result

def compareFamily(row, pds_family):
    def _compare(output_list, compare, row, pds_family):
        field_name     = compare[0]
        pds_field_name = compare[1]
        csv_field_name = compare[2]

        changed, row_value, pds_value = compare_strings(row[csv_field_name],
                                                        pds_family[pds_field_name])
        if changed:
            changes.append({
                'Envelope ID' : "'" + pds_family['ParKey'],
                'Type'        : 'Family',
                'Name'        : pds_family['Name'],
                'ID'          : pds_family['FamRecNum'],
                'Field'       : field_name,
                'Old'         : pds_value,
                'New'         : row_value,
            })

    #-----------------------------------------------------------------------

    def _phone_compare(output_list, row, pds_family):
        output_field_name = 'Home Phone'
        csv_field_name    = 'phone'

        csv_value         = row[csv_field_name].strip()
        pds_phone         = get_phone_number(pds_family, 'Home')

        changed, pds_phone, csv_value = compare_strings(pds_phone, csv_value)
        if changed:
            changes.append({
                'Envelope ID' : "'" + pds_family['ParKey'],
                'Type'        : 'Family',
                'Name'        : pds_family['Name'],
                'ID'          : pds_family['FamRecNum'],
                'Field'       : output_field_name,
                'Old'         : pds_phone,
                'New'         : csv_value,
            })

    #-----------------------------------------------------------------------

    # First, compare the simple strings
    compares = [ ('Street Address 1', 'StreetAddress1', 'street'  ),
                 ('Street Address 2', 'StreetAddress2', 'street2' ),
                 ('City'            , 'city_state'    , 'city'    ),
                 ('Zip Code'        , 'StreetZip'     , 'zip'     ), ]
    changes = list()
    for compare in compares:
        _compare(changes, compare, row, pds_family)

    # Then compare the phone number
    _phone_compare(changes, row, pds_family)

    # Save all changes (if there were any)
    if len(changes) > 0:
        return {
            'type'    : 'family',
            'fid'     : pds_family['FamRecNum'],
            'changes' : changes,
        }
    else:
        return None

#----------------------------------------------------------------------------

def compareMember(row, pds_member):
    def _general_string_compare(output_list, compare, row, pds_member):
        field_name     = compare[0]
        pds_field_name = compare[1]
        csv_field_name = compare[2]

        if pds_field_name in pds_member:
            pds_value = pds_member[pds_field_name]
        else:
            pds_value = ''

        changed, csv_value, pds_value = compare_strings(row[csv_field_name], pds_value)
        if changed:
            changes.append({
                'Envelope ID' : "'" + pds_member['family']['ParKey'],
                'Type'        : 'Member',
                'Name'        : pds_member['Name'],
                'ID'          : pds_member['MemRecNum'],
                'Field'       : field_name,
                'Old'         : pds_value,
                'New'         : csv_value,
            })


    def _year_compare(output_list, row, pds_member):
        output_field_name = 'Birth Year'
        csv_field_name    = 'year'

        str_value  = row[csv_field_name]
        csv_value  = None if str_value == '' else int(str_value, 10)
        pds_year   = pds_member['YearOfBirth']
        if pds_year < 0:
            pds_year = None

        changed, pds_year, csv_value = compare_ints(pds_year, csv_value)
        if changed:
            changes.append({
                'Envelope ID' : "'" + pds_member['family']['ParKey'],
                'Type'        : 'Member',
                'Name'        : pds_member['Name'],
                'ID'          : pds_member['MemRecNum'],
                'Field'       : output_field_name,
                'Old'         : pds_year,
                'New'         : csv_value,
            })


    def _email_compare(output_list, row, pds_member):
        #Check if email is already present, and mark as preferred if not already so
        output_field_name = 'Preferred Email'
        csv_field_name    = 'email'

        csv_value  = row[csv_field_name].strip()
        pds_emails = PDSChurch.find_any_email(pds_member)
        preferred  = pds_emails[0] if len(pds_emails) > 0 else None

        changed, preferred, csv_value = compare_strings(preferred, csv_value)
        if changed:
            changes.append({
                'Envelope ID' : "'" + pds_member['family']['ParKey'],
                'Type'        : 'Member',
                'Name'        : pds_member['Name'],
                'ID'          : pds_member['MemRecNum'],
                'Field'       : output_field_name,
                'Old'         : preferred,
                'New'         : csv_value,
            })

    def _wedding_compare(output_list, row, pds_member):
        #CSV has MM/DD/YYYY, vs PDS' YYYY/MM/DD
        output_field_name = 'Wedding Date'
        csv_field_name    = 'wedding'

        csv_value, pds_value = get_wedding_date(row[csv_field_name], pds_member)
        if pds_value == None_date:
            pds_value = ''

        # There seems to be a lot of errors in the CSV with marriage dates
        # <1900. I'm guessing this is a result of improper PDS date conversion
        # to the input of the Jotform.  So just ignore any CSV dates <1900.
        if csv_value.year >= 1900 and csv_value != pds_value:
            changes.append({
                'Envelope ID' : "'" + pds_member['family']['ParKey'],
                'Type'        : 'Member',
                'Name'        : pds_member['Name'],
                'ID'          : pds_member['MemRecNum'],
                'Field'       : output_field_name,
                'Old'         : f'{pds_value}',
                'New'         : f'{csv_value}',
            })

    def _phone_compare(output_list, row, pds_family):
        output_field_name = 'Cell Phone'
        csv_field_name    = 'phone'

        csv_value         = row[csv_field_name].strip()
        pds_phone = get_phone_number(pds_member, 'Cell')

        changed, pds_phone, csv_value = compare_strings(pds_phone, csv_value)
        if changed:
            changes.append({
                'Envelope ID' : "'" + pds_member['family']['ParKey'],
                'Type'        : 'Member',
                'Name'        : pds_member['Name'],
                'ID'          : pds_member['MemRecNum'],
                'Field'       : output_field_name,
                'Old'         : pds_phone,
                'New'         : csv_value,
            })



    # First, compare the simple strings
    compares = [ ('Title'           , 'prefix'           , 'title'     ),
                 ('First Name'      , 'first'            , 'first'     ),
                 ('Middle Name'     , 'middle'           , 'middle'    ),
                 ('Last Name'       , 'last'             , 'last'      ),
                 ('Nickname'        , 'nickname'         , 'nickname'  ),
                 ('Suffix'          , 'suffix'           , 'suffix'    ),
                 ('Gender'          , 'Gender'           , 'sex'       ),
                 ('Marital Status'  , 'marital_status'   , 'marital'   ),
                 ('Occupation'      , 'occupation'       , 'occupation'),
                 ('Employer'        , 'Location'         , 'employer'  ), ]
    changes = list()
    for compare in compares:
        _general_string_compare(changes, compare, row, pds_member)

    #Then, do the more complex comparisons
    _year_compare(changes, row, pds_member)
    _email_compare(changes, row, pds_member)
    _wedding_compare(changes, row, pds_member)
    _phone_compare(changes, row, pds_member)





    if len(changes) > 0:
        return {
            'type'    : 'member',
            'mid'     : pds_member['MemRecNum'],
            'changes' : changes,
        }
    else:
        return None

##############################################################################

def fixWeddingDate(value):
    date = value.split('-', 2)
    if len(date)<2 : return ""
    else:
        fixedDate = f"{date[2]}-{date[0]}-{date[1]}"
        return fixedDate

##############################################################################

def catchMissingYear(value):
    if (value==""): return False
    else: return True

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

#----------------------------------------------------------------------------

def generate_family_changelog(csv_family_list, pds_families):
    family_changelog = dict()

    for fid, row in csv_family_list.items():
        if fid in pds_families:
            family_changes = compareFamily(row, pds_families[fid])
            if family_changes:
                family_changelog[fid] = family_changes

    print(f"== Found {len(family_changelog)} Family changes")
    return family_changelog

#----------------------------------------------------------------------------

def generate_member_changelog(csv_member_list, pds_members):
    member_changelog = dict()

    for mid, row in csv_member_list.items():
        if mid in pds_members:
            member_changes = compareMember(row, pds_members[mid])
            if member_changes:
                member_changelog[mid] = member_changes

    print(f"== Found {len(member_changelog)} Member changes")
    return member_changelog

#----------------------------------------------------------------------------

def write_changelogs(pds_families, pds_members,
                     family_changelog, member_changelog):
    fieldnames = ['Envelope ID', 'Type', 'Name', 'ID', 'Field', 'Old', 'New']
    filename   = 'changelog.csv'

    num_rows = 0
    with open(filename, "w+", encoding="utf-8", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        num_rows = 1

        # Write the families in a deterministic order
        fids = sorted(pds_families)
        for fid in fids:
            family = pds_families[fid]
            emitted = False

            if fid in family_changelog:
                row = family_changelog[fid]
                for change in row['changes']:
                    writer.writerow(change)
                    emitted = True
                    num_rows += 1

            # If there are any changes to the Members of this Family, write them
            # out now.
            for member in family['members']:
                mid = member['MemRecNum']
                if mid in member_changelog:
                    row = member_changelog[mid]
                    for change in row['changes']:
                        writer.writerow(change)
                        emitted = True
                        num_rows += 1

            # If we wrote any part of a Family, emit a blank line
            if emitted:
                writer.writerow({})

    print(f"== Wrote {filename} with {num_rows} data rows")

#############################################################################

def main():
    log = ECC.setup_logging(debug=False)

    (_, pds_families,
    pds_members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    log=log)

    csv_rows = load_input_csv()

    csv_families, csv_members = extract_csv_data(csv_rows)

    family_changelog = generate_family_changelog(csv_families, pds_families)
    member_changelog = generate_member_changelog(csv_members, pds_members)

    write_changelogs(pds_families, pds_members,
                     family_changelog, member_changelog)

if __name__ == '__main__':
    main()
