#!/usr/bin/env python3

#
# Run some queries on PDS email data, generate some CSVs with the
# results of the queries.  These queries are likely only needed
# one-time -- it is unlikely that they will be run on an ongoing
# basis.

#
# TO DO BEFORE SENDING EMAIL
# - Add "I am no longer a parishioner" option to the form
# - Signup for a plan on Jotfotm
# - Confirm what we're doing for Members with no Email addresses
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

# Jeff's module (written in C)
import pds

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
                      'emails',
                      'keywords',
                      'active_ministries'])

Email = recordclass('Email',
                    ['address',
                     'preferred'])

Keyword = recordclass('Keyword',
                      ['id',
                       'keyword'])

Ministry = recordclass('Ministry',
                       ['id',
                        'name'])

Status = recordclass('Status',
                       ['id',
                        'description'])

pp = pprint.PrettyPrinter(indent=4)

# Dictionaries to fill in
# Family key: FamRecNum
families = dict()
# Member key: MemRecNum
members = dict()
# Member key: MemRecNum
members_with_inactive_families = dict()
# Keywords, key: ID
keywords = dict()
# Ministries, key: ID
ministries = dict()
# Statuses, key: ID
statuses = dict()

today = datetime.date.today()
thirteen_years = datetime.timedelta(days = (365 * 13))

##############################################################################

def find_statuses(cur):
    query = ('SELECT * '
             'FROM StatusType_DB ')

    for status_row in cur.execute(query).fetchall():
        status_id=status_row[0]
        status = Status(id=status_id,
                        description=status_row[1])
        statuses[status_id] = status

#-----------------------------------------------------------------------------

def find_ministries(cur):
    query = ('SELECT * '
             'FROM MinType_DB ')

    for ministry_row in cur.execute(query).fetchall():
        ministry_id = ministry_row[0]
        ministry = Ministry(id=ministry_id,
                            name=ministry_row[1])
        ministries[ministry_id] = ministry

#-----------------------------------------------------------------------------

def find_keywords(cur):
    query = ('SELECT * '
             'FROM MemKWType_DB ')

    for kw_row in cur.execute(query).fetchall():
        kw_id = kw_row[0]
        kw = Keyword(id=kw_id,
                     keyword=kw_row[1])
        keywords[kw_id] = kw

##############################################################################

def find_family_addresses(cur, fam_id):
    addrs = []

    query = ('SELECT MemEmail_DB.EMailAddress,MemEmail_DB.EmailOverMail '
             'FROM MemEmail_DB '
             'INNER JOIN Fam_DB ON MemEmail_DB.MemRecNum=Fam_DB.FamRecNum '
             'WHERE MemEmail_DB.MemRecNum=? AND '
             '(Fam_DB.PDSInactive{db_num}=0 OR Fam_DB.PDSInactive{db_num} is NULL) AND '
             'Fam_DB.CensusFamily{db_num}=1 AND '
             'MemEmail_DB.FamEmail=1'
             .format(db_num=database))

    for email_row in cur.execute(query, (int(fam_id),)).fetchall():
        email_address = email_row[0]
        email_preferred = email_row[1]
        email = Email(address=email_address.lower(),
                      preferred=email_preferred)
        addrs.append(email)

    return addrs

#-----------------------------------------------------------------------------

def find_active_families(cur):
    # Find all active families in database 1
    query = ('SELECT FamRecNum,Name,ParKey '
             'FROM Fam_DB '
             'WHERE (Fam_DB.PDSInactive{db_num}=0 OR '
             'FAM_DB.PDSInactive{db_num} is null) AND '
             'Fam_DB.CensusFamily{db_num}=1 '
             'ORDER BY FamRecNum'
             .format(db_num=database))

    num_active_families = 0
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
        num_active_families = num_active_families + 1

    print("    Number of active families: {}".format(num_active_families))

##############################################################################

def find_member_addresses(cur, mem_id):
    addrs = []

    query = ('SELECT MemEmail_DB.EMailAddress,MemEmail_DB.EmailOverMail '
             'FROM MemEmail_DB '
             'INNER JOIN Mem_DB ON MemEmail_DB.MemRecNum=Mem_DB.MemRecNum '
             'WHERE MemEmail_DB.MemRecNum=? AND '
             '(Mem_DB.PDSInactive{db_num}=0 OR Mem_DB.PDSInactive{db_num} is NULL) AND '
             'Mem_DB.CensusMember{db_num}=1 AND '
             '(MemEmail_DB.FamEmail is NULL or MemEmail_DB.FamEmail=0)'
             .format(db_num=database))

    for email_row in cur.execute(query, (int(mem_id),)).fetchall():
        email_address = email_row[0]
        email_preferred = email_row[1]
        email = Email(address=email_address.lower(),
                      preferred=email_preferred)
        addrs.append(email)

    return addrs

#-----------------------------------------------------------------------------

def find_member_keywords(cur, mem_id):
    mem_keywords = []

    query = ('SELECT DescRec '
             'FROM MemKW_DB '
             'WHERE MemRecNum=?')

    for mem_kw_row in cur.execute(query, (int(mem_id),)).fetchall():
        kw_id = mem_kw_row[0]

        mem_keywords.append(keywords[kw_id].keyword)

    return mem_keywords

#-----------------------------------------------------------------------------

def find_member_active_ministries(cur, mem_id):
    mem_ministries = []

    query = ('SELECT MinDescRec '
             'FROM MemMin_DB '
             'INNER JOIN StatusType_DB on MemMin_DB.StatusDescRec = StatusType_DB.StatusDescRec '
             'WHERE MemMin_DB.MemRecNum=? and StatusType_DB.Active=1')

    for mem_ministry_row in cur.execute(query, (int(mem_id),)).fetchall():
        ministry_id = mem_ministry_row[0]
        mem_ministries.append(ministries[ministry_id].name)

    return mem_ministries

#-----------------------------------------------------------------------------

def find_active_members(cur):
    query = ('SELECT MemRecNum,Name,FamRecNum,DateOfBirth,MonthOfBirth,YearOfBirth '
             'FROM Mem_DB '
             'WHERE Mem_DB.deceased=0 AND '
             '(Mem_DB.PDSInactive{db_num}=0 OR Mem_DB.PDSInactive{db_num} is null) AND '
             'Mem_DB.CensusMember{db_num}=1'
             .format(db_num=database))

    num_active_members = 0
    num_active_ge13_members = 0
    p = re.compile("(\d\d\d\d)-(\d\d)-(\d\d)")
    for member_row in cur.execute(query).fetchall():
        mem_id = member_row[0]
        mem_name = member_row[1]
        mem_fam_id = member_row[2]
        mem_birth_date = member_row[3]

        try:
            m = p.match(mem_birth_date)
            mem_birth_year = m.group(1)
            mem_birth_month = m.group(2)
            mem_birth_day = m.group(3)
        except:
            mem_birth_year = None
            mem_birth_month = None
            mem_birth_day = None

        # Find all member email addresses
        mem_addrs = find_member_addresses(cur, mem_id)

        # Find all member keywords
        mem_keywords = find_member_keywords(cur, mem_id)

        # Find all member ministries
        mem_ministries = find_member_active_ministries(cur, mem_id)

        member = Member(name=mem_name,
                        id=mem_id,
                        birth_day=mem_birth_day,
                        birth_month=mem_birth_month,
                        birth_year=mem_birth_year,
                        family_id=mem_fam_id,
                        keywords=mem_keywords,
                        active_ministries=mem_ministries,
                        emails=mem_addrs)

        # Fun situation: A Member may not be inactive, but their
        # family may be inactive!
        try:
            # This will succeed if there's an active family
            families[mem_fam_id].members.append(member)
            members[mem_id] = member

            num_active_members = num_active_members + 1
            (have_birthdate, is_ge13) = member_is_ge13(member)
            if is_ge13:
                num_active_ge13_members = num_active_ge13_members + 1

        except:
            members_with_inactive_families[mem_id] = member

    print("    Number of active members: {}".format(num_active_members))
    print("    Number of active members >=13: {}".format(num_active_ge13_members))

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

##############################################################################

def write_members_ge13yo_with_no_email():
    no_email_results = list()
    email_results = list()

    # "members" is a dict
    for member_id in members:
        m = members[member_id]
        (have_birthdate, is_ge13) = member_is_ge13(m)
        if not is_ge13:
            continue

        if len(m.emails) == 0:
            no_email_results.append(m)
        else:
            email_results.append(m)

    write_member_csv('members-ge13yo-with-no-email.csv', no_email_results)
    write_member_csv('members-ge13yo-with-some-email.csv', email_results)

##############################################################################

def write_members_ge13yo_with_1_non_preferred_email():
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

    write_member_csv('members-ge13yo-with-1-non-preferred-email.csv', results)

##############################################################################

def write_members_ge13yo_with_N_non_preferred_email():
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

    write_member_csv('members-ge13yo-with-N-non-preferred-email.csv', results)

##############################################################################

# This is who we want to sent the update email to
def write_members_ge13yo_not_in_mailman():



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

    write_member_csv('members-ge13yo-not-in-parishioner-listserve.csv', results)

##############################################################################

# This will ultimately be the "real" list
def write_members_ge13yo_in_email_ministry():
    pass

##############################################################################

def write_member_ge13yo_emails_for_form():
    results = list()

    FormMemData = recordclass('FormMemData',
                              ['mem_rec_num',
                               'name',
                               'parkey',
                               'preferred_email',
                               'other_emails'])

    # "members" is a dict
    for member_id in members:
        m = members[member_id]
        (have_birthdate, is_ge13) = member_is_ge13(m)
        if not is_ge13:
            continue

        if len(m.emails) < 1:
            continue

        # JMS HARD-CODED HACK JUST TO TEST WITH TECH COMMITTEE
        #if 'S-Technology Committee' not in m.active_ministries:
        #    continue
        #print("FOUND TECH: {}".format(m))

        # At this point, we have a member that we want to, and can,
        # email.

        # We need to capture all email addresses, and know which one
        # is "preferred".  If there's no "preferred", then pick the
        # lexigraphicaly first one.
        preferred_email = None
        other_emails = []
        for me in m.emails:
            # Don't take duplicates
            if me.address.lower() in other_emails:
                continue

            if preferred_email is None and me.preferred == True:
                preferred_email = me.address
            else:
                other_emails.append(me.address.lower())

        if preferred_email is None:
            other_emails.sort(reverse=True)
            preferred_email = other_emails.pop()

        memdata = FormMemData(mem_rec_num=member_id,
                              name=m.name,
                              parkey=families[m.family_id].parkey,
                              preferred_email=preferred_email,
                              other_emails=other_emails)
        results.append(memdata)

    count = 0
    filename = 'members-ge13-email-update-form.csv'
    print("+++ Custom writing to file {}"
          .format(filename))
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['ParKey', 'Member Name', 'PreferredEmail',
                      'OtherEmail1', 'OtherEmail2', 'OtherEmail3',
                      'OtherEmail4', 'OtherEmail5' ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames,
                                quoting=csv.QUOTE_ALL)
        writer.writeheader()

        for r in results:
            other_emails = []
            for i in range(5):
                try:
                    other_emails.append(r.other_emails[i])
                except:
                    other_emails.append('')

            writer.writerow({'ParKey': r.parkey.strip(),
                             'Member Name': r.name,
                             'PreferredEmail': r.preferred_email,
                             'OtherEmail1': other_emails[0],
                             'OtherEmail2': other_emails[1],
                             'OtherEmail3': other_emails[2],
                             'OtherEmail4': other_emails[3],
                             'OtherEmail5': other_emails[4]})

            count = count + 1

    print("    Number of members written: {0}".format(count))

##############################################################################

def write_member_ge13yo_family_emails_for_form():
    results = list()

    FormMemData = recordclass('FormMemData',
                              ['mem_rec_num',
                               'name',
                               'parkey',
                               'preferred_email',
                               'other_emails'])

    # "members" is a dict
    for member_id in members:
        m = members[member_id]
        (have_birthdate, is_ge13) = member_is_ge13(m)
        if not is_ge13:
            continue

        # JMS HARD-CODED HACK JUST TO TEST WITH TECH COMMITTEE
        if 'S-Technology Committee' not in m.active_ministries:
            continue

        # We only want Members with 0 email addresses.
        if len(m.emails) > 0:
            continue

        # Find the corresponding Family.
        family_id = m.family_id
        f = families[family_id]

        # If there's no Family email, there's nothing we can do.
        if len(f.emails) == 0:
            continue

        # Now we have a Member with no email addresses, but with a
        # corresponding Family that has >=1 email addresses.

        # We need to capture all email addresses, and know which one
        # is "preferred".  If there's no "preferred", then pick the
        # lexigraphicaly first one.
        preferred_email = None
        other_emails = []
        for fe in f.emails:
            # Don't take duplicates
            if fe.address.lower() in other_emails:
                continue

            if preferred_email is None and fe.preferred == True:
                preferred_email = fe.address
            else:
                other_emails.append(fe.address.lower())

        if preferred_email is None:
            other_emails.sort(reverse=True)
            preferred_email = other_emails.pop()

        memdata = FormMemData(mem_rec_num=member_id,
                              name=m.name,
                              parkey=families[m.family_id].parkey,
                              preferred_email=preferred_email,
                              other_emails=other_emails)
        results.append(memdata)

    count = 0
    filename = 'members-ge13-email-family-update-form.csv'
    print("+++ Custom writing to file {}"
          .format(filename))
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['ParKey', 'Member Number', 'Member Name', 'PreferredEmail',
                      'OtherEmail1', 'OtherEmail2', 'OtherEmail3',
                      'OtherEmail4', 'OtherEmail5' ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames,
                                quoting=csv.QUOTE_ALL)
        writer.writeheader()

        for r in results:
            other_emails = []
            for i in range(5):
                try:
                    other_emails.append(r.other_emails[i])
                except:
                    other_emails.append('')

            writer.writerow({'ParKey': r.parkey.strip(),
                             'Member Name': r.name,
                             'Member Number': r.mem_rec_num,
                             'PreferredEmail': r.preferred_email,
                             'OtherEmail1': other_emails[0],
                             'OtherEmail2': other_emails[1],
                             'OtherEmail3': other_emails[2],
                             'OtherEmail4': other_emails[3],
                             'OtherEmail5': other_emails[4]})

            count = count + 1

    print("    Number of members written: {0}".format(count))

    # Update MemEMail.db database file
    new_db_file = 'data-current/MemEmail-updated.DB'
    if os.path.exists(new_db_file):
        os.unlink(new_db_file)
    os.system('cp data-current/MemEMail.DB {dest}'.format(dest=new_db_file))
    mem_count = 0
    email_count = 0
    f = pds.open(new_db_file)
    for r in results:
        f.add_member_email(r.mem_rec_num, r.preferred_email, True)
        email_count = email_count + 1
        for i in range(5):
            try:
                f.add_member_email(r.mem_rec_num, r.other_emails[i], False)
                email_count = email_count + 1
            except:
                pass

        mem_count = mem_count + 1

    f.close()

    print("    Number of members updated with a preferred address: {}"
          .format(mem_count))
    print("    Number of email addresses added to Members overall: {}"
          .format(email_count))

def write_unknown_parishonier_listserv_addresses():
    filename = 'parishioner-current.txt'
    if not os.path.exists(filename):
        print("Cannot find file \"{file}\"; skipping".format(file=filename))
        return

    # Read current parishioner listserve members
    listserv = list()
    with open(filename, 'r', newline='') as textfile:
        tmp = textfile.readlines()

        # Make sure all the addresses are lower case.  Crude, but effective.
        for addr in tmp:
            listserv.append(addr.rstrip().lower())

    # Check every address in the listserve.  Can we find a Member
    # associated with that address?
    not_found = list()
    for addr in listserv:
        found = False

        # "members" is a dict
        for member_id in members:
            m = members[member_id]
            (have_birthdate, is_ge13) = member_is_ge13(m)
            if not is_ge13:
                continue

            for email in m.emails:
                if email.address == addr:
                    found = True
                    break

            if found:
                break

        if not found:
            not_found.append(addr)
            print("NOT FOUND: {addr}".format(addr=addr))

    with open('unknown-listserve-addresses.txt', 'w', newline='') as textfile:
        for addr in not_found:
            textfile.write(addr + '\n')

##############################################################################

def main():
    print("=== Crunching the data...")
    conn = sqlite3.connect('pdschurch.sqlite3')
    cur = conn.cursor()

    find_statuses(cur)
    find_ministries(cur)
    find_keywords(cur)

    # Build up dictionary of families and members
    find_active_families(cur)
    find_active_members(cur)

    # Done with the database
    conn.close()
    print("=== Data crunched!");

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
    write_members_ge13yo_with_no_email()

    # 5. Members >=13 years old that have exactly one email address,
    # and it's not preferred
    write_members_ge13yo_with_1_non_preferred_email()

    # 6. Members >=13 years old that have more than one email address,
    # and none are preferred
    write_members_ge13yo_with_N_non_preferred_email()

    # 7. Members >=13 years old who are not in the parishioner mailman list
    write_members_ge13yo_not_in_mailman()

    # 8. Members who have duplicate email addresses
    write_members_with_dup_emails()

    # 9. Preferred Members >=13 years old in the parish-wide email
    # ministry
    write_members_ge13yo_in_email_ministry()

    # 10. Write out data for the email update form
    write_member_ge13yo_emails_for_form()

    # 11. Write out data for the email update form
    write_member_ge13yo_family_emails_for_form()

    # 12. Read current parishioner list, find any email address that
    # is not associated with an active Member.
    write_unknown_parishonier_listserv_addresses()

main()
