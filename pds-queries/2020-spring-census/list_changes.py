#!/usr/bin/env python3

# Basic script to create a list of families which have not responded to the
# 2020 spring census. This version is based on a CSV file import, so you will
# need to retrieve the latest file.

import sys
sys.path.insert(0, '../../python')

import os
import csv
import re
import sqlite3

import ECC
import PDSChurch

from pprint import pprint
from pprint import pformat

#############################################################################

def main():
    log = ECC.setup_logging(debug=False)

    (pds, families,
    members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    log=log)

    families_replied = list()
    with open('ECC census update - Sheet1.csv', encoding='utf-8') as csvfile:
        csvreader = csv.DictReader(csvfile)
        for row in csvreader:
            families_replied.append(row)

    family_list = list()
    member_list = list()
    for row in families_replied:
        this_family = {
            'fid' : row['fid'].strip(),
            'name' : row['Household name'].strip(),
            'street' : row['Street Address'].strip(),
            'street2' : row['Street Address Line 2'].strip(),
            'city' : (row['City'].strip()+' '+row['State'].strip()),
            'zip' : row['Zip Code'].strip(),
            'phone' : row['Land line phone number (leave blank if you have no land line)'].strip()
        }
        family_list.append(this_family)
        for x in range(1,8):
            if(row[f'mid{x}'] != ''):
                this_member = pullMember(x,row)
                member_list.append(this_member)
    print(len(member_list))

    family_changelog = list()
    for row in family_list:
        for family in families.values():
            if(int)(row['fid']) == family['FamRecNum']:
                family_changes = compareFamily(row, family)
                family_changelog.append(family_changes)
                break
    
    member_changelog = list()
    for row in member_list:
        for member in members.values():
            if(int)(row['mid']) == member['MemRecNum']:
                member_changes = compareMember(row, member)
                member_changelog.append(member_changes)
                break

    with open("familychangelog.txt", "w+", encoding="utf-8") as f:
        for row in family_changelog:
            if len(row)>0: f.write(f"{row}\n")
    with open("memberchangelog.txt", "w+", encoding="utf-8") as f:
        for row in member_changelog:
            if len(row)>0: f.write(f"{row}\n")




def pullMember(num, row):
    if(num == 1):
        this_member = {
            'mid' : row['mid1'].strip(),
            'title' : row['Title'].strip(),
            'first' : row['Legal first name'].strip(),
            'nickname' : row['Nickname (only if different than legal first name)'].strip(),
            'middle' : row['Middle name'].strip(),
            'last' : row['Last name'].strip(),
            'suffix' : row['Suffix (if applicable)'].strip(),
            'year' : row['Year of birth'].strip(),
            'email' : row['Preferred email address'].strip(),
            'phone' : row['Cell phone number'].strip(),
            'sex' : row['Sex'].strip(),
            'marital' : row['Marital status'].strip(),
            'wedding' : fixWeddingDate(row[f'Wedding date (if applicable)'].strip()),
            'occupation' : row['Occupation (if retired, indicate previous occupation)'].strip(),
            'employer' : row['Employer / School attending (Kindergarten thru College, if applicable)'].strip(),
        }
        return this_member
    else:
        this_member = {
            'mid' : row[f'mid{num}'].strip(),
            'title' : row[f'Title {num}'].strip(),
            'first' : row[f'Legal first name {num}'].strip(),
            'nickname' : row[f'Nickname (only if different than legal first name) {num}'].strip(),
            'middle' : row[f'Middle name {num}'].strip(),
            'last' : row[f'Last name {num}'].strip(),
            'suffix' : row[f'Suffix (if applicable) {num}'].strip(),
            'year' : row[f'Year of birth {num}'].strip(),
            'email' : row[f'Preferred email address {num}'].strip(),
            'phone' : row[f'Cell phone number {num}'].strip(),
            'sex' : row[f'Sex {num}'].strip(),
            'marital' : row[f'Marital status {num}'].strip(),
            'wedding' : fixWeddingDate(row[f'Wedding date (if applicable) {num}'].strip()),
            'occupation' : row[f'Occupation (if retired, indicate previous occupation) {num}'].strip(),
            'employer' : row[f'Employer / School attending (Kindergarten thru College, if applicable) {num}'].strip(),
        }
        return this_member

def compareFamily(row, family):
    changes = list()
    if row['street'] != family['StreetAddress1'] and row['street'] != '':
        changes.append(f"Street Address changed from {family['StreetAddress1']} to {row['street']}")
    #else: changes.append("")
    if row['street2'] != family['StreetAddress2'] and row['street2'] != '':
        changes.append(f"StreetAddress2 changed from {family['StreetAddress2']} to {row['street2']}")
    #else: changes.append("")
    if row['city'] != family['city_state'] and row['city'] != '':
        changes.append(f"City changed from {family['city_state']} to {row['city']}")
    #else: changes.append("")
    if row['zip'] != family['StreetZip'] and row['zip'] != '':
        changes.append(f"Zip code changed from {family['StreetZip']} to {row['zip']}")
    #else: changes.append("")
    #if row['phone'] != '':
    #   changes.append(f"Landline phone number added: {row['phone']}")
    #else: changes.append("")
    if len(changes)>0: changes.insert(0, row['fid'])
    changelog = ",".join(changes)
    return changelog

def compareMember(row, member):
    changes = list()
    if row['title'] != member['prefix'] and row['title'] != '':
        changes.append(f"Member title changed from {member['prefix']} to {row['title']}")
    #else: changes.append("")
    if row['first'] != member['first'] and row['first'] != '':
        changes.append(f"First name changed from {member['first']} to {row['first']}")
    #else: changes.append("")
    if row['middle'] != member['middle'] and row['middle'] != '':
        changes.append(f"Middle name changed from {member['middle']} to {row['middle']}")
    #else: changes.append("")
    if row['last'] != member['last'] and row['last'] != '':
        changes.append(f"Last name changed from {member['last']} to {row['last']}")
    #else: changes.append("")
    if row['nickname'] != member['nickname'] and row['nickname'] != '':
        changes.append(f"Nickname changed from {member['nickname']} to {row['nickname']}")
    #else: changes.append("")
    if row['suffix'] != member['suffix'] and row['suffix'] != '':
        changes.append(f"Suffix changed from {member['suffix']} to {row['suffix']}")
    #else: changes.append("")
    if catchMissingYear(row['year']) and (int)(row['year']) != (int)(member['YearOfBirth']) and row['year'] != '':
        changes.append(f"Birth Year updated from {member['YearOfBirth']} to {row['year']}")
    #else: changes.append("")
    #if row['email'] not in member['preferred_emails'] and row['email'] != '':
    #   changes.append(f"Email {row['email']} added")
    #else: changes.append("")
    #if row['phone'] != '':
    #   changes.append(f"Phone Number {row['phone']} added")
    #else: changes.append("")
    if row['sex'] != member['Gender'] and row['sex'] != '':
        changes.append(f"Gender changed from {member['Gender']} to {row['sex']}")
    #else: changes.append("")
    #if row['marital'] != member['marital_status'] and row['marital'] != '':
    #   changes.append(f"Marital status changed from {member['marital_status']} to {row['marital']}")
    #else: changes.append("")
    #if (str)(row['wedding']) != (str)(member['marriage_date']) and row['wedding'] != '':
    #   changes.append(f"Wedding date updated from {member['marriage_date']} to {row['wedding']}")
    #else: changes.append("")
    #if row['occupation'] != member['occupation'] and row['occupation'] != '':
    #   changes.append(f"Occupation changed from {member['occupation']} to {row['occupation']}")
    #else: changes.append("")
    #if row['employer'] != '':
    #   changes.append(f"Current employer updated to {row['employer']}")
    #else: changes.append("")
    if len(changes)>0: changes.insert(0, row['mid'])
    changelog = ", ".join(changes)
    return changelog

def fixWeddingDate(value):
    date = value.split('-', 2)
    if len(date)<2 : return ""
    else: 
        fixedDate = f"{date[2]}-{date[0]}-{date[1]}"
        return fixedDate

def catchMissingYear(value):
    if (value==""): return False
    else: return True

main()
