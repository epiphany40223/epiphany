#!/usr/bin/env python3

# Basic script to create a list of all PDS trainings of a given type.

import sys
import os

import logging.handlers
import logging

# We assume that there is a "ecc-python-modules" sym link in this
# directory that points to the directory with ECC.py and friends.
moddir = os.path.join(os.getcwd(), 'ecc-python-modules')
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)

sys.path.insert(0, moddir)

import ECC
import Google
import PDSChurch
import GoogleAuth
from google.api_core import retry

from datetime import date
from datetime import datetime
from datetime import timedelta

from oauth2client import tools
from apiclient.http import MediaFileUpload

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

from training_sheets import EverythingSheet, SchedulableSheet, NonSchedulableSheet

# Globals

gapp_id         = 'client_id.json'
guser_cred_file = 'user-credentials.json'

now = datetime.now()
timestamp = f'{now.year:04}-{now.month:02}-{now.day:02} {now.hour:02}:{now.minute:02}'

trainings   = [
    {
        "title"     : 'Communion Ministers',
        "gsheet_id" : '1T4g6povnXPYOY8G4Oou7jq_Ere4jm4-z0Y37IKT-s20',
        'pds_type'  : 'Communion Minister training',
    },
]

#---------------------------------------------------------------------------

def check_ministries(member):
    if not member['Inactive']:
        member['involved'] = True

    key = 'active_ministries'
    if key in member:
        for ministry in member[key]:
            if ministry['Description'] == '313A-Communion: Weekend':
                member['weekend'] = 'Yes'
            else:
                member['weekend'] = 'No'

            if ministry['Description'] == '313B-Communion: Weekday':
                member['weekday'] = 'Yes'
            else:
                member['weekday'] = 'No'

            if ministry['Description'] == '313C-Communion: Homebound':
                member['homebound'] = 'Yes'
            else:
                member['homebound'] = 'No'

    return member

#---------------------------------------------------------------------------

def pds_find_training(pds_members, training_to_find, log):
    out = dict()
    reqcount = 0

    for member in pds_members.values():
        key = 'requirements'
        if key not in member:
            continue

        for req in member[key]:
            if req['description'] != training_to_find['pds_type']:
                continue
            reqcount += 1

            mid = member['MemRecNum']
            start_date = req['start_date']
            if start_date == PDSChurch.date_never:
                start_date = ''
            if mid not in out:
                out[mid] = dict()
            if start_date not in out[mid]:
                out[mid][start_date] = list()

            end_date = req['end_date']
            if end_date == PDSChurch.date_never:
                end_date = ''

            member = check_ministries(member)
            out[mid][start_date].append({
                'mid'           :   mid,
                'name'          :   f"{member['first']} {member['last']}",
                'email'         :   PDSChurch.find_any_email(member)[0],
                'phone'         :   PDSChurch.find_member_phone(member, 'Cell'),
                'start_date'    :   start_date,
                'end_date'      :   end_date,
                'stage'         :   req['result'],
                'involved'      :   member['involved'],
                'weekend'       :   member['weekend'],
                'weekday'       :   member['weekday'],
                'homebound'     :   member['homebound'],
            })

    if reqcount == 0:
        log.info(f"No trainings of type: {training_to_find['title']} found")
        return None
    else:
        log.info(f"Found {reqcount} training records")
        return out

def write_xlsx(title, trainingdata, log):
    filename = title

    wb = Workbook()

    every = EverythingSheet(wb, trainingdata)
    every.create_roster(title)

    schedulable = SchedulableSheet(wb, trainingdata)
    schedulable.create_roster(title)

    nonschedulable = NonSchedulableSheet(wb, trainingdata)
    nonschedulable.create_roster(title)

    wb.save(filename)
    log.debug(f'Wrote {filename}')

    return filename

#---------------------------------------------------------------------------

def create_roster(trainingdata, training, google, log, dry_run):
    # Create xlsx file
    filename = write_xlsx(training['title'], trainingdata, log)
    log.info(f"Wrote temp XLSX file: {filename}")

    # Upload xlsx to Google
    if not dry_run:
        upload_overwrite(filename=filename, google=google, file_id=training['gsheet_id'],
                        log=log)
        log.debug("Uploaded XLSX file to Google")

        # Remove temp local xlsx file
        try:
            os.unlink(filename)
            log.debug("Unlinked temp XLSX file")
        except:
            log.info(f"Failed to unlink temp XLSX file {filename}!")

#---------------------------------------------------------------------------

@retry.Retry(predicate=Google.retry_errors)
def upload_overwrite(filename, google, file_id, log):
    # Strip the trailing ".xlsx" off the Google Sheet name
    gsheet_name = filename
    if gsheet_name.endswith('.xlsx'):
        gsheet_name = gsheet_name[:-5]

    try:
        log.info(f'Uploading file update to Google file ID {file_id}')
        metadata = {
            'name'     : gsheet_name,
            'mimeType' : Google.mime_types['sheet'],
            'supportsAllDrives' : True,
        }
        media = MediaFileUpload(filename,
                                mimetype=Google.mime_types['sheet'],
                                resumable=True)
        file = google.files().update(body=metadata,
                                     fileId=file_id,
                                     media_body=media,
                                     supportsAllDrives=True,
                                     fields='id').execute()
        log.debug(f"Successfully updated file: {filename} (ID: {file['id']})")

    except Exception as e:
        # When errors occur, we do want to log them.  But we'll re-raise them to
        # let an upper-level error handler handle them (e.g., retry.Retry() may
        # actually re-invoke this function if it was a retry-able Google API
        # error).
        log.error('Google file update failed for some reason:')
        log.error(e)
        raise e

#------------------------------------------------------------------

def setup_cli_args():
    tools.argparser.add_argument('--logfile',
                                 help='Also save to a logfile')

    tools.argparser.add_argument('--debug',
                                 action='store_true',
                                 default=False,
                                 help='Be extra verbose')

    tools.argparser.add_argument('--dry-run',
                                 action='store_true',
                                 default=False,
                                 help='Do not upload to Google')

    tools.argparser.add_argument('--sqlite3-db',
                                 required=True,
                                 help='Location of PDS sqlite3 database')

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

#-------------------------------------------------------------------

def main():
    args = setup_cli_args()
    log = ECC.setup_logging(info=True,
                            debug=args.debug,
                            logfile=args.logfile)

    log.info("Reading PDS data...")
    (pds, pds_families,
     pds_members) = PDSChurch.load_families_and_members(filename=args.sqlite3_db,
                                                        parishioners_only=False,
                                                        log=log)

    apis = {
        'drive' : { 'scope'       : Google.scopes['drive'],
                    'api_name'    : 'drive',
                    'api_version' : 'v3', },
    }
    google = None
    if not args.dry_run:
        services = GoogleAuth.service_oauth_login(apis,
                                                app_json=args.app_id,
                                                user_json=args.user_credentials,
                                                log=log)
        google = services['drive']

    for training in trainings:
        training_data = pds_find_training(pds_members, training, log)
        create_roster(training_data, training, google, log, args.dry_run)

    # All done
    pds.connection.close()

main()
