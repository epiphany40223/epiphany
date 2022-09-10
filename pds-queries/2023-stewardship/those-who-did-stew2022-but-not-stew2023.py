#!/usr/bin/env python3

from email.headerregistry import HeaderRegistry
import os
import sys

# We assume that there is a "ecc-python-modules" sym link in this
# directory that points to the directory with ECC.py and friends.
moddir = os.path.join(os.getcwd(), 'ecc-python-modules')
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)

sys.path.insert(0, moddir)

import datetime
import csv

import ECC
import PDSChurch
import Google
import GoogleAuth

import constants

#--------------------------------------------------------------------------

def _family_phones(family):
    phones = dict()

    types = ['Cell', 'Home']
    for type in types:
        phone = PDSChurch.find_member_phone(family, type)
        if phone:
            phones[phone] = f"{phone} (Family {type})"

    for member in family['members']:
        for type in types:
            phone = PDSChurch.find_member_phone(family, type)
            if phone:
                phones[phone] = f"{phone} ({member['email_name']} {type})"

    return '\n'.join(list(phones.values()))

#--------------------------------------------------------------------------

def setup_google(log):
    apis = {
        'drive' : { 'scope'       : Google.scopes['drive'],
                    'api_name'    : 'drive',
                    'api_version' : 'v3', },
    }
    services = GoogleAuth.service_oauth_login(apis,
                                              app_json=constants.gapp_id,
                                              user_json=constants.guser_cred_file,
                                              log=log)
    google = services['drive']

    #---------------------------------------------------------------------

    def _read_jotform_gsheet(google, gfile_id):
        response = google.files().export(fileId=gfile_id,
                                          mimeType=Google.mime_types['csv']).execute()

        # The ordering of these fields is critical, although the names are not
        fields = constants.jotform_gsheet_columns['prelude']

        csvreader = csv.DictReader(response.decode('utf-8').splitlines(),
                                   fieldnames=fields)
        return csvreader

    #---------------------------------------------------------------------
    # All we need are quick-lookup dictionaries to know if a given FID
    # has submitted or not.
    #
    # So convert the CSV data structures to a quick-lookup dictionary.
    def _convert(csv_data, log):
        output_data = dict()

        first = True
        for row in csv_data:
            # Skip the first / title row
            if first:
                first = False
                continue

            fid = row['fid']
            if fid:
                fid = int(fid)
            else:
                fid = 0
            output_data[fid] = True

        return output_data

    log.info("Loading Jotform submissions Google sheet")
    jotform_csv = _read_jotform_gsheet(google, constants.jotform_gsheet_gfile_id)
    submissions = _convert(jotform_csv, log=log)

    return submissions

#--------------------------------------------------------------------------

def main():
    log = ECC.setup_logging(debug=False)

    log.info("Reading PDS data...")
    (pds, families,
     members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    active_only=True,
                                                    parishioners_only=True,
                                                    log=log)

    log.info("Reading Jotform submissions...")
    submissions = setup_google(log=log)

    key = 'keywords'
    for family in families.values():
        if 'status' not in family:
            continue

        if family['status'] == '2023 Stewardship':
            found = False
            for k in family[key]:
                if k == 'Active: Stewardship 2023':
                    # They did a paper this year -- huzzah!
                    found = True
                    break

            if not found:
                print(f"BAD FAMILY (did stewardship for '22, but not '23): {family['Name']}, env: {family['ParKey']}")

    not_this_year = list()
    for family in families.values():
        if key not in family:
            continue

        found = False
        for keyword in family[key]:
            if keyword == 'Active: Stewardship 2022':
                # They did it last year

                if family['FamRecNum'] in submissions:
                    # They did Jotform this year, too -- huzzah!
                    continue
                if family['status'] == '2023 Stewardship':
                    # They did Jotform this year, too (in paper) -- huzzah!
                    continue

                # Look for a status for this year for a paper submission
                found = False
                for k in family[key]:
                    if k == 'Active: Stewardship 2023':
                        # They did a paper this year -- huzzah!
                        found = True
                        break
                if found:
                    continue

                # They did it last year, but not (yet?) this year
                not_this_year.append(family)
                break

    filename = 'last-year-but-not-this-year.csv'
    with open(filename, "w") as fp:
        fields = ['Name', 'Env ID', 'Phones']
        writer = csv.DictWriter(fp, fieldnames=fields)
        writer.writeheader()

        for family in not_this_year:
            item = {
                'Name' : family['Name'],
                'Env ID' : f"' {family['ParKey']}",
                'Phones' : _family_phones(family),
            }
            writer.writerow(item)

    print(f"Wrote file: {filename}")

main()
