#!/usr/bin/env python3

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

#--------------------------------------------------------------------------

def _are_members_active(family):
    key = 'active_ministries'
    for member in family['members']:
        if key in member:
            if len(member[key]) > 0:
                return "Yes"

    return "No"

#--------------------------------------------------------------------------

def _have_family_email(family):
    addrs = PDSChurch.family_business_logistics_emails(family)
    if len(addrs) > 0:
        return "Yes"

    return "No"
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

def _did_family_donate(family, year):
    key = 'funds'
    if key not in family:
        return "No"

    year -= 2000
    for pds_year in family[key]:
        if year == int(pds_year):
            print(f"JMS Found family {family['Name']} donated in year {year}")
            for fund in family[key][pds_year]:
                key2 = 'history'
                if key2 in family[key][pds_year][fund] and len(family[key][pds_year][fund][key2]) > 0:
                    return "Yes"

    return "No"

#--------------------------------------------------------------------------

def main():
    log = ECC.setup_logging(debug=False)

    (pds, families,
     members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    active_only=True,
                                                    parishioners_only=True,
                                                    log=log)

    today = datetime.date.today()
    start = datetime.date(year=today.year, month=7, day=1)

    inactive_families = list()

    for family in families.values():
        key = 'keywords'
        active = False
        if key in family:
            for keyword in family[key]:
                if keyword.startswith('Active:'):
                    active = True
                    break

        if not active:
            key = 'DateRegistered'
            if key in family and family[key] != '0000-00-00':
                d = datetime.date.fromisoformat(family[key])
                if d > start:
                    active = False

        if not active:
            print(f"Found inactive family: {family['Name']}")
            inactive_families.append(family)

    print(f"Found {len(inactive_families)} inactive families")
    filename = 'inactive-families.csv'
    with open(filename, "w") as fp:
        fieldnames = ['Name', 'Env ID', 'Phones', 'Registered', 'Have email', 'Members Active in Ministries']
        for year in range(2018, 2023):
            fieldnames.append(f"Donated in {year}")
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()

        for family in inactive_families:
            key = 'DateRegistered'
            reg = ''
            if key in family:
                reg = family[key]

            item = {
                'Name' : family['Name'],
                'Env ID' : f"' {family['ParKey']}",
                'Phones' : _family_phones(family),
                'Registered' : reg,
                'Have email' : _have_family_email(family),
                'Members Active in Ministries' : _are_members_active(family),
            }

            for year in range(2018, 2023):
                donated = _did_family_donate(family, year)
                fieldname = f"Donated in {year}"
                item[fieldname] = donated

            writer.writerow(item)

    print(f"Wrote file: {filename}")

main()
