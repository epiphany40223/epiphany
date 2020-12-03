#!/usr/bin/env python3
#
# Helper routines
#

import sys
sys.path.insert(0, '../../python')

import re

from datetime import datetime
from datetime import timedelta

#--------------------------------------------------------------------------

# "year" is of the form: f'{stewardship_year - 2000 - 1:02}'
def calculate_family_values(family, year, log=None):
    if 'funds' in family and year in family['funds']:
        funds = family['funds'][year]
    else:
        funds = dict()

    if log:
        log.debug(f"Size of family funds dictionary: {len(funds)}")

    # Calculate 3 values:
    # 1. Pledge amount for CY{year}
    # 2. Total amount given in CY{year} so far
    # 3. Family names
    pledged = 0
    for fund in funds.values():
        fund_rate = fund['fund_rate']
        if fund_rate and fund_rate['FDTotal']:
            pledged += int(fund_rate['FDTotal'])

    contributed = 0
    for fund in funds.values():
        for item in fund['history']:
            # Not quite sure how this happens, but sometimes the value is None.
            val = item['item']['FEAmt']
            if val is not None:
                contributed += val

    family['calculated'] = {
        "pledged"        : pledged,
        "contributed"    : contributed,
        "household_name" : household_name(family),
    }

#--------------------------------------------------------------------------

def jotform_date_to_datetime(d):
    # Google is showing three different date formats, depending on how
    # the volumn is formatted (even though they're actually just
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

#--------------------------------------------------------------------------

def member_is_hoh_or_spouse(m):
    if 'Head' in m['type'] or 'Spouse' in m['type']:
        return True
    else:
        return False

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


#--------------------------------------------------------------------------

def url_escape(s):
    return s.replace('\"', '\\"')

def pkey_url(env_id):
    return "' {0}".format(str(env_id).strip())
