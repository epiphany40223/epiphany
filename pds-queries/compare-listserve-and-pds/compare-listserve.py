#!/usr/bin/env python3

import sys
sys.path.insert(0, '../python')

import csv
import os
import re

import ECC
import PDSChurch

from pprint import pprint

##############################################################################

def csv_parkey(member):
    return "' {}".format(str(member['family']['ParKey'].strip()))

##############################################################################

# Each line of the listserve will be one of three formats:
#
# Name <addr>
# "Name" <addr>
# addr
#
def read_listserve(name):
    filename = name + '.txt'
    if not os.path.exists(filename):
        print("Could not find file: {file} -- skipping"
              .format(file=filename))
        return

    with open(filename, 'r') as f:
        raw_lines = f.readlines()

    exp_name_email    = re.compile('^(.*)\s+<(.+)>\n$')
    exp_remove_quotes = re.compile('^"(.+)"$')

    listserve_members = dict()
    for line in raw_lines:
        result = exp_name_email.match(line)

        if result:
            # If we had either of the name/email forms, extract
            name = result.group(1)
            addr = result.group(2).lower()

            # If there were quotes, strip them
            result = exp_remove_quotes.match(name)
            if result:
                name = result.group(1)

        else:
            # Otherwise, it was a pure email address
            name = ''
            addr = line.strip()

        listserve_members[addr] = {
            'name' : name,
            'addr' : addr,
        }

    return listserve_members

##############################################################################

def _find_ministry_members(target_ministry_name,
                           all_members, ministry_members):
    print("Checking for ministry: {}".format(target_ministry_name));
    for mid, member in all_members.items():
        key = 'active_ministries'
        if key not in member:
            continue

        for ministry in member[key]:
            if ministry['Description'] == target_ministry_name:
                if mid not in ministry_members:
                    ministry_members[mid] = member

def read_ministry(ministry, all_members):
    ministry_members = dict()

    print(type(ministry))

    if type(ministry) is list:
        ministries = ministry
        for ministry in ministries:
            _find_ministry_members(ministry, all_members, ministry_members)
    else:
        _find_ministry_members(ministry, all_members, ministry_members)

    return ministry_members

##############################################################################

# Report:
#
# 1. Listserve members who match PDS Members who are in the ministry
# 2. Listserve members who match PDS Members who are NOT in the
#    ministry
# 3. Listserve members who do not match PDS Members
# 4. PDS Members who are in the ministry who were not found in the
#    listserve
#
def compare_members(all_members,
                    listserve, listserve_members,
                    ministry, ministry_members):
    # Entries in "matched" are both in the listserver and in the PDS
    # ministry
    matched = list()

    # Entries in "listserve_not_in_ministry" are listserver email
    # addresses found in PDS, but who are not in the ministry.
    listserve_not_in_ministry = list()

    keys = ['preferred_emails', 'non_preferred_emails']

    # Go through each active ministry member, and see if one of its
    # email addresses is in the listserve.
    for mid, member in all_members.items():
        for key in keys:
            for entry in member[key]:
                member_addr = entry['EMailAddress']
                if member_addr in listserve_members:
                    # We found a Member that has an email address in
                    # the listserve.  Is this

                    to_save = {
                        'listserve' : listserve_members[member_addr],
                        'ministry'  : member,
                    }

                    # Is this Member in the correct ministry?
                    found = False
                    for m in member['active_ministries']:
                        if type(ministry) is list:
                            for m1 in ministry:
                                if m['Description'] == m1:
                                    found = True
                                    break
                        else:
                            if m['Description'] == ministry:
                                found = True;

                    if found:
                        print("MATCHED: {} vs {}".format(m['Description'],
                                                         member['active_ministries']))
                        matched.append(to_save)
                    else:
                        listserve_not_in_ministry.append(to_save)

                    # Delete these entries from listserve_members and
                    # ministry_members so that we know we found them
                    del listserve_members[member_addr]
                    # We may have already deleted this Member from the
                    # list of members (because multiple email
                    # addresses from a single Member may be in the
                    # listserve)
                    if mid in ministry_members:
                        del ministry_members[mid]


    # At this point:
    # - Anyone left is listserve_members was not in PDS
    # - Anyone left in pds_ministry_members was not in the listserve

    output_filename = listserve + "-comparison.csv"
    # Now write it all out
    with open(output_filename, 'w', newline='') as csvfile:
        if type(ministry) is list:
            ministry_name = ', '.join(ministry)
        else:
            ministry_name = ministry
        last_field = 'In {name} PDS ministry'.format(name=ministry_name)
        fieldnames = ['Listserve name',
                      'Listserve email address',
                      'PDS Member name',
                      'PDS Member envelope ID',
                      last_field]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames,
                                quoting=csv.QUOTE_ALL)
        writer.writeheader()

        # First, write out listserve members who are in PDS and in the
        # ministry
        for entry in matched:
            le  = entry['listserve']
            mem = entry['ministry']
            writer.writerow({'Listserve name'          : le['name'],
                             'Listserve email address' : le['addr'],
                             'PDS Member name'         : mem['Name'],
                             'PDS Member envelope ID'  : csv_parkey(mem),
                             last_field                : 'YES'
            })

        # Next, write out listserve members who are in PDS, but not in
        # the ministry
        for entry in listserve_not_in_ministry:
            le  = entry['listserve']
            mem = entry['ministry']
            writer.writerow({'Listserve name'          : le['name'],
                             'Listserve email address' : le['addr'],
                             'PDS Member name'         : mem['Name'],
                             'PDS Member envelope ID'  : csv_parkey(mem),
                             last_field                : 'NO'
            })

        # Next, write out listserve members who are not in PDS
        for name, entry in listserve_members.items():
            writer.writerow({'Listserve name'          : entry['name'],
                             'Listserve email address' : entry['addr'],
                             'PDS Member envelope ID'  : '',
                             last_field                : 'NO'
            })

        # Finally, write out PDS ministry members who were not found
        # in the listserve
        for mid, m in ministry_members.items():
            writer.writerow({'Listserve name'          : "",
                             'Listserve email address' : "",
                             'PDS Member name'         : "",
                             'PDS Member name'         : m['Name'],
                             'PDS Member envelope ID'  : csv_parkey(m),
                             last_field                : 'YES'
            })

##############################################################################

def main():
    log = ECC.setup_logging(debug=True)

    (pds, families,
     members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    parishioners_only=False,
                                                    log=log)

    lists = [ ( 'musicians', [ '38-Instrumentalists & Cantors',
                               '29-Worship&Music Support Team' ]),
              ( 'advocates-for-the-common-good',
                '70- Advocates for Common Good' ),
              ( 'bell-ringers', '32-Bell Choir ' ),
              ( 'breadmakers', '22-Bread Baking Ministry' ),
              ( 'choir', '31-Adult Choir' ),
              ( 'cup-and-plate-coordinators', '35-Communion Min. Coordinator' ),
              ( 'EBM', '72-Epiphany Backside Misistry' ),
              ( 'EYB', '41-Epiphany Youth Band' ),
              ( 'junior-high-parents', '84-Youth Grp(Jr High)Adult Vol' ),
              ( 'MOE', '62-Men of Epiphany' ),
              ( 'sages', '63-Sages (for 50 yrs. +)' ),
              ( 'seamstresses', '57-Healing Blanket Ministry' ),
              ( 'senior-high-parents', '88-Youth Grp(Sr Hi) Adult Vol' ),
              ( 'social-resp-steering-committee', 'L-Social Resp Steering Comm'),
              ( 'ten-percent-committee', '78-Ten Percent Committee' ),
              ( 'worship-committee', 'L-Worship Committee' ),
              ( 'young-adults', '90-Young Adult Ministry' ),
              ]

    for list_tuple in lists:
        listserve = list_tuple[0]
        ministry  = list_tuple[1]

        list_members     = read_listserve(listserve)
        ministry_members = read_ministry(ministry, members)

        compare_members(members,
                        listserve, list_members,
                        ministry, ministry_members)

main()
