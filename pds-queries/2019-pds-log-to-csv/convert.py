#!/usr/bin/env python3

import csv
import os

from pprint import pprint

filename_in  = 'PDSOffice.log'
filename_out = 'PDSOffice.csv'

columns = [
    'Date',
    'Time',
    'PDS User',
    'Event',
    'Program',
    'Subgroup',
]

# There's a row in the log that has a non-UTF8 character in it that screws up
# the parser (and causes "for row in reader" to fail).  It's the " " (some
# editors render this as a blank, but it's not a blank) between (502) and 299.
# Because of this, we have to read the file in manually, edit out this crazy
# character, and then pass the lines through the CSV reader (vs. just passing
# the file to the CSV reader).
"""
02/21/2019 5:03:09 PM	Linda	Phone number: (502)_299-2107	PDS Church Office Management	1
"""

lines = list()
with open(filename_in, 'rb') as logfile:
    for line in logfile:
        try:
            new_line = line.decode("utf-8")
        except UnicodeDecodeError:
            # Skip this line -- we know it's both bad and meaningless.
            continue

        lines.append(new_line)

with open(filename_out, 'w') as csvoutfile:
    writer = csv.writer(csvoutfile, quoting=csv.QUOTE_ALL)
    writer.writerow(columns)

    reader = csv.reader(lines, delimiter='\t',
                    quoting=csv.QUOTE_NONE)

    for row in reader:
            # row[0] will be of the form 'aa/bb/cccc hh:mm:ss XM'
            # First plit into 3 parts
            (d, t1, t2) = row[0].split(' ')
            # Then consolidate the 2nd and 3rd parts together
            newrow = [d, t1+t2]
            # Now re-add the rest of the original row
            newrow.extend(row[1:])

            writer.writerow(newrow)

print("Wrote {}".format(filename_out))
