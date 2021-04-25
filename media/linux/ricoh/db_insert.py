#!/usr/bin/env python3

# Script to import a CSV downloaded from the Ricoh printer into an SQLite3
# database.  If the database does no exist, create it.

import os
import csv
import sys
import sqlite3
import argparse
import datetime

# Load the ECC python modules.  There will be a sym link off this directory.
moddir = os.path.join(os.path.dirname(sys.argv[0]), 'ecc-python-modules')
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)

sys.path.insert(0, moddir)

import ECC

###########################################################

# Map SQLite field names to the CSV column names.
# All of these values are integers in the CSV (or blank).
# There are a small number of other non-integer fields that are not in this
# dictionary.
fields = {
    'total'                     : 'Total Prints',
    'bwTotal'                   : 'B & W(Total Prints)',
    'colorTotal'                : 'Color(Total Prints)',
    'bwResult'                  : 'B & W:Result(Total Prints)',
    'colorResult'               : 'Color:Result(Total Prints)',
    'bwCopier'                  : 'Black & WhiteTotal(Copier/Document Server)',
    'bwSmallCopier'             : 'Black & White(Small size)(Copier/Document Server)',
    'bwLargeCopier'             : 'Black & White(Large size)(Copier/Document Server)',
    'singleColorCopier'         : 'Single ColorTotal(Copier/Document Server)',
    'singleColorSmallCopier'    : 'Single Color(Small size)(Copier/Document Server)',
    'singleColorLargeCopier'    : 'Single Color(Large size)(Copier/Document Server)',
    'twoColorCopier'            : 'Two-colorTotal(Copier/Document Server)',
    'twoColorSmallCopier'       : 'Two-color(Small size)(Copier/Document Server)',
    'twoColorLargeCopier'       : 'Two-color(Large size)(Copier/Document Server)',
    'fullColorCopier'           : 'Full ColorTotal(Copier/Document Server)',
    'fullColorSmallCopier'      : 'Full Color(Small size)(Copier/Document Server)',
    'fullColorLargeCopier'      : 'Full Color(Large size)(Copier/Document Server)',
    'bwPrinter'                 : 'Black & WhiteTotal(Printer)',
    'bwSmallPrinter'            : 'Black & White(Small size)(Printer)',
    'bwLargePrinter'            : 'Black & White(Large size)(Printer)',
    'singleColorPrinter'        : 'Single ColorTotal(Printer)',
    'singleColorSmallPrinter'   : 'Single Color(Small size)(Printer)',
    'singleColorLargePrinter'   : 'Single Color(Large size)(Printer)',
    'twoColorPrinter'           : 'Two-colorTotal(Printer)',
    'twoColorSmallPrinter'      : 'Two-color(Small size)(Printer)',
    'twoColorLargePrinter'      : 'Two-color(Large size)(Printer)',
    'colorPrinter'              : 'ColorTotal(Printer)',
    'colorSmallPrinter'         : 'Color(Small size)(Printer)',
    'colorLargePrinter'         : 'Color(Large size)(Printer)',
    'scannerTotal'              : 'ScannerTotal(Scanner)',
    'bwScanner'                 : 'Black & WhiteTotal(Scanner)',
    'bwSmallScanner'            : 'Black & White(Small size)(Scanner)',
    'bwLargeScanner'            : 'Black & White(Large size)(Scanner)',
    'colorScanner'              : 'Full ColorTotal(Scanner)',
    'colorSmallScanner'         : 'Full Color(Small size)(Scanner)',
    'colorLargeScanner'         : 'Full Color(Large size)(Scanner)',
    'bwFax'                     : 'Black & WhiteTotal(Fax)',
    'bwSmallFax'                : 'Black & White(Small size)(Fax)',
    'bwLargeFax'                : 'Black & White(Large size)(Fax)',
    'colorFax'                  : 'ColorTotal(Fax)',
    'colorSmallFax'             : 'Color(Small size)(Fax)',
    'colorLargeFax'             : 'Color(Large size)(Fax)',
    'transmissionPagesFax'      : 'Transmission Pages(Fax)',
    'transmissionChargeFax'     : 'Transmission Charge(Fax)',
    'volumeUsed'                : 'Volume Used(Print Volume Use Limitation)',
    'limitValue'                : 'Limit Value(Print Volume Use Limitation)',
    'prevVolumeUsed'            : 'Previous Volume Used(Print Volume Use Limitation)',
    'blackDev'                  : 'Black(Development)',
    'colorDev'                  : 'Color (YMC)(Development)',
    'twoSidedCopier'            : '2 sided Sheets(Copier/Document Server)',
    'combinedCopier'            : 'Combined Pages(Copier/Document Server)',
    'twoSidedPrinter'           : '2 sided Sheets(Printer)',
    'combinedPrinter'           : 'Combined Pages(Printer)',
}

###########################################################

# loads the new csv, returns list of the rows
def load_csv(log, filename):

    csv_rows = list()
    with open(filename, encoding='utf-8') as csvfile:
        csvreader = csv.DictReader(csvfile)
        for row in csvreader:
            csv_rows.append(row)

    log.debug(f"== Loaded {len(csv_rows)} rows from CSV")
    return csv_rows


# extracts the data from the csv, returns list of staffers and their info
def extract_csv_data(log, csv_rows):

    def _extract_row(row):
        # Initialize with the non-integer values in the data
        extracted_row = {
            'department'    : row['User'].strip(),
            'name'          : row['Name'].strip(),
            # I don't really know what this value is, but let's keep it anyway;
            # we might want it someday.
            'lastResetDate' : row['Last Reset Date(Print Volume Use Limitation)'].strip(),
        }

        for sql_fieldname, csv_fieldname in fields.items():
            # The Ricoh data will be '' or '-' if the value is actually 0.
            # Make sure the value we extract is always an integer.
            value = row[csv_fieldname].strip()
            if value == '' or value == '-':
                extracted_row[sql_fieldname] = 0
            else:
                extracted_row[sql_fieldname] = int(value)

        return extracted_row

    output = list()
    for row in csv_rows:
        this_row = _extract_row(row)
        output.append(this_row)

    log.debug(f"== Extracted {len(output)} rows from CSV")
    return output


def open_db(log, filename):
    # If the database exists, just open and return it
    if os.path.exists(filename):
        return sqlite3.connect(filename)

    # Otherwise, create the database and its schema.
    # Specifically mention the non-integer fields that are not in the
    # "fields" dictionary:
    # - key: unique key ID for the row
    # - inserttimestamp: the timestamp at which the data was entered into the db
    # - timestamp: the timestamp of the data
    # - department: the Ricoh department ID
    # - name: the Ricoh username
    conn = sqlite3.connect(filename)
    c    = conn.cursor()
    sql  = 'CREATE TABLE IF NOT EXISTS printlog ('
    for sql_fieldname in fields:
        sql += f'{sql_fieldname} integer NOT NULL,'
    sql += '''Key integer primary key,
            InsertTimestamp default current_timestamp NOT NULL,
            Timestamp text NOT NULL,
            department text NOT NULL,
            name text NOT NULL,
            lastResetDate text NOT NULL)'''

    log.debug(f"Creating schema with SQL: {sql}")

    c.execute(sql)
    conn.commit()

    return conn


def write_to_db(log, timestamp, csv, conn):
    c = conn.cursor()

    # Use the first extracted CSV row to make the template SQL
    # (because all the CSV rows will contain the same fields)
    sorted_fields = sorted(csv[0])
    sql = ('INSERT INTO printlog (' +
            ','.join(sorted_fields) +
            ', Timestamp) VALUES (' +
            ('?,' * len(sorted_fields)) +
            '?)')
    log.debug(f"Insert row template SQL: {sql}")

    # Insert each CSV row's value into the database
    for row in csv:
        values = [ row[x] for x in sorted_fields ]
        values.append(timestamp)
        values_tuple = tuple(values)
        log.debug(f"SQL insert values tuple: {values_tuple}")
        c.execute(sql, values_tuple)

    # Commit those inserts to the database
    conn.commit()
    log.info(f"Inserted {len(csv)} rows into the database")


def setup_cli_args():
    parser = argparse.ArgumentParser(description='Import Ricoh data into an SQLite3 database.')
    parser.add_argument('--csv',
                        required=True,
                        help='Path to CSV file containing Ricoh values to import to the database')
    parser.add_argument('--db',
                        required=True,
                        help='Path to write output sqlite3 database')
    parser.add_argument('--timestamp',
                        default=datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                        help='Use this GMT "yyyy-mm-dd hh:mm:ss" timestamp when inserting into the database')

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


def main():
    args = setup_cli_args()
    log  = ECC.setup_logging(info=args.verbose,
                             debug=args.debug,
                             logfile=args.logfile, rotate=True,
                             slack_token_filename=args.slack_token_filename)

    csv_rows = load_csv(log, args.csv)
    csv      = extract_csv_data(log, csv_rows)
    conn     = open_db(log, args.db)
    write_to_db(log, args.timestamp, csv, conn)
    conn.close()

if __name__ == "__main__":
    main()
