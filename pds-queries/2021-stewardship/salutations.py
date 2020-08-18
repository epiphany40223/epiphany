#!/usr/bin/env python3

import sys
sys.path.insert(0, '../../python')

import csv

import ECC
import PDSChurch

from pprint import pprint

###########################################################################

def main():
    log = ECC.setup_logging(debug=False)

    (pds, families,
     members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    log=log)

    def _add(data, member):
        last = member['last']
        if last not in data['names']:
            data['names'][last] = list()
        data['names'][last].append(member)

    fids = sorted(families.keys())
    for fid in fids:
        family = families[fid]

        data = {
            'names'   : dict(),
            'hoh'     : list(),
            'spouses' : list(),
        }

        for member in family['members']:
            last = member['last']

            if 'Head' in member['type']:
                data['hoh'].append(member)
                _add(data, member)
            if 'Spouse' in member['type']:
                data['spouses'].append(member)
                _add(data, member)

        salutation = ''
        for last_name in sorted(data['names'].keys()):
            first_names = list()
            for member in data['names'][last_name]:
                if 'nickname' in member and member['nickname'] is not None:
                    first_names.append(member['nickname'])
                elif member['first'] is not None:
                    first_names.append(member['first'])
                else:
                    first_names.append("***UNKNOWN***")
                    log.error("Unknown first name")

            firsts = ' and '.join(first_names)
            if len(salutation) > 0:
                salutation += ' and '
            salutation += f"{firsts} {last_name}"

        data['salutation'] = salutation
        family['data'] = data.copy()

    filename = "data.csv"
    with open(filename, "w") as f:
        w = csv.writer(f)

        # Format of rows
        # Salutation
        # [Name, type]+

        for fid in fids:
            family = families[fid]
            row = list()


            if 'data' not in family:
                continue
            data = family['data']
            if 'salutation' not in data:
                continue

            row.append(data['salutation'])
            for member in data['hoh']:
                row.append(member['email_name'])
                row.append('HoH')
            for member in data['spouses']:
                row.append(member['email_name'])
                row.append('Spouse')

            w.writerow(row)

    print(f"Wrote {filename}")

main()
