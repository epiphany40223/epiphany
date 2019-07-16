#!/usr/bin/env python3

import csv
import os

from pprint import pprint

columns = [
    'Date',
    'Time',
    'PDS User',
    'Event',
    'Program',
    'Subgroup',
]

with open('PDSOffice.log', 'rU') as tsvfile:
    with open('PDSOffice.csv', 'w') as csvfile:
        writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
        writer.writerow(columns)

        reader = csv.reader(tsvfile, delimiter='\t',
                            quoting=csv.QUOTE_NONE)

        # There's a row in the log that has a non-UTF8 character in it
        # that screws up the parser (and causes "for row in reader" to
        # fail).  It's the "_" between (502) and 299.  I've previously
        # edited this character out manually.  Would be nice to be
        # able to handle this properly in Python, though...
        """
02/21/2019 5:03:09 PM	Linda	Phone number: (502)_299-2107	PDS Church Office Management	1
        """

        for row in reader:
            # row[0] will be of the form 'aa/bb/cccc hh:mm:ss XM'
            # First plit into 3 parts
            (d, t1, t2) = row[0].split(' ')
            # Then consolidate the 2nd and 3rd parts together
            newrow = [d, t1+t2]
            # Now re-add the rest of the original row
            newrow.extend(row[1:])

            writer.writerow(newrow)
