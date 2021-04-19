#!/usr/bin/env python3

# Compare ECC Python pledge numbers to the "Pledge Drive Status Report.xlsx" report from PDS.

import os
import sys
import csv
import copy
import datetime
import openpyxl

# Load the ECC python modules.  There will be a sym link off this directory.
moddir = os.path.join(os.path.dirname(sys.argv[0]), 'ecc-python-modules')
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)

sys.path.insert(0, moddir)

import ECC
import PDSChurch

pledge_minimum = 0

first_year = 2010
last_year  = datetime.date.today().year

##############################################################################

shorten_fund = {
    'Stewardship Contribution' : 'Stew',
    'Miscellaneous Collection' : 'Misc',
    'ECC Capital Campaign'     : 'Cap',
    'COF Capital Campaign 2021' : 'Cap',
}

def find_family_funding(year, family):
    data = {
        'year'    : year,
        'fid'     : family['FamRecNum'],
        'found'   : False,
        'types'   : dict(),
        'pledged' : 0,
        'q1'      : 0,
        'q2'      : 0,
        'q3'      : 0,
        'q4'      : 0,
        'total'   : 0,
    }

    key      = 'funds'
    pds_year = f"{year-2000:02d}"
    if key not in family or pds_year not in family[key]:
        return data

    funds = family[key][pds_year]
    for fund in funds.keys():

        fund_rate = funds[fund]['fund_rate']
        if fund_rate and fund_rate['FDTotal']:
            data['pledged'] += int(fund_rate['FDTotal'])
            data['found'] = True

        fund_name = funds[fund]['fund']['FundName']
        if fund_name in shorten_fund:
            data['types'][shorten_fund[fund_name]] = True
        else:
            data['types'][fund_name] = True

        for item in funds[fund]['history']:
            amount = item['item']['FEAmt']
            if amount is None:
                # Yes, this happens.  Sigh.
                continue

            quarter = int((item['item']['FEDate'].month-1) / 3) + 1
            data[f'q{quarter}'] += amount
            data['total'] += amount
            data['found'] = True

    return data

##############################################################################

def find_last_gift(families, log):
    key = 'money'
    for fid, family in families.items():
        family[key] = dict()

        last_gift_cy   = 0
        last_gift_type = ''
        for year in range(first_year, last_year+1):
            data = find_family_funding(year, family)
            family[key][year] = data

            if data['total'] > 0:
                last_gift_cy = year
                last_gift_type = ', '.join(data['types'])

        family['last gift CY']   = last_gift_cy
        family['last gift type'] = last_gift_type

##############################################################################

family_statuses = {
    '07PL1'            : 2007,
    '08PL1'            : 2008,
    '09PL1'            : 2009,
    '10PL1'            : 2010,
    '11PL1'            : 2011,
    '12PL1'            : 2012,
    '13PL'             : 2013,
    '14PL'             : 2014,
    '15PL'             : 2015,
    '2016'             : 2016,
    '2017'             : 2017,
    '2018'             : 2018,
    '2019 Stewardsihp' : 2019,
    '2020 Stewardship' : 2020,
    '2021 Stewardship' : 2021,
}

active_keywords  = {
    'Active: Census 2018'      : 2018,
    'Active: Stewardship 2020' : 2019,
    'Active: Stewardship 2021' : 2020,
    'Active: Census 2020'      : 2020,
    'Active: Census 2021'      : 2021,
}

shorten_activity = {
    'Active: Census 2018'      : 'Census',
    'Active: Census 2020'      : 'Census',
    'Active: Census 2021'      : 'Census',
    'Active: Stewardship 2020' : 'Stew',
    'Active: Stewardship 2021' : 'Stew',
}


def find_last_activity(families, log):
    for fid, family in families.items():
        last_activity_cy = 0
        activities       = { year : list() for year in range(first_year, last_year+1) }

        # The "status" field was used to record stewardship (sometimes)
        key = 'status'
        if key in family:
            if family[key] in family_statuses:
                status = family[key]
                year   = family_statuses[status]
                last_activity_cy = max(year, last_activity_cy)

                if year in activities:
                    # This was always stewardship
                    activities[year].append('Stew')

        # Search family keywords for activity
        key = 'keywords'
        if key in family:
            for activity, year in active_keywords.items():
                if activity in family[key]:
                    last_activity_cy = max(year, last_activity_cy)

                    if activity in shorten_activity:
                        activities[year].append(shorten_activity[activity])
                    else:
                        activities[year].append(activity)

        # Search the members of the family for activity in ministries
        # Ministries that start with a number are current ministries.
        # Ministries that start with a letter are no longer active.
        def _search(member, last_activity_cy, key):
            if key not in member:
                return last_activity_cy

            for ministry in member[key]:
                # 1. If the entry is "active" and this is a ministry that starts with a number:
                #    - If there is no end date, assume end date is today
                #    - If there is an end date, assume activity from start to end years
                # 2. Otherwise:
                #    - If there is no end date, we can only assume activity in the start date's year.  :-(
                #    - If there is an end date, assume activity from start to end years
                if ministry['active'] and ministry['Description'][0].isdigit():
                    if ministry['end'] == PDSChurch.date_never:
                        ministry['end'] = datetime.date.today()
                else:
                    if ministry['end'] == PDSChurch.date_never:
                        ministry['end'] = ministry['start']

                for year in range(ministry['start'].year,
                                  ministry['end'].year+1):
                    if year not in activities:
                        continue

                    name = 'Ministry'
                    if name not in activities[year]:
                        activities[year].append(name)
                    last_activity_cy = max(year, last_activity_cy)

            return last_activity_cy

        for member in family['members']:
            last_activity_cy = _search(member, last_activity_cy, 'active_ministries')
            last_activity_cy = _search(member, last_activity_cy, 'inactive_ministries')

        family['activity'] = activities
        family['last activity cy'] = last_activity_cy

##############################################################################

def write_results(families, log):
    filename = 'last-family-activity.csv'
    with open(filename, 'w') as fp:
        fieldnames = ['FID', 'EnvID', 'Name', 'Registered', 'Last gift (CY)', 'Last activity (CY)']
        for year in range(first_year, last_year+1):
            fieldnames.append(f'{year} gifts')
        # The first activities we look for are in 2018
        for year in range(first_year, last_year+1):
            fieldnames.append(f'{year} activities')

        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()

        for fid, family in families.items():
            last_gift_cy   = ''
            last_gift_type = ''
            key = 'last gift CY'
            if key in family:
                last_gift_cy = family[key]
            key = 'last gift type'
            if key in family:
                last_gift_type = family[key]

            if last_gift_cy == 0:
                last_gift_cy = ''

            last_activity = ''
            last_activity_cy = ''
            key = 'last activity cy'
            if key in family:
                last_activity_cy = family['last activity cy']
            if last_activity_cy == 0:
                last_activity_cy = ''

            # 13 June 2021: there's a problem with the Family "Name" field. Some
            # Family names are repeated multiple times.  Use some simple
            # hueristics for remove these multiples.
            def _split(token):
                parts = name.split(f"{token},")
                if parts[0] == name:
                    return name
                if parts[0] == "":
                    return name
                return f"{parts[0]}{token}"

            name = family['Name']
            name = _split("Mrs.")
            name = _split("Mrs")
            name = _split("Mr")
            name = _split("Mr.")
            name = _split("Ms")
            name = _split("Ms.")
            name = _split("Dr")
            name = _split("Drs")
            name = _split("Drs.")
            name = _split("Dr.")
            name = _split("Sr")
            name = _split("Sr.")
            name = _split("Jr")
            name = _split("Jr.")
            name = _split("Fr.")
            name = _split("Deacon")
            name = _split('M/M')
            name = _split('D/M')
            name = _split('M/D')
            name = _split("Mr & Mrs")
            parts = name.split(",")
            if len(parts) > 2 and parts[1] == parts[2]:
                name = f"{parts[0]},{parts[1]}"

            registered = family['DateRegistered']
            if registered == '0000-00-00':
                registered = ''

            item = {
                'FID'                : fid,
                'EnvID'              : f"'{family['ParKey']}",
                'Name'               : name,
                'Registered'         : registered,
                'Last gift (CY)'     : last_gift_cy,
                'Last activity (CY)' : last_activity_cy,
            }

            for year in range(first_year, last_year+1):
                key = 'money'
                if year in family[key]:
                    item[f'{year} gifts'] = ', '.join(family[key][year]['types'].keys())

                key = 'activity'
                if year in family[key]:
                    if len(family[key]) > 0 and len(family[key][year]) > 0:
                        item[f'{year} activities'] = ', '.join(family[key][year])

            writer.writerow(item)

    log.info(f"Wrote {filename}")

##############################################################################

def main():
    log = ECC.setup_logging(debug=False)

    (pds, families,
     members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    active_only=True,
                                                    parishioners_only=True,
                                                    log=log)

    log.info(f"Loaded {len(members)} total Members")
    log.info(f"Loaded {len(families)} total Families")

    #squyres = 119353
    #hall = 549102
    #for year in range(2015, 2021+1):
        #data = find_family_funding(year, families[hall])
        #print(f"Hall {year}: {data}")

    find_last_gift(families, log)
    find_last_activity(families, log)

    write_results(families, log)

main()
