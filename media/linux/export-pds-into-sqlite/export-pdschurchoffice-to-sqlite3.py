#!/usr/bin/env python3

import subprocess
import argparse
import shutil
import time
import glob
import sys
import os
import re

# We assume that there is a "ecc-python-modules" sym link in this
# directory that points to the directory with ECC.py and friends.
moddir = os.path.join(os.getcwd(), 'ecc-python-modules')
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)

sys.path.insert(0, moddir)

import ECC

# Logging.  It's significantly more convenient if this is a global.
log = None

database_temp_name = time.strftime("pdschurchoffice-%Y-%m-%d-%H%M%S.sqlite3")

###############################################################################

def setup_args():
    parser = argparse.ArgumentParser(description='Import PDS data to a new SQLite3 database.')
    parser.add_argument('--sqlite3',
                        default='sqlite3',
                        help='Path to sqlite3 (if not in PATH)')
    parser.add_argument('--pxview',
                        default='pxview',
                        help='pxview binary (it not found in PATH)')

    parser.add_argument('--pdsdata-dir',
                        default='.',
                        help='Path to find PDS data files')
    parser.add_argument('--out-dir',
                        default='.',
                        help='Path to write output sqlite3 database and temporary .sql files')
    parser.add_argument('--temp-dir',
                        default='tmp',
                        help='Path to write temporary files (safe to remove afterwards) relative to the out directory')

    parser.add_argument('--output-database',
                        default="pdschurch.sqlite3",
                        help='Output filename for the final SQLite3 database')
    parser.add_argument('--logfile',
                        default=None,
                        help='Optional output logfile')

    parser.add_argument('--slack-token-filename',
                        required=True,
                        help='File containing the Slack bot authorization token')

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

#------------------------------------------------------------------------------

# Cleanse / sanity check CLI args

def check_args(args, log):
    pxview_bin = shutil.which(args.pxview)
    if not pxview_bin:
        str = 'Cannot find pxview executable'
        log.critical(str)
        raise Exception(str)
    args.sqlite3 = shutil.which(args.sqlite3)
    if not args.sqlite3:
        str = 'Cannot find sqlite3 executable'
        log.critical(str)
        raise Exception(str)
    if not os.path.exists(args.pdsdata_dir):
        str = f'Cannot find PDS data dir {args.pdsdata_dir}'
        log.critical(str)
        raise Exception(str)

###############################################################################

# Remove the temp directory if it's already there

def setup_temps(args):
    name = os.path.join(args.out_dir, args.temp_dir)
    args.temp_dir = name
    shutil.rmtree(args.temp_dir, ignore_errors=True)
    os.makedirs(args.temp_dir, exist_ok=True)

    global database_temp_name
    name = os.path.join(args.out_dir, database_temp_name)
    database_temp_name = name
    if os.path.exists(database_temp_name):
        os.unlink(database_temp_name)

###############################################################################

# Find the PDS database files
def find_pds_files(args):
    dbs = glob.glob(f'{args.pdsdata_dir}/*.DB')

    return dbs

###############################################################################

# Run sqlite3; we'll be interactively feeding it commands (see below
# for an explanation why).
def open_sqlite3(args):
    sql3_args = list()
    # JMS Why is -echo necessary?  If we don't have it, we seem to get no
    # output :-(
    sql3_args.append('-echo')

    # Write to a temporary database.  We'll rename it at the end.
    global database_temp_name
    sql3_args.append(database_temp_name)

    log.debug(f"sqlite bin: {args.sqlite3}")
    sqlite3 = subprocess.Popen(args=sql3_args,
                               executable=args.sqlite3,
                               universal_newlines=True,
                               stdin=subprocess.PIPE)
    log.info("Opened sqlite3");

    return sqlite3


###############################################################################

def replace_things_not_in_quotes(line, tokens):
    # Unfortunately searching for \bTOKEN\b is not sufficient, because
    # some of these tokens occur inside quoted strings (which we
    # should not change!).  I can't find a simple regexp that will
    # ignore things in strings (e.g., python only allows look-behinds
    # with fixed width patterns), so we're going to do a pedantic -- but
    # hopefully simple -- approach read/maintain approach:
    #
    # 1. We know the line will be well-formed SQL.  Meaning: there
    # will be no line terminated with an open quote / no line opening
    # with a previously-unterminated quote.
    #
    # 2. Split the line into an array of quoted things and unquoted
    # things.
    #
    # 3. Even number entries will be outside quotes (and we should
    # search/replace those).  Odd number entries will be inside quotes
    # (and we should ignore those).
    #
    # Not sexy, but effective.  It unfortunately slows things down
    # compared to a simple regexp, but oh well.  :-(

    f          = re.IGNORECASE
    quote_expr = re.compile(r"^(.+?)('.*?')(.*)")
    word_exprs = list()
    new_tokens = list()

    token_str = r'\b(' + '|'.join(tokens) + r')\b'
    token_expr = re.compile(token_str, flags=f)

    results          = list()
    still_to_process = line
    while (True):
        parts = quote_expr.match(still_to_process)

        # If we didn't match, there were no quotes.  So search the
        # whole still_to_process.  Otherwise, search the first
        # matching group.
        if parts is None:
            str = still_to_process
        else:
            str = parts.group(1)

        # 1st group is what we can search
        match = token_expr.search(str)
        if match:
            # If we found one of the tokens, replace it with the same
            # token but with a "pds" prefix.
            replace = 'pds' + match.group(1).lower()
            str = token_expr.sub(replace, str)
        results.append(str)

        if parts is None:
            break

        # 2nd group is what was in the quotes
        results.append(parts.group(2))

        # 3rd group is what we still have to process
        still_to_process = parts.group(3)

    return ''.join(results)

def process_db(args, db, sqlite3):
    log.info(f"=== PDS table: {db}")

    results = re.search('(.+).DB$', os.path.basename(db))
    table_base = results.group(1)

    # There are sometimes DB filenames that begin with "@".  These are
    # apparently temporary / scratch files (so says PDS support), and
    # should be skipped.
    if table_base.startswith('@'):
        log.info(f"  ==> Skipping bogus {table_base} table")
        return
    if table_base.startswith('SPECIAL'):
        log.info(f"  ==> Skipping bogus {table_base} table")
        return

    # PDS has "PDS" and "PDS[digit]" tables.  "PDS" is the real one;
    # skip "PDS[digit]" tables.  Sigh.  Ditto for RE, SCH.
    if (re.search('^PDS\d+$', table_base, flags=re.IGNORECASE) or
        re.search('^RE\d+$', table_base, flags=re.IGNORECASE) or
        re.search('^SCH\d+$', table_base, flags=re.IGNORECASE)):
        log.info(f"   ==> Skipping bogus {table_base} table")
        return

    # We have the PDS SMB file share opened as read-only, and pxview
    # doesn't like opening files in read-only mode.  So we have to
    # copy the files to a read-write location first.

    # Yes, we use "--sql" here, not "--sqlite".  See the comment below
    # for the reason why.  :-(
    pxview_args = list()
    pxview_args.append(args.pxview)
    pxview_args.append('--sql')

    shutil.copy(db, args.temp_dir)
    temp_db = os.path.join(args.temp_dir, f'{table_base}.DB')
    pxview_args.append(temp_db)

    # Is there an associated blobfile?
    blobname = f'{table_base}.MB'
    blobfile = f"{args.pdsdata_dir}/{blobname}"
    if os.path.exists(blobfile):
        shutil.copy(blobfile, args.temp_dir)
        temp_blobfile = os.path.join(args.temp_dir, blobname)
        pxview_args.append(f'--blobfile={temp_blobfile}')

    # Sadly, we can't have pxview write directly to the sqlite
    # database because PDS has some field names that are SQL reserved
    # words.  :-( Hence, we have to have pxview output the SQL, read
    # the SQL here in Python, then twonk the SQL a bit, and then we
    # can import it into the sqlite3 database using the sqlite3
    # executable.
    sql_file = f'{args.out_dir}/{table_base}.sql'
    if os.path.exists(sql_file):
        os.unlink(sql_file)
    pxview_args.append('-o')
    pxview_args.append(sql_file)

    # Write out the SQL file
    if args.debug:
        log.debug(f'=== PXVIEW command: {args.pxview} {pxview_args}')
    subprocess.run(args=pxview_args)

    if args.debug:
        log.debug('Final SQL:')

    # Must use latin-1 encoding: utf-8 will choke on some of the
    # characters (not sure exactly which ones -- e.g., there are
    # characters in Fam.sql that will cause exceptions in utf-8
    # decoding).
    sf = open(sql_file, 'r', encoding='latin-1')

    # Go through all the lines in the file
    transaction_started = False
    for line in list(sf):
        line = line.strip()

        # Starting with PDS 9.0G, some table names are "resttemp.DB",
        # instead of matching whatever the filename is (e.g., Mem.DB
        # has a table name of "resttemp.DB").  Needless to say, having
        # a bunch of tables with the same name creates problems when
        # we insert them all into a single database.  So intercept
        # those and rename them back to their filename.
        table_name = table_base + "_DB"
        line = re.sub('resttemp_DB', table_name, line)

        # PDS uses some fields named "order", "key", "default", etc.,
        # which are keywords in SQL
        line = replace_things_not_in_quotes(line,
                                            [ 'order',
                                              'key',
                                              'default',
                                              'check',
                                              'both',
                                              'owner',
                                              'access',
                                              'sql' ])

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
            log.debug(f"SQL: {line.rstrip()}")

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
def close_sqlite3(sqlite3):
    sqlite3.stdin.write('\n.exit\n')
    sqlite3.communicate()

# Rename the temp database to the final database name
def rename_sqlite3_database(args):
    # Once we are done writing the new database, atomicly rename it into
    # the final database name.
    global database_temp_name
    final_filename = os.path.join(args.out_dir, args.output_database)
    os.rename(src=database_temp_name, dst=final_filename)

###############################################################################

def main():
    args = setup_args()
    global log
    log = ECC.setup_logging(info=args.verbose,
                            debug=args.debug,
                            logfile=args.logfile, rotate=True,
                            slack_token_filename=args.slack_token_filename)
    check_args(args, log)

    setup_temps(args)
    dbs     = find_pds_files(args)
    sqlite3 = open_sqlite3(args)
    for db in dbs:
        process_db(args, db, sqlite3)
    close_sqlite3(sqlite3)

    log.info("Finished converting DB --> Sqlite")
    rename_sqlite3_database(args)

if __name__ == '__main__':
    main()
