#!/usr/bin/env python3.6

import logging.handlers
import argparse
import logging
import sqlite3
import time
import csv
import os
import re

args = None
log = None

verbose = True
debug = False

# Which database number to use?
# At ECC, the active database is 1.
database = 1

#-------------------------------------------------------------------

def diediedie(msg):
    log.error(msg)
    log.error("Aborting")

    send_mail(fatal_notify_to,
              'Fatal error from PDS<-->Google Group sync', msg)

    exit(1)

####################################################################
#
# PDS queries
#
####################################################################

def count_mem_keywords(pds):
    print("=== Member keywords");

    # Get all the member keywords
    keywords = dict()
    query = "select DescRec,Description from MemKWType_DB"
    for row in pds.execute(query).fetchall():
        id   = row[0]
        desc = row[1]

        keywords[id] = desc
        log.debug("Found keyword {kw} (ID: {id})".format(kw=desc, id=id))

    # Write a CSV with the results
    filename = 'member-keywords.csv'
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = [ 'Keyword', 'Count' ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames,
                                quoting=csv.QUOTE_ALL)
        writer.writeheader()

        # For each of those keywords, find out how many active members are
        # using it
        for key in keywords:
            query = '''SELECT count(MemKW_DB.MemRecNum)
FROM   MemKW_DB
       INNER JOIN Mem_DB ON MemKW_DB.MemRecNum = Mem_DB.MemRecNum
WHERE  Mem_DB.deceased = 0 AND
       (Mem_DB.PDSInactive1 = 0 OR Mem_DB.PDSInactive1 is null) AND
       Mem_DB.CensusMember1 = 1 AND
       MemKW_DB.DescRec = {id}'''.format(id=key)

            count = pds.execute(query).fetchone()[0]

            writer.writerow({ 'Keyword' : keywords[key],
                              'Count' : count })
            log.debug("Wrote CSV: keyword={kw}, count={count}"
                      .format(kw=keywords[key], count=count))

#-------------------------------------------------------------------

def count_fam_keywords(pds):
    print("=== Family keywords");

    # Get all the family keywords
    keywords = dict()
    query = "select DescRec,Description from FamKWType_DB"
    for row in pds.execute(query).fetchall():
        id   = row[0]
        desc = row[1]

        keywords[id] = desc
        log.debug("Found keyword {kw} (ID: {id})".format(kw=desc, id=id))

    # Write a CSV with the results
    filename = 'family-keywords.csv'
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = [ 'Keyword', 'Count' ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames,
                                quoting=csv.QUOTE_ALL)
        writer.writeheader()

        # For each of those keywords, find out how many active members are
        # using it
        for key in keywords:
            query = '''SELECT count(FamKW_DB.FamRecNum)
FROM   FamKW_DB
       INNER JOIN Fam_DB ON FamKW_DB.FamRecNum = Fam_DB.FamRecNum
WHERE  (Fam_DB.PDSInactive1 = 0 OR Fam_DB.PDSInactive1 is null) AND
       Fam_DB.CensusFamily1 = 1 AND
       FamKW_DB.DescRec = {id}'''.format(id=key)

            count = pds.execute(query).fetchone()[0]

            writer.writerow({ 'Keyword' : keywords[key],
                              'Count' : count })
            log.debug("Wrote CSV: keyword={kw}, count={count}"
                      .format(kw=keywords[key], count=count))

#-------------------------------------------------------------------

def find_weird_cities(pds):
    print("=== Weird cities")

    # Get all the weird city/states
    cities = dict()
    query = "select CityRec,CityState from City_DB"
    for row in pds.execute(query).fetchall():
        id         = row[0]
        city_state = row[1]

        # If it's weird, keep it
        keep = False
        if '  ' in city_state:
            keep = True
        elif ('.' in city_state and
              not re.search('^Mt. ', city_state) and
              not re.search('^St. ', city_state)):
            keep = True
        elif re.search('\d', city_state):
            keep = True
        elif re.search(', [A-Z][a-z]$', city_state):
            keep = True
        elif re.search(', [a-z][a-z]$', city_state):
            keep = True
        elif re.search(', [a-z][A-Z]$', city_state):
            keep = True
        elif re.search(', ...+$', city_state):
            keep = True

        if not keep:
            continue

        cities[id] = city_state
        log.debug("Found weird city '{city}' (ID: {id})"
                  .format(city=city_state, id=id))

    # Write a CSV with the results
    filename = 'weird-cities.csv'
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = [ 'WeirdCity', 'Count' ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames,
                                quoting=csv.QUOTE_ALL)
        writer.writeheader()

        # For each of those keywords, find out how many active members are
        # using it
        for id in cities:
            query = '''SELECT count(Fam_DB.FamRecNum)
FROM   Fam_DB
       INNER JOIN City_DB ON Fam_DB.StreetCityRec = City_DB.CityRec
WHERE  (Fam_DB.PDSInactive1 = 0 OR Fam_DB.PDSInactive1 is null) AND
       Fam_DB.CensusFamily1 = 1 AND
       Fam_DB.StreetCityRec = {id}'''.format(id=id)

            count = pds.execute(query).fetchone()[0]

            writer.writerow({ 'WeirdCity' : cities[id],
                              'Count' : count })
            log.debug("Wrote CSV: city={city}, count={count}"
                      .format(city=cities[id], count=count))

#-------------------------------------------------------------------

def count_phone_types(pds):
    print("=== Phone types");

    # Get all the phone types
    types = dict()
    query = "select PhoneTypeRec,Description from phonetyp_DB"
    for row in pds.execute(query).fetchall():
        id   = row[0]
        desc = row[1]

        types[id] = desc
        log.debug("Found phone type {type} (ID: {id})".format(type=desc, id=id))

    # Write a CSV with the results
    filename = 'phone-types.csv'
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = [ 'PhoneType', 'Count' ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames,
                                quoting=csv.QUOTE_ALL)
        writer.writeheader()

        # For each of those keywords, find out how many active members are
        # using it
        for id in types:
            query = '''SELECT count(Mem_DB.MemRecNum)
FROM   Mem_DB
       INNER JOIN MemPhone_DB ON MemPhone_DB.Rec = Mem_DB.MemRecNum
WHERE  Mem_DB.deceased = 0 AND
       (Mem_DB.PDSInactive1 = 0 OR Mem_DB.PDSInactive1 is null) AND
       Mem_DB.CensusMember1 = 1 AND
       MemPhone_DB.PhoneTypeRec = {id}'''.format(id=id)

            count = pds.execute(query).fetchone()[0]

            writer.writerow({ 'PhoneType' : types[id],
                              'Count' : count })
            log.debug("Wrote CSV: phonetype={type}, count={count}"
                      .format(type=types[id], count=count))


####################################################################
#
# PDS setup functions
#
# (i.e., open/close SQLite3 database that was previously created from
# the PDS database)
#
####################################################################

def pds_connect():
    global args

    pds_conn = sqlite3.connect(args.sqlite3_db)
    pds_cur = pds_conn.cursor()

    return pds_cur

#-------------------------------------------------------------------

def pds_disconnect(pds):
    pds.close()

####################################################################
#
# Setup functions
#
####################################################################

def setup_logging(args):
    level=logging.ERROR

    if args.debug:
        level="DEBUG"
    elif args.verbose:
        level="INFO"

    global log
    log = logging.getLogger('queries')
    log.setLevel(level)

    # Make sure to include the timestamp in each message
    f = logging.Formatter('%(asctime)s %(levelname)-8s: %(message)s')

    # Default log output to stdout
    s = logging.StreamHandler()
    s.setFormatter(f)
    log.addHandler(s)

#-------------------------------------------------------------------

def setup_cli_args():
    global args

    parser = argparse.ArgumentParser(description='Run some SQLite3 queries')

    parser.add_argument('--sqlite3-db',
                        required=True,
                        help='SQLite3 database containing PDS data')

    global verbose
    parser.add_argument('--verbose',
                        action='store_true',
                        default=verbose,
                        help='If enabled, emit extra status messages during run')
    global debug
    parser.add_argument('--debug',
                        action='store_true',
                        default=debug,
                        help='If enabled, emit even more extra status messages during run')

    args = parser.parse_args()

    # --debug also implies --verbose
    if args.debug:
        args.verbose = True
    setup_logging(args)

####################################################################
#
# Main
#
####################################################################

def main():
    setup_cli_args()

    pds = pds_connect()

    count_mem_keywords(pds)
    count_fam_keywords(pds)
    find_weird_cities(pds)
    count_phone_types(pds)

    pds_disconnect(pds)

if __name__ == '__main__':
    main()
