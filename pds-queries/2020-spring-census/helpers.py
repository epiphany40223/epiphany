#!/usr/bin/env python3
#
# Helper routines
#

import sys
sys.path.insert(0, '../../python')

import re

from pprint import pprint
from pprint import pformat
from datetime import datetime
from datetime import timedelta
from datetime import date

None_date = date(year = 1899, month = 12, day = 30)

#--------------------------------------------------------------------------

def jotform_date_to_datetime(d):
    # Google is showing three different date formats, depending on how
    # the column is formatted (even though they're actually just
    # different representations of the same date).  Shug.  Handle them
    # all.
    result = re.match('(\d{4})-(\d{2})-(\d{2}) (\d{1,2}):(\d{2}):(\d{2})', d)
    if result is not None:
        submit_date = datetime(year   = int(result.group(1)),
                               month  = int(result.group(2)),
                               day    = int(result.group(3)),
                               hour   = int(result.group(4)),
                               minute = int(result.group(5)),
                               second = int(result.group(6)))

    else:
        result = re.match('(\d{1,2})/(\d{1,2})/(\d{4}) (\d{1,2}):(\d{2}):(\d{2})', d)
        if result:
            submit_date = datetime(year   = int(result.group(3)),
                                   month  = int(result.group(1)),
                                   day    = int(result.group(2)),
                                   hour   = int(result.group(4)),
                                   minute = int(result.group(5)),
                                   second = int(result.group(6)))

        else:
            # According to
            # https://www.ablebits.com/office-addins-blog/2019/08/13/google-sheets-change-date-format/,
            # Google Sheets uses "0" as December 30, 1899.
            submit_date = datetime(month=12, day=30, year=1899)

            delta = timedelta(days=float(d))
            submit_date += delta

    return submit_date

def jotform_date_to_date(d):
    if d == '':
        return None_date

    # Google is showing multiple different date formats, depending on how
    # the column is formatted (even though they're actually just
    # different representations of the same date).  Shug.  Handle them
    # all.
    result = re.match('(\d{4})-(\d{2})-(\d{2})', d)
    if result is not None:
        submit_date = date(year   = int(result.group(1)),
                               month  = int(result.group(2)),
                               day    = int(result.group(3)))
        return submit_date

        result = re.match('(\d{1,2})/(\d{1,2})/(\d{4})', d)
    if result:
        submit_date = date(year   = int(result.group(3)),
                               month  = int(result.group(1)),
                               day    = int(result.group(2)))
        return submit_date

    result = re.match('(\d{2})-(\d{2})-(\d{4})', d)
    if result is not None:
        submit_date = date(year   = int(result.group(3)),
                               month  = int(result.group(1)),
                               day    = int(result.group(2)))
        return submit_date

    # According to
    # https://www.ablebits.com/office-addins-blog/2019/08/13/google-sheets-change-date-format/,
    # Google Sheets uses "0" as December 30, 1899.
    submit_date  = None_date
    delta        = timedelta(days=float(d))
    submit_date += delta
    return submit_date

#--------------------------------------------------------------------------

def member_is_hoh_or_spouse(m):
    if 'Head' in m['type'] or 'Spouse' in m['type']:
        return True
    else:
        return False

#--------------------------------------------------------------------------

def filter_parishioner_families_only(families, log):
    filtered_families = dict()
    for fid, family in families.items():
        # Fake Families start with ID 9000
        id = int(family['ParKey'].strip())
        if id > 0 and id < 9000:
            filtered_families[fid] = family
        else:
            log.info(f"Filtered non-parishioner Family: {family['Name']}")

    return filtered_families

#--------------------------------------------------------------------------

def household_name(family):
    # The format is:
    # HoHLast,HohFirst[(SPOUSE)],HohTitle,HohSuffix
    #
    # SPOUSE will be:
    # (SpFirst) or
    # (SpLast,SpFirst[,SpTitle][,SpSuffix])
    hoh_name     = family['Name']
    hoh_names    = dict()
    spouse_name  = None
    spouse_names = dict()

    result = re.search('^(.+)\((.+)\)(.*)$', family['Name'])
    if result:
        hoh_name = result.group(1)
        if result.group(3):
            hoh_name += result.group(3)
        spouse_name = result.group(2)

    # Parse out the Head of Household name
    parts = hoh_name.split(',')
    hoh_names['last'] = parts[0]
    if len(parts) > 1:
        hoh_names['first'] = parts[1]
    if len(parts) > 2:
        hoh_names['prefix'] = parts[2]
    if len(parts) > 3:
        hoh_names['suffix'] = parts[3]

    # Parse out the Spouse name
    if spouse_name:
        parts = spouse_name.split(',')
        if len(parts) == 1:
            spouse_names['last']  = hoh_names['last']
            spouse_names['first'] = parts[0]
        elif len(parts) == 2:
            spouse_names['last']  = parts[0]
            spouse_names['first'] = parts[1]
        if len(parts) > 2:
            spouse_names['prefix'] = parts[2]
        if len(parts) > 3:
            spouse_names['suffix'] = parts[3]
    else:
        spouse_names = dict()

    # Make the final string name to be returned
    name = hoh_names['first']
    if 'first' in spouse_names:
        if hoh_names['last'] == spouse_names['last']:
            name += (' and {sf} {last}'
                    .format(sf=spouse_names['first'],
                            last=hoh_names['last']))
        else:
            name += (' {hlast} and {sfirst} {slast}'
                    .format(hlast=hoh_names['last'],
                            sfirst=spouse_names['first'],
                            slast=spouse_names['last']))
    else:
        name += ' ' + hoh_names['last']

    return name
