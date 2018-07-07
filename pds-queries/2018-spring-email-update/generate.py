#!/usr/bin/env python3

import fileinput
import datetime
import sqlite3
import pprint
import time
import csv
import os
import re
from recordclass import recordclass

import smtplib
import base64
from email.message import EmailMessage

##############################################################################

Sent = recordclass('Sent',
                   ['parkey',
                    'member_name',
                    'original_email',
                    'other_email_1',
                    'other_email_2',
                    'other_email_3',
                    'other_email_4',
                    'other_email_5'])

Updated = recordclass('Updated',
                      ['parkey',
                       'member_name',
                       'original_email'])

pp = pprint.PrettyPrinter(indent=4)

##############################################################################

name_order = re.compile('^([^,]+),(.+)$')
name_squash1 = re.compile('\(.+\)')
name_squash2 = re.compile('\{.+\}')

def transmorgify(name_in):
    # Fix a few things with names
    name = name_in.strip()

    # Remove all (foo) and {foo}
    name = name_squash1.sub('', name)
    name = name_squash2.sub('', name)

    # Some names are "Last,First".  Change that to "First Last"
    m = name_order.match(name)
    if m:
        first_name = m.group(2)
        full_name = "{first} {last}".format(last=m.group(1),
                                            first=m.group(2))
    else:
        words = name.split(' ')
        first_name = words[0]
        full_name = name

    return full_name

def read_sent_mail_list():
    sent = list()

    filename = "2017-10-01 Mailed email update form to these PDS members on.csv"
    with open(filename, 'r') as csvfile:
        reader = csv.DictReader(csvfile, dialect='excel')
        for row in reader:
            name = transmorgify(row['Member Name'])
            s = Sent(parkey          = int(row['ParKey']),
                     member_name     = name,
                     original_email  = row['PreferredEmail'],
                     other_email_1   = row['OtherEmail1'],
                     other_email_2   = row['OtherEmail2'],
                     other_email_3   = row['OtherEmail3'],
                     other_email_4   = row['OtherEmail4'],
                     other_email_5   = row['OtherEmail5'])
            sent.append(s)

    return sent

def read_updated_1():
    updated_1 = list()

    filename = "Epiphany Catholic Church Parishioner Email Update - 1 address.csv"
    with open(filename, 'r') as csvfile:
        reader = csv.DictReader(csvfile, dialect='excel')
        for row in reader:
            name = transmorgify(row['Your name'])
            print("Read: {pk} {name}"
                  .format(pk=row['Family ID/envelope number'], name=name))
            u = Updated(parkey          = int(row['Family ID/envelope number']),
                        member_name     = name,
                        original_email  = row['PreferredEmail (ORIGINAL)'])
            updated_1.append(u)

    return updated_1

def read_updated_multi():
    updated_multi = list()

    filename = "Epiphany Catholic Church Parishioner Email Update - 1 of many addresses.csv"
    with open(filename, 'r') as csvfile:
        reader = csv.DictReader(csvfile, dialect='excel')
        for row in reader:
            name = transmorgify(row['Your name'])
            print("Read multi: {pk} {name}"
                  .format(pk=row['Family ID/envelope number'], name=name))
            u = Updated(parkey          = int(row['Family ID/envelope number']),
                        member_name     = name,
                        original_email  = row['PreferredEmail (ORIGINAL)'])
            updated_multi.append(u)

    return updated_multi

def subtract(sent, updated):
    print("COMPARING")

    newlist = list()
    for s in sent:
        found = False

        for member in updated:
            if False:
                print("Comparing: {spk} {sname} = {mpk} {mname}"
                      .format(spk=s.parkey, sname=s.member_name,
                              mpk=member.parkey, mname=member.member_name))

            if s.parkey == member.parkey and s.original_email == member.original_email:
                found = True
                print("Found match: {spk} {sname} = {mpk} {mname}"
                      .format(spk=s.parkey, sname=s.member_name,
                              mpk=member.parkey, mname=member.member_name))
                break

        if not found:
            newlist.append(s)

    return newlist

def write_to_update(members_who_have_not_updated):
    filename = 'those-who-have-not-updated.csv'
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['ParKey', 'OriginalEmail']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames,
                                quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for member in members_who_have_not_updated:
            writer.writerow({'ParKey': member.parkey,
                             'OriginalEmail': member.original_email})

    print("Wrote file: {}".format(filename))

##############################################################################

def main():
    # Read the list of those to whom we sent emails
    sent = read_sent_mail_list()

    # Read those who have updated 1 email address
    updated_1 = read_updated_1()

    # Read those who have updated multiple email address
    updated_multi = read_updated_multi()

    # Compute to whom we need to send updates
    u1 = subtract(sent, updated_1)
    u2 = subtract(u1, updated_multi)
    print("Length at start: {}".format(len(sent)))
    print("Length after first: {}".format(len(u1)))
    print("Length after second: {}".format(len(u2)))

    write_to_update(u2)

main()
