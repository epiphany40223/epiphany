#!/usr/bin/env python

import subprocess
import argparse
import shutil
import time
import glob
import os
import re

sqlite3_bin = "sqlite3"
pxview_bin = "pxview"
data_dir = '.'
database_name = time.strftime("pdschurchoffice-%Y-%m-%d-%H%M%S.sqlite3")

# JMS Override:
database_name = "pdschurch.sqlite3"

###############################################################################

parser = argparse.ArgumentParser(description='Import PDS data to a new SQLite3 database.')
parser.add_argument('--sqlite3',
                    default=sqlite3_bin,
                    help='Path to sqlite3 (if not in PATH)')
parser.add_argument('--sqlite3-db-name',
                    default=database_name,
                    help='Name of output sqlite3 database name')
parser.add_argument('--pxview',
                    default=pxview_bin,
                    help='pxview binary (it not found in PATH)')
parser.add_argument('--pdsdata-dir',
                    default=data_dir,
                    help='Path to find PDS data files')
parser.add_argument('--debug',
                    default=False,
                    action='store_true',
                    help='Enable extra debugging')

args = parser.parse_args()

#------------------------------------------------------------------------------

# Cleanse / sanity check CLI args

pxview_bin = shutil.which(args.pxview)
if not pxview_bin:
    raise Exception('Cannot find pxview executable')
sqlite3_bin = shutil.which(args.sqlite3)
if not sqlite3_bin:
    raise Exception('Cannot find sqlite3 executable')
if not os.path.exists(args.pdsdata_dir):
    raise Exception('Cannot find PDS data dir {}'.format(args.pdsdata_dir))

###############################################################################

# Remove the database file if it's already there

if os.path.exists(args.sqlite3_db_name):
    os.unlink(args.sqlite3_db_name)

###############################################################################

# Find the PDS database files

dbs = glob.glob('{dir}/*.DB'.format(dir=args.pdsdata_dir))

###############################################################################

# Run sqlite3; we'll be interactively feeding it commands (see below
# for an explanation why).
sql3_args = list()
if args.debug:
    sql3_args.append('-echo')
sql3_args.append(args.sqlite3_db_name)

print("sqlite bin: {}".format(sqlite3_bin))
sqlite3 = subprocess.Popen(args=sql3_args,
                           executable=sqlite3_bin,
                           universal_newlines=True,
                           stdin=subprocess.PIPE)
print("Opened");

# This helps SQLite performance considerably (it's slightly risky, in
# general, because it removes some atomic-ness of transactions, but
# for this application, it's fine).
# JMS Apparently this syntax is wrong...?
#cmd = 'PRAGMA {db}.synchronous=0;\n'.format(db=args.sqlite3_db_name)
#sqlite3.stdin.write('PRAGMA {db}.synchronous=0;\n'.format(db=args.sqlite3_db_name))

###############################################################################

for db in dbs:
    print("=== PDS table: {full}".format(full=db))

    results = re.search('(.+).DB$', os.path.basename(db))
    table_base = results.group(1)

    # PDS has "PDS" and "PDS[digit]" tables.  "PDS" is the real one;
    # skip "PDS[digit]" tables.  Sigh.  Ditto for RE, SCH.
    if (re.search('^PDS\d+$', table_base, flags=re.IGNORECASE) or
        re.search('^RE\d+$', table_base, flags=re.IGNORECASE) or
        re.search('^RE\d+.DB$', table_base, flags=re.IGNORECASE) or
        re.search('^SCH\d+$', table_base, flags=re.IGNORECASE)):
        print("   ==> Skipping bogus {short} table".format(short=table_base))
        continue

    # PDS also has a duplicate table "resttemp_db" in the AskRecNum
    # and RecNum databases.  They appear to be empty, so just skip
    # them.
    if (re.search('^AskRecNum$', table_base, flags=re.IGNORECASE) or
        re.search('^RecNum$', table_base, flags=re.IGNORECASE)):
        print("   ==> Skipping bogus {short} table".format(short=table_base))
        continue

    # We dont' currently care about the *GIANT* databases (that take
    # -- literally -- hours to import on an RPi).
    if (re.search('fund', table_base, flags=re.IGNORECASE)):
        print("   ==> Skipping giant {short} table".format(short=table_base))
        continue

    # Yes, we use "--sql" here, not "--sqlite".  See the comment below
    # for the reason why.  :-(
    pxview_args = list()
    pxview_args.append(pxview_bin)
    pxview_args.append('--sql')
    pxview_args.append(db)

    # Is there an associated blobfile?
    blobfile = "{dir}/{short}.MB".format(dir=args.pdsdata_dir, short=table_base)
    if os.path.exists(blobfile):
        pxview_args.append('--blobfile={file}'.format(file=blobfile))

    # Sadly, we can't have pxview write directly to the sqlite
    # database because PDS has some field names that are SQL reserved
    # words.  :-( Hence, we have to have pxview output the SQL, read
    # the SQL here in Python, then twonk the SQL a bit, and then we
    # can import it into the sqlite3 database using the sqlite3
    # executable.
    sql_file = '{dir}/{base}.sql'.format(dir=args.pdsdata_dir, base=table_base)
    if os.path.exists(sql_file):
        os.unlink(sql_file)
    pxview_args.append('-o')
    pxview_args.append(sql_file)

    # Write out the SQL file
    if args.debug:
        print('=== PXVIEW command: {pxview} {args}'
              .format(pxview=pxview_bin, args=pxview_args))
    subprocess.run(args=pxview_args)

    if args.debug:
        print('Final SQL:')

    # Must use latin-1 encoding: utf-8 will choke on some of the
    # characters (not sure exactly which ones -- e.g., there are
    # characters in Fam.sql that will cause exceptions in utf-8
    # decoding).
    sf = open(sql_file, 'r', encoding='latin-1')

    # Go through all the lines in the file
    f = re.IGNORECASE
    transaction_started = False
    for line in list(sf):

        # PDS uses some fields named "order", "key", "default", etc.,
        # which are keywords in SQL
        line = re.sub(r'\border\b', 'pdsorder', line, flags=f)
        line = re.sub(r'\bkey\b', 'pdskey', line, flags=f)
        line = re.sub(r'\bdefault\b', 'pdsdefault', line, flags=f)
        line = re.sub(r'\bcheck\b', 'pdscheck', line, flags=f)
        line = re.sub(r'\bboth\b', 'pdsboth', line, flags=f)
        line = re.sub(r'\bowner\b', 'pdsowner', line, flags=f)
        line = re.sub(r'\baccess\b', 'pdsaccess', line, flags=f)
        line = re.sub(r'\bsql\b', 'pdssql', line, flags=f)

        # SQLite does not have a boolean class; so turn TRUE and FALSE
        # into 1 and 0.
        line = re.sub('TRUE', '1', line)
        line = re.sub('FALSE', '0', line)

        # PDS Puts dates into YYYY-MM-DD, which sqlite3 will turn into
        # a mathematical expression.  So quote it so that sqlite3 will
        # treat it as a string.
        line = re.sub(r', (\d\d\d\d-\d\d-\d\d)([,)])', r', "\1"\2', line)
        # Must do this twice (!) because Python re will not replace
        # two overlapping patterns (i.e., if the string contains ',
        # 2005-03-03, 2005-04-04', those two patterns overlap, and the
        # 2nd one will not be replaced).
        line = re.sub(r', (\d\d\d\d-\d\d-\d\d)([,)])', r', "\1"\2', line)

        if args.debug:
            print("SQL: {}".format(line.rstrip()))

        # If we're insertting and we haven't started the transaction,
        # start the transaction.
        if not transaction_started and re.search('insert', line, flags=re.IGNORECASE):
            sqlite3.stdin.write('BEGIN TRANSACTION;\n')
            transaction_started = True

        sqlite3.stdin.write(line)

    if transaction_started:
        sqlite3.stdin.write('END TRANSACTION;\n')

    sf.close()
    os.unlink(sql_file)

###############################################################################

# Close down sqlite3

sqlite3.stdin.write('.exit\n')
sqlite3.communicate()
