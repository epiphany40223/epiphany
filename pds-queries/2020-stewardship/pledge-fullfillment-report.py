#!/usr/bin/env python3

# This report is to map how Families want to fill their pledges to a
# PDS keyword and make a CSV suitable for importing.

import sys
sys.path.insert(0, '../../python')

import collections
import traceback
import datetime
import argparse
import csv
import os
import re

import ECC
import Google
import PDSChurch
import GoogleAuth

import helpers

from pprint import pprint
from pprint import pformat
from datetime import datetime
from datetime import timedelta

from oauth2client import tools

#------------------------------------------------------------------------------

from constants import jotform_member_ministries
from constants import jotform_ministry_groups
from constants import jotform_member_fields
from constants import jotform_family_fields
from constants import already_submitted_fam_status

from constants import gapp_id
from constants import guser_cred_file
from constants import jotform_member_gfile_id
from constants import jotform_family_gfile_id
from constants import upload_team_drive_folder_id
from constants import gsheet_editors

from constants import ministry_start_date
from constants import ministry_end_date

from constants import title
from constants import stewardship_begin_date
from constants import stewardship_end_date

from constants import smtp_server
from constants import smtp_from

from constants import email_image_url
from constants import api_base_url

##############################################################################

email_to = 'jsquyres@gmail.com'

##############################################################################

def upload_to_gsheet(google, folder_id, filename, fieldnames, csv_rows,
                remove_csv, log):
    if csv_rows is None or len(csv_rows) == 0:
        return None, None

    # First, write out a CSV file
    csv_filename = filename
    try:
        os.remove(csv_filename)
    except:
        pass

    csvfile = open(csv_filename, 'w')
    writer  = csv.DictWriter(csvfile, fieldnames=fieldnames,
                            quoting=csv.QUOTE_ALL)
    writer.writeheader()
    for row in csv_rows:
        writer.writerow(row)
    csvfile.close()

    # Now upload that file to Google Drive
    try:
        log.info('Uploading file to google "{file}"'
              .format(file=filename))
        metadata = {
            'name'     : filename,
            'mimeType' : Google.mime_types['sheet'],
            'parents'  : [ folder_id ],
            'supportsTeamDrives' : True,
            }
        media = MediaFileUpload(csv_filename,
                                mimetype=Google.mime_types['sheet'],
                                resumable=True)
        file = google.files().create(body=metadata,
                                     media_body=media,
                                     supportsTeamDrives=True,
                                     fields='id').execute()
        log.debug('Successfully uploaded file: "{filename}" (ID: {id})'
              .format(filename=filename, id=file['id']))

    except:
        log.error('Google upload failed for some reason:')
        log.error(traceback.format_exc())
        exit(1)

    # Set permissions on the GSheet to allow the stewardship 2020
    # workers group to edit the file (if you are view-only, you
    # can't even adjust the column widths, which will be
    # problematic for the comments report!).
    try:
        perm = {
            'type': 'group',
            'role': 'writer',
            'emailAddress': gsheet_editors,
        }
        out = google.permissions().create(fileId=file['id'],
                                          supportsTeamDrives=True,
                                          sendNotificationEmail=False,
                                          body=perm,
                                          fields='id').execute()
        log.debug("Set Google permission for file: {id}"
                 .format(id=out['id']))
    except:
        log.error('Google set permission failed for some reason:')
        log.error(traceback.format_exc())
        exit(1)

    # Remove the temp file when we're done
    if remove_csv:
        try:
            os.remove(csv_filename)
            csv_filename = None
        except:
            pass

    return file['id'], csv_filename

##############################################################################

def pledge_fullfillment_report(google, pds_families, jotform_pledges, log):

    # Map mechanism to keyword
    mech_field = '2020 mechanism'
    mech_map = {
        '' : '',
        'Bank draft (online bill pay through my bank)' : 'Bank Draft 2020',
        'Online giving: credit card (via Epiphany\'s WeShare service)' : 'CC2020',
        'Online giving: ACH (via Epiphany\'s WeShare service)' : 'ACH2020',
        'A gift of stock to Epiphany' : 'Stock 2020',
        'An IRA distribution directly to Epiphany' : 'IRA 2020',
        'Offertory envelopes' : 'EVIL',
    }

    #-----------------------------------------------------------------

    # Map frequency to keyword
    freq_field = '2020 frequency'
    freq_map = {
        ''                    : '',
        'Weekly donations'    : 'Weekly',
        'Monthly donations'   : 'Monthly',
        'Quarterly donations' : 'Quarterly',
        'One annual donation' : 'Annual',
    }

    #-----------------------------------------------------------------

    csv_rows = list()
    for row in jotform_pledges:
        fid = int(row['fid'])
        if fid not in pds_families:
            continue

        family          = pds_families[fid]
        output_template = {
            'fid' : fid,
            'name' : family['Name'],
            'envelope number' : "'" + family['ParKey'],
        }

        freq_jot      = row['2020 frequency']
        freq_keyword  = freq_map[freq_jot]

        # Only make an output CSV row if the frequency has changed
        if (freq_keyword != '' and
            ('keywords' not in family or
             freq_keyword not in family['keywords'])):
            output = output_template.copy()
            output['keyword to add'] = freq_keyword
            output['comment'] = 'New frequency keyword'
            csv_rows.append(output)

        # Was this a change in frequency?
        if 'keywords' in family:
            for kw in family['keywords']:
                if kw in freq_map and kw != freq_keyword:
                    output = output_template.copy()
                    output['keyword to delete'] = freq_keyword
                    output['comment'] = 'DELETE FREQUENCY'
                    csv_rows.append(output)

        #------------------------------------------------------

        # The mechanism field was a "check all that apply".  Multiple
        # values will be separated by \n.
        envelopes     = 0
        mech_jots     = row['2020 mechanism']
        log.info("Family {f} mechnaism: {m}".format(f=family['Name'], m=mech_jots))
        mech_keywords = list()
        mech_other    = list()
        for mech_jot in mech_jots.splitlines():
            if mech_jot == 'Offertory envelopes':
                envelopes = 1
            elif mech_jot in mech_map:
                mech_keywords.append(mech_map[mech_jot])
            else:
                mech_other.append(mech_jot)

        # Output envelope user only if it's a change
        pds_envelope_user = family['EnvelopeUser']
        if pds_envelope_user is None:
            pds_envelope_user = 0
        log.info("PDS envelope {pds} jotform envelope {jot}"
                 .format(pds=pds_envelope_user, jot=envelopes))
        if pds_envelope_user != envelopes:
            output = output_template.copy()
            output['envelopes'] = envelopes
            output['comment'] = 'Envelope status change'
            csv_rows.append(output)

        # Only add a mechanism keyword if it's a change (which, since
        # these are all 2020 keywords, they should be, but hey:
        # defensive programming).
        for mech_keyword in mech_keywords:
            if not mech_keyword:
                continue

            if ('keywords' in family
                and mech_keyword in family['keywords']):
                continue

            output = output_template.copy()
            output['keyword to add'] = mech_keyword
            output['comment'] = 'New mechanism keyword'
            csv_rows.append(output)

        # Output all comments
        for other in mech_other:
            text = other.strip()
            if not text:
                continue

            output = output_template.copy()
            output['comment'] = "OTHER: " + text
            csv_rows.append(output)

    #---------------------------------------------------------------

    if len(csv_rows) == 0:
        log.warn("No pledge data to output!")
        return

    #---------------------------------------------------------------

    # Output the CSV file
    filename     = 'pledge-fullfillment-report.csv'
    column_names = dict()
    for row in csv_rows:
        for key in row:
            column_names[key] = True

    with open(filename, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=sorted(column_names.keys()),
                                quoting=csv.QUOTE_ALL)
        writer.writeheader()

        for row in csv_rows:
            writer.writerow(row)

    log.info('Wrote file: {f}'.format(f=filename))

##############################################################################

def _export_gsheet_to_csv(service, start, end, google_sheet_id, fieldnames):
    response = service.files().export(fileId=google_sheet_id,
                                      mimeType=Google.mime_types['csv']).execute()

    # At least one of the form questions was a many-of-many (i.e.,
    # multiple options may be checked).  Jotform will return these
    # values separated by \n, but within a single quoted strong.
    #
    # Don't use .splitlines() to split the response.decode() because
    # that will separate the multli-line strings into separate Python
    # list items.  Although DictReader is smart enough to keep going
    # to read a multi-line string that spans multiple Python list
    # items, we've lost the \n by this point, and we therefore have no
    # opprotunity to separate the \n-separated values in the string.
    #
    # Instead, write the response.decode() into a temporary file, and
    # then give a file handle to the temporary file back to
    # DictReader.  Then multi-line strings are read properly by
    # DictReader, and later in the code we can properly split the
    # multi-line strings to see the multiple options.
    filename = 'temp-gsheet-export.csv'
    with open(filename, 'w') as f:
        f.write(response.decode('utf-8'))

    with open(filename, 'r') as f:
        csvreader = csv.DictReader(f, fieldnames=fieldnames)

        rows = list()
        for row in csvreader:
            # Skip title row
            if 'Submission' in row['SubmitDate']:
                continue

            # Is this submission between start and end?
            submit_date = helpers.jotform_date_to_datetime(row['SubmitDate'])
            if submit_date < start or submit_date > end:
                continue

            rows.append(row)

    os.unlink(filename)

    return rows

#-----------------------------------------------------------------------------

def read_jotform(google, start, end, family_gfile_id):
    def _deduplicate(rows, field):
        index = dict()

        # Save the last row number for any given MID/FID
        # (we only really care about the *last* entry that someone makes)
        for i, row in enumerate(rows):
            index[row[field]] = i

        # Now create a new output list that has just that last row for any given
        # MID/FID
        out = list()
        for i, row in enumerate(rows):
            if index[row[field]] == i:
                out.append(row)

        return out

    #------------------------------------------------------------------------

    family_csv = _export_gsheet_to_csv(google, start, end, family_gfile_id,
                                      jotform_family_fields)
    family_csv = _deduplicate(family_csv, 'fid')

    return family_csv

##############################################################################

def setup_args():
    tools.argparser.add_argument('--gdrive-folder-id',
                                 help='If specified, upload a Google Sheet containing the results to this Team Drive folder')

    global gapp_id
    tools.argparser.add_argument('--app-id',
                                 default=gapp_id,
                                 help='Filename containing Google application credentials')
    global guser_cred_file
    tools.argparser.add_argument('--user-credentials',
                                 default=guser_cred_file,
                                 help='Filename containing Google user credentials')

    args = tools.argparser.parse_args()

    return args

##############################################################################

def main():
    global families, members

    args = setup_args()
    log = ECC.setup_logging(debug=False)

    #---------------------------------------------------------------

    log.info("Reading PDS data...")
    (pds, pds_families,
     pds_members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                        log=log)

    # Remove non-parishioner families
    pds_families = helpers.filter_parishioner_families_only(pds_families)

    # Close the databases
    pds.connection.close()

    #---------------------------------------------------------------

    apis = {
        'drive' : { 'scope'       : Google.scopes['drive'],
                    'api_name'    : 'drive',
                    'api_version' : 'v3', },
    }
    services = GoogleAuth.service_oauth_login(apis,
                                              app_json=args.app_id,
                                              user_json=args.user_credentials,
                                              log=log)
    google = services['drive']

    #---------------------------------------------------------------

    epoch = datetime(year=1971, month=1, day=1)
    end   = datetime.now()
    # No one wants to see the microseconds
    end   = end   - timedelta(microseconds=end.microsecond)

    # Load all the results
    log.info("Downloading Jotform raw data...")
    jotform_pledge_all = read_jotform(google, epoch, end,
                jotform_family_gfile_id)

    #---------------------------------------------------------------

    # Do the individual reports

    pledge_fullfillment_report(google, pds_families, jotform_pledge_all, log)

main()
