#!/usr/bin/env python3

import sys
sys.path.insert(0, '../python')

import csv

import ECC
import PDSChurch

from pprint import pprint

##############################################################################

def _is_member_good(member):
    if (('preferred_emails' not in member or
         len(member['preferred_emails']) == 0) and
        ('non_preferred_emails' not in member or
         len(member['non_preferred_emails']) == 0)):
        return False

    return True

def find_bad_families(families):
    bad_families = dict()

    for fid, f in families.items():
        count = 0
        bad_members = list()
        for m in f['members']:
            type = m['type']
            if 'Head' in type or 'Spouse' in type:
                count += 1
                if not _is_member_good(m):
                    fid = f['FamRecNum']
                    bad_members.append(m)

        if len(bad_members) == count:
            bad_families[fid] = list()
            for m in bad_members:
                bad_families[fid].append({
                    'family' : f,
                    'member' : m,
                })

    return bad_families

#-----------------------------------------------------------------------------

# If we don't do this wonky value for the Family ID, Excel will strip
# off the leading zeros.  :-(
def _pkey(env_id):
    return "' {0}".format(str(env_id).strip())

def report(bad_families):
    # Output a CSV for the families that we don't have HoH/Spouse emails
    filename = 'families_who_dont_have_hoh_or_spouse_emails.csv'
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['Family ID', 'Family Name',
                      'Relevant Member', 'Member Type', 'Family Email']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames,
                                quoting=csv.QUOTE_ALL)
        writer.writeheader()

        num_members = 0
        for fid in sorted(bad_families):
            entry_list = bad_families[fid]
            for entry in entry_list:
                num_members = num_members + 1

                f = entry['family']
                m = entry['member']

                family_email = PDSChurch.find_preferred_email(f)

                env_id = _pkey(f['ParKey'])
                writer.writerow({'Family ID'      : env_id,
                                 'Family Name'    : f['Name'],
                                 'Relevant Member': m['Name'],
                                 'Member Type'    : m['type'],
                                 'Family Email'   : family_email})

    print("Wrote out {num_families} families ({num_members} members) in {filename}"
          .format(num_families=len(bad_families),
                  num_members=num_members,
                  filename=filename))

##############################################################################

def main():
    log = ECC.setup_logging(debug=True)

    (pds, families,
     members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    log=log)

    bad_families = find_bad_families(families)
    report(bad_families)

main()
