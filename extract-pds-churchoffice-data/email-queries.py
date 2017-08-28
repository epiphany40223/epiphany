#!/usr/bin/env python3

#
# Run some queries on PDS email data, generate some CSVs with the
# results of the queries.  These queries are likely only needed
# one-time -- it is unlikely that they will be run on an ongoing
# basis.
#

import fileinput
import datetime
import sqlite3
import pprint
import time
import csv
import os
import re
from recordclass import recordclass

# Which database number to use?
# At ECC, the active database is 1.
database = 1

##############################################################################

Family = recordclass('Family',
                     ['name',
                      'fam_rec_num',
                      'parkey',
                      'emails',
                      'members'])

Member = recordclass('Member',
                     ['name',
                      'id',
                      'birth_day',
                      'birth_month',
                      'birth_year',
                      'family_id',
                      'emails'])

Email = recordclass('Email',
                    ['address',
                     'preferred'])

pp = pprint.PrettyPrinter(indent=4)

# Dictionaries to fill in
# Family key: FamRecNum
families = dict()
# Member key: MemRecNum
members = dict()
# Member key: MemRecNum
members_with_inactive_families = dict()

today = datetime.date.today()
thirteen_years = datetime.timedelta(days = (365 * 13))

##############################################################################

def find_family_addresses(cur, fam_id):
    addrs = []

    query = ('SELECT MemEmail_DB.EMailAddress,MemEmail_DB.EmailOverMail '
             'FROM MemEmail_DB '
             'INNER JOIN Fam_DB ON MemEmail_DB.MemRecNum=Fam_DB.FamRecNum '
             'WHERE MemEmail_DB.MemRecNum=? AND '
             '(Fam_DB.PDSInactive{0}=0 OR Fam_DB.PDSInactive{0} is NULL) AND '
             'Fam_DB.CensusFamily{0}=1 AND '
             'MemEmail_DB.FamEmail=1'
             .format(database))

    for email_row in cur.execute(query, (int(fam_id),)).fetchall():
        email_address = email_row[0]
        email_preferred = email_row[1]
        email = Email(address=email_address,
                      preferred=email_preferred)
        addrs.append(email)

    return addrs

#-----------------------------------------------------------------------------

def find_active_families(cur):
    # Find all active families in database 1
    query = ('SELECT FamRecNum,Name,ParKey '
             'FROM Fam_DB '
             'WHERE (Fam_DB.PDSInactive{0}=0 OR '
             'FAM_DB.PDSInactive{0} is null) AND '
             'Fam_DB.CensusFamily{0}=1 '
             'ORDER BY FamRecNum'.format(database))

    for family_row in cur.execute(query).fetchall():
        fam_id = family_row[0]
        fam_name = family_row[1]
        fam_parkey = family_row[2]

        # Find all family email addresses
        fam_addrs = find_family_addresses(cur, fam_id)

        family = Family(name=fam_name,
                        fam_rec_num=fam_id,
                        parkey=fam_parkey,
                        emails=fam_addrs,
                        members=[])

        families[fam_id] = family

##############################################################################

def find_member_addresses(cur, mem_id):
    addrs = []

    query = ('SELECT MemEmail_DB.EMailAddress,MemEmail_DB.EmailOverMail '
             'FROM MemEmail_DB '
             'INNER JOIN Mem_DB ON MemEmail_DB.MemRecNum=Mem_DB.MemRecNum '
             'WHERE MemEmail_DB.MemRecNum=? AND '
             '(Mem_DB.PDSInactive{0}=0 OR Mem_DB.PDSInactive{0} is NULL) AND '
             'Mem_DB.CensusMember{0}=1 AND '
             '(MemEmail_DB.FamEmail is NULL or MemEmail_DB.FamEmail=0)'
             .format(database))

    for email_row in cur.execute(query, (int(mem_id),)).fetchall():
        email_address = email_row[0]
        email_preferred = email_row[1]
        email = Email(address=email_address,
                      preferred=email_preferred)
        addrs.append(email)

    return addrs

#-----------------------------------------------------------------------------

def find_active_members(cur):
    query = ('SELECT MemRecNum,Name,FamRecNum,DateOfBirth,MonthOfBirth,YearOfBirth '
             'FROM Mem_DB '
             'WHERE Mem_DB.deceased=0 AND '
             '(Mem_DB.PDSInactive{0}=0 OR Mem_DB.PDSInactive{0} is null) AND '
             'Mem_DB.CensusMember{0}=1'
             .format(database))

    p = re.compile("(\d\d\d\d)-(\d\d)-(\d\d)")
    for member_row in cur.execute(query).fetchall():
        mem_id = member_row[0]
        mem_name = member_row[1]
        mem_fam_id = member_row[2]
        mem_birth_date = member_row[3]

        m = p.match(mem_birth_date)
        mem_birth_year = m.group(1)
        mem_birth_month = m.group(2)
        mem_birth_day = m.group(3)

        # Find all member email addresses
        mem_addrs = find_member_addresses(cur, mem_id)

        member = Member(name=mem_name,
                        id=mem_id,
                        birth_day=mem_birth_day,
                        birth_month=mem_birth_month,
                        birth_year=mem_birth_year,
                        family_id=mem_fam_id,
                        emails=mem_addrs)

        # Fun situation: A Member may not be inactive, but their
        # family may be inactive!
        try:
            # This will succeed if there's an active family
            families[mem_fam_id].members.append(member)
            members[mem_id] = member
        except:
            members_with_inactive_families[mem_id] = member

##############################################################################

def write_family_csv(filename, families):
    print("=== Writing family CSV file: {0}".format(filename))
    if len(families) == 0:
        print("    No results!")
        return

    count = 0
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['Family ID', 'Family Name']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames,
                                quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for f in families:
            count = count + 1

            # If we don't do this wonky value for the Family ID,
            # Excel will strip off the leading zeros.  :-(
            writer.writerow({'Family ID': "' {0}".format(str(f.parkey).strip()),
                             'Family Name': f.name})

    print("    Number of families written: {0}".format(count))

#-----------------------------------------------------------------------------

def write_member_csv(filename, members):
    print("=== Writing member CSV file: {0}".format(filename))
    if len(members) == 0:
        print("    No results!")
        return

    count = 0
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['Family ID', 'Member Name', 'Over 13?']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames,
                                quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for m in members:
            count = count + 1
            # If we don't do this wonky value for the Member Family ID,
            # Excel will strip off the leading zeros.  :-(
            try:
                parkey = "' {0}".format(families[m.family_id].parkey.strip())
            except:
                parkey = 'None'

            (have_birthdate, is_ge13) = member_is_ge13(m)
            age = None
            if have_birthdate:
                if is_ge13:
                    age = 'Yes'
                else:
                    age = 'No'
            else:
                age = 'Assumed yes'

            writer.writerow({'Family ID': parkey,
                             'Member Name': m.name,
                             'Over 13?': age})

    print("    Number of members written: {0}".format(count))

##############################################################################

def write_members_with_inactive_families():
    results = list()

    for m in members_with_inactive_families:
        results.append(members_with_inactive_families[m])

    write_member_csv('members-with-inactive-families.csv', results)

##############################################################################

def write_families_with_no_email_at_all():
    results = list()

    # "families" is a dict
    for family_id in families:
        f = families[family_id]
        if len(f.emails) > 0:
            continue

        # f.members is a list
        found = False
        for m in f.members:
            if len(m.emails) > 0:
                found = True
                break

        if not found:
            results.append(f)

    write_family_csv('families-with-no-email-addresses-at-all.csv', results)

##############################################################################

def write_families_with_email_but_no_member_emails():
    results = list()

    # "families" is a dict
    for family_id in families:
        f = families[family_id]
        if len(f.emails) == 0:
            continue

        # f.members is a list
        found = False
        for m in f.members:
            if len(m.emails) > 0:
                found = True
                break

        if not found:
            results.append(f)

    write_family_csv('families-with-email-but-no-member-emails.csv', results)

##############################################################################

def write_families_with_emails_same_as_members():
    results = list()

    # "families" is a dict
    for family_id in families:
        f = families[family_id]
        if len(f.emails) == 0:
            continue

        # f.members is a list
        for m in f.members:
            if len(m.emails) == 0:
                continue

            found = False
            for fe in f.emails:
                for me in m.emails:
                    if fe.address.lower() == me.address.lower():
                        found = True
                        break

            if found:
                results.append(m)

    write_member_csv('families-emails-same-as-members.csv', results)

##############################################################################

def write_families_with_email_that_is_not_a_member_email():
    results = list()

    # "families" is a dict
    for family_id in families:
        f = families[family_id]
        if len(f.emails) == 0:
            continue

        have_member_emails = False
        found_fe = True
        for fe in f.emails:
            found_tmp = False

            # f.members is a list
            for m in f.members:
                if len(m.emails) == 0:
                    continue

                have_member_emails = True
                for me in m.emails:
                    if fe.address.lower() == me.address.lower():
                        found_tmp = True
                        break

            if not found_tmp:
                found_fe = False
                break

        # If there are any member emails at all, and we had at least
        # one family email that was not found, then save the family.
        if have_member_emails and not found_fe:
            results.append(f)
            break

    write_family_csv('families-with-email-that-is-not-a-member-email.csv', results)

##############################################################################

#
# Returns a tuple:
# 1st: whether we have a birthdate for this member or not
# 2nd: whether the member is >= 13 years old (only relevant if first==True)
#
def member_is_ge13(member):
    # If the date is not set, then just return True.  Shrug.
    if (member.birth_day is None or
        int(member.birth_day) == 0 or
        member.birth_month is None or
        int(member.birth_month) == 0 or
        member.birth_year is None or
        int(member.birth_year) == 0):
        return (False, True)

    mem_birthdate = datetime.date(day=int(member.birth_day),
                                  month=int(member.birth_month),
                                  year=int(member.birth_year))
    if mem_birthdate + thirteen_years <= today:
        return (True, True)
    else:
        return (True, False)

#-----------------------------------------------------------------------------

def write_members_gt13yo_with_no_email():
    results = list()

    # "members" is a dict
    for member_id in members:
        m = members[member_id]
        (have_birthdate, is_ge13) = member_is_ge13(m)
        if not is_ge13:
            continue

        if len(m.emails) == 0:
            results.append(m)

    write_member_csv('members-gt13yo-with-no-email.csv', results)

##############################################################################

def write_members_gt13yo_with_1_non_preferred_email():
    results = list()

    # "members" is a dict
    for member_id in members:
        m = members[member_id]
        (have_birthdate, is_ge13) = member_is_ge13(m)
        if not is_ge13:
            continue

        if len(m.emails) != 1:
            continue

        if not m.emails[0].preferred:
            results.append(m)

    write_member_csv('members-gt13yo-with-1-non-preferred-email.csv', results)

##############################################################################

def write_members_gt13yo_with_N_non_preferred_email():
    results = list()

    # "members" is a dict
    for member_id in members:
        m = members[member_id]
        (have_birthdate, is_ge13) = member_is_ge13(m)
        if not is_ge13:
            continue

        if len(m.emails) < 2:
            continue

        have_duplicate = False
        for (i, m1) in enumerate(m.emails):
            for j in range(i+1, len(m.emails)):
                if m1.address.lower() == m.emails[j].address.lower():
                    have_duplicate = True
                    break

        if have_duplicate:
            results.append(m)

    write_member_csv('members-with-dup-emails.csv', results)

##############################################################################

def write_members_with_dup_emails():
    results = list()

    # "members" is a dict
    for member_id in members:
        m = members[member_id]
        (have_birthdate, is_ge13) = member_is_ge13(m)
        if not is_ge13:
            continue

        if len(m.emails) < 2:
            continue

        have_preferred = False
        for me in m.emails:
            if me.preferred == True:
                have_preferred = True
                break

        if not have_preferred:
            results.append(m)

    write_member_csv('members-gt13yo-with-N-non-preferred-email.csv', results)

##############################################################################

# This is who we want to sent the update email to
def write_members_gt13yo_not_in_mailman():



    print("JMS FINISH ME")
    return






    # Read in parishioner email list
    parishioner_list = list()
    with fileinput.input(files=('parishioner.txt')) as f:
        for line in f:
            parishioner_list.append(line)

    results = list()

    # "members" is a dict
    for member_id in members:
        m = members[member_id]
        (have_birthdate, is_ge13) = member_is_ge13(m)
        if not is_ge13:
            continue

        if m.emails is None or len(m.emails) == 0:
            continue

        # Use the first preferred email address, if available
        preferred_address = None
        for me in sorted(m.emails):
            if me.preferred == True:
                preferred_address = me
                break

        if preferred_address is None:
            preferred_address = sorted(m.emails)[0]

    write_member_csv('members-gt13yo-not-in-parishioner-listserve.csv', results)

##############################################################################

# This will ultimately be the "real" list
def write_members_gt13yo_in_email_ministry():
    pass

##############################################################################

def main():
    conn = sqlite3.connect('pdschurchoffice-current.sqlite3')
    cur = conn.cursor()

    # Build up dictionary of families and members
    find_active_families(cur)
    find_active_members(cur)

    # Done with the database
    conn.close()

    # Now we have dictionaries of Families and members.
    # Analyze these data structures and make some CSVs.

    # 0. Active members with inactive families
    write_members_with_inactive_families()

    # 1. Families (including members) that have no email addresses at all.
    write_families_with_no_email_at_all()

    # 2. Families that have family email addresses, but no member email addresses
    write_families_with_email_but_no_member_emails()

    # 3. Families that have family email adddresses *and* (different)
    # member email addresses
    write_families_with_email_that_is_not_a_member_email()

    # 3.5 Families that have family email addresses that are
    # duplicates of their Members
    write_families_with_emails_same_as_members()

    # 4. Members >=13 years old that have no email addresses
    write_members_gt13yo_with_no_email()

    # 5. Members >=13 years old that have exactly one email address,
    # and it's not preferred
    write_members_gt13yo_with_1_non_preferred_email()

    # 6. Members >=13 years old that have more than one email address,
    # and none are preferred
    write_members_gt13yo_with_N_non_preferred_email()

    # 7. Members >=13 years old who are not in the parishioner mailman list
    write_members_gt13yo_not_in_mailman()

    # 8. Members who have duplicate email addresses
    write_members_with_dup_emails()

    # 9. Preferred Members >=13 years old in the parish-wide email
    # ministry
    write_members_gt13yo_in_email_ministry()

main()
