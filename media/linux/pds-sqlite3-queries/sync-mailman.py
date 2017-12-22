#!/usr/bin/env python3.6

"""Run some queries on PDS email data, generate some CSVs with the
results of the queries.

No locking / lockfile is used in this script because it is assumed
that simultaneous access is prevented by locking at a higher level
(i.e., ../run-all.py).
"""

import datetime
import argparse
import logging
import logging.handlers
import sqlite3
import pprint
import time
import csv
import os
import re

from recordclass import recordclass

# significantly easier if this is a global
log = None

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

StaffClergy = recordclass('StaffClegy',
                          ['name',
                           'id',
                           'emails'])

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
# Staff / Clergy key: CCRec
staffclergy = dict()
# Keywords, key: ID
keywords = dict()
# Ministries, key: ID
ministries = dict()
# Statuses, key: ID
statuses = dict()

today = datetime.date.today()
thirteen_years = datetime.timedelta(days = (365 * 13))

##############################################################################

def setup_args():
    parser = argparse.ArgumentParser(description='Run queries on the SQLite3 database of PDS data')

    parser.add_argument('--sqlite3-db',
                        default=None,
                        help='Path to SQLite3 PDS database file')

    parser.add_argument('--logfile',
                        default=None,
                        help='Optional output logfile')

    parser.add_argument('--verbose',
                        default=False,
                        action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--debug',
                        default=False,
                        action='store_true',
                        help='Enable extra debugging')

    args = parser.parse_args()

    return args

###############################################################################

def setup_logging(args):
    level=logging.ERROR

    if args.debug:
        level="DEBUG"
    elif args.verbose:
        level="INFO"

    global log
    log = logging.getLogger('pds')
    log.setLevel(level)

    # Make sure to include the timestamp in each message
    f = logging.Formatter('%(asctime)s %(levelname)-8s: %(message)s')

    # Default log output to stdout
    s = logging.StreamHandler()
    s.setFormatter(f)
    log.addHandler(s)

    # Optionally save to a rotating logfile
    if args.logfile:
        s = logging.handlers.RotatingFileHandler(filename=args.logfile,
                                                 maxBytes=(pow(2,20) * 10),
                                                 backupCount=10)
        s.setFormatter(f)
        log.addHandler(s)

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

    log.info("Number of active families: {}".format(num_active_families))

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

    log.info("Number of active members: {}"
             .format(num_active_members))
    log.info("Number of active members >=13: {}"
             .format(num_active_ge13_members))

#-----------------------------------------------------------------------------

def find_staffclergy_addresses(cur, cc_id):
    addrs = []

    query = ('SELECT EMailAddress,EmailOverMail '
             'FROM CCEmail_DB '
             'WHERE RecNum=?'
             .format(db_num=database))

    for email_row in cur.execute(query, (int(cc_id),)).fetchall():
        email_address = email_row[0]
        email_preferred = email_row[1]
        email = Email(address=email_address.lower(),
                      preferred=email_preferred)
        addrs.append(email)

    return addrs

#-----------------------------------------------------------------------------

def find_active_staffclergy(cur):
    # Staff and Clergy are in the ChurchContact database
    query = ('SELECT CCRec,Name '
             'FROM ChurchContact_DB '
             'WHERE (CensusInactive{db_num} = 0 OR CensusInactive{db_num} is null) AND '
                 '(IsPDSStaff{db_num} = 1 OR IsPDSClergy{db_num} = 1)'
             .format(db_num=database))

    for cc_row in cur.execute(query).fetchall():
        cc_id = cc_row[0]
        cc_name = cc_row[1]

        # Find all corresponding email addresses
        cc_addrs = find_staffclergy_addresses(cur, cc_id)

        sc = StaffClergy(name=cc_name,
                         id=cc_id,
                         emails=cc_addrs)
        staffclergy[cc_id] = sc

    log.info("Number of active staff/clergymembers: {}"
             .format(len(staffclergy)))

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

# Examine a list of email addresses and determine which one is
# "preferred".  If there's no "preferred" marked in the data, then
# pick the lexigraphicaly first one.
def find_preferred_email(emails):
    preferred_email = None
    other_emails = []
    for email in emails:
        # Don't take duplicates
        if email.address.lower() in other_emails:
            continue

        if preferred_email is None and email.preferred == True:
            preferred_email = email.address
        else:
            other_emails.append(email.address.lower())

    if preferred_email is None:
        other_emails.sort(reverse=True)
        preferred_email = other_emails.pop()

    return preferred_email

##############################################################################

def write_parishioner_mailman_list(filename):
    results = list()
    emails = list()

    # "members" is a dict
    for member_id in members:
        m = members[member_id]
        (have_birthdate, is_ge13) = member_is_ge13(m)
        if not is_ge13:
            continue

        if len(m.emails) < 1:
            continue

        # Make sure they have the "Parish-wide Email" keyword
        if 'Parish-wide Email' not in m.keywords:
            continue

        # At this point, we have a member that we want to, and can,
        # email.  Find their preferred email.
        preferred_email = find_preferred_email(m.emails)

        # Double check to make sure we're not adding a duplicate
        if preferred_email not in emails:
            results.append((m.name, preferred_email))
            emails.append(preferred_email)

    # Add all the staff / clergy emails.
    for staffclergy_id in staffclergy:
        sc = staffclergy[staffclergy_id]
        preferred_email = find_preferred_email(sc.emails)

        # Sanity check for duplicates here, too (e.g., in class
        # staff/clergy are Members).
        if preferred_email not in emails:
            results.append((sc.name, preferred_email))
            emails.append(preferred_email)

    count = 0
    with open(filename, 'w', newline='') as textfile:
        for t in results:
            textfile.write('"{name}" <{email}>\n'
                           .format(name=t[0], email=t[1]))
            count = count + 1

    log.info("Number of addresses written to {file}: {count}"
             .format(file=filename, count=count))

##############################################################################

def main():
    args = setup_args()
    setup_logging(args)

    log.info("Crunching the data...")
    conn = sqlite3.connect(args.sqlite3_db)
    cur = conn.cursor()

    find_statuses(cur)
    find_ministries(cur)
    find_keywords(cur)

    # Build up dictionary of families and members
    find_active_families(cur)
    find_active_members(cur)
    find_active_staffclergy(cur)

    # Done with the database
    conn.close()
    log.info("Data crunched!");

    # Now we have dictionaries of Families and members.
    # Analyze these data structures and make some CSVs.

    # 1. Write out the members for the current "all parish" list
    filename = 'mailman-parishioner.txt'
    write_parishioner_mailman_list(filename)

if __name__ == '__main__':
    main()
