#!/usr/bin/env python
#
# Download Google's calendar audit data JSON and save in a Google
# Drive target folder.

import os
import sys

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
import GoogleAuth

import json
import time
import tempfile
import datetime

from oauth2client import tools
from apiclient.http import MediaFileUpload
from google.api_core import retry

from pprint import pprint
from pprint import pformat
from dateutil.parser import parse

default_app_json  = 'client_id.json'
default_user_json = 'user-credentials.json'

verbose = True
debug   = False
logfile = None

max_upload_retries = 5

default_google_team_drive_folder_id = '0ANZ3dhbzh1r-Uk9PVA'

####################################################################
#
# Setup functions
#
####################################################################

def setup_cli_args():
    global default_app_json
    tools.argparser.add_argument('--app-id',
                                 default=default_app_json,
                                 help='Filename containing Google application credentials')
    global default_user_json
    tools.argparser.add_argument('--user-credentials',
                                 default=default_user_json,
                                 help='Filename containing Google user credentials')
    tools.argparser.add_argument('--slack-token-filename',
                                 required=True,
                                 help='File containing the Slack bot authorization token')

    global default_google_team_drive_folder_id
    tools.argparser.add_argument('--target-google-folder',
                                 default=default_google_team_drive_folder_id,
                                 help='ID of target Google folder to upload results')

    global verbose
    tools.argparser.add_argument('--verbose',
                                 action='store_true',
                                 default=verbose,
                                 help='If enabled, emit extra status messages during run')
    global debug
    tools.argparser.add_argument('--debug',
                                 action='store_true',
                                 default=debug,
                                 help='If enabled, emit even more extra status messages during run')
    global logfile
    tools.argparser.add_argument('--logfile',
                                 default=logfile,
                                 help='Store verbose/debug logging to the specified file')

    global args
    args = tools.argparser.parse_args()

    # --debug implies --verbose
    if args.debug:
        args.verbose = True

    return args

####################################################################

def verify_target_google_folder(service, id, log):
    http = service.files().get(fileId=id,
                               fields='id,mimeType,name,webViewLink,parents',
                               supportsTeamDrives=True)
    folder = Google.call_api(http, log=log)

    if folder is None or folder['mimeType'] != Google.mime_types['folder']:
        log.error(f"Error: Could not find any contents of folder ID: {id}")
        exit(1)

    log.info(f"Valid folder ID: {id} ({folder['name']})")

####################################################################

def generate_calendar_audit_report(service, log):
    log.info("Querying calendar audit data...")

    # Result will likely be long / paginated.
    results    = list()
    page_token = None
    num_pages  = 0
    while True:
        http = service.activities().list(pageToken=page_token,
                                         userKey='all',
                                         applicationName='calendar')
        response = Google.call_api(http, log)

        activities = response.get('items', [])
        if len(activities) > 0:
            results.extend(activities)
            num_pages += 1

        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break

    log.info("Downloaded {a} calendar audit entries ({b} pages)"
             .format(a=len(results), b=num_pages))

    return results

####################################################################

#
# It would have been nice to write out a spreadsheet.
#
# However, according to
# https://developers.google.com/admin-sdk/reports/v1/appendix/activity/calendar,
# there are 30 different JSON event types that can come back.  I am
# not going to try to map all of those to columns in a spreadsheet --
# the chance for error is too great.  This is just a backup to
# Google's calendar audit records, anyway.  So I think just emitting a
# text file of all the JSON that we got is sufficient.  If there is a
# desire to process the json further, this file can be downloaded and
# then processed as desired.
#
def write_temp_json_file(activities, log):
    first_utc = None
    last_utc  = None

    # Find the first and last timestamps.
    # Google's timestamps are UTC.
    for activity in activities:
        d = parse(activity['id']['time'], fuzzy=True)
        if first_utc is None or d < first_utc:
            first_utc = d
        if last_utc is None or d > last_utc:
            last_utc = d

    # Convert to our local timezone
    first_local = first_utc.astimezone(ECC.local_tz)
    last_local  = last_utc.astimezone(ECC.local_tz)

    # Make the filename based on the timestamps
    def _mkdate(dt):
        return ('{year:04}{month:02}{day:02}-{hour:02}{minute:02}{second:02}'
                .format(year   = dt.year,
                        month  = dt.month,
                        day    = dt.day,
                        hour   = dt.hour,
                        minute = dt.minute,
                        second = dt.second))

    first = _mkdate(first_local)
    last  = _mkdate(last_local)

    filename = ('ECC Google calendar audit data {first} through {last}.json'
                .format(first=first, last=last))

    try:
        os.unlink(filename)
    except:
        pass

    f = open(filename, 'w')
    json.dump(activities, f)
    f.close()

    log.info("Wrote to temporary local JSON file: {f}"
              .format(f=filename))

    return filename

####################################################################

def upload_to_google(service, filename, folder_id, log):
    try:
        log.info('Uploading file to google "{file}"'
                 .format(file=filename))
        metadata = {
            'name'     : filename,
            'mimeType' : Google.mime_types['json'],
            'parents'  : [ folder_id ],
            'supportsTeamDrives' : True,
        }
        media = MediaFileUpload(filename,
                                mimetype=Google.mime_types['json'],
                                resumable=True)
        http = service.files().create(body=metadata,
                                      media_body=media,
                                      supportsTeamDrives=True,
                                      fields='id')
        response = Google.call_api(http, log)

        log.info('Successfully uploaded file: "{filename}" (ID: {id})'
                 .format(filename=filename, id=response['id']))
        return

    except Exception as e:
        log.error('Google upload failed for some reason:')
        log.error(e)
        raise e

    log.error("Google upload failed!")


####################################################################

def main():
    args = setup_cli_args()

    log = ECC.setup_logging(info=args.verbose,
                            debug=args.debug,
                            logfile=args.logfile, rotate=True,
                            slack_token_filename=args.slack_token_filename)

    # Note: these logins have been configured on the Google cloud
    # console to only allow logins with @epiphanycatholicchurch.org
    # accounts.  If the login flow runs in a browser where you are
    # logged in to a non-@epiphanycatholicchurch.org account, it will
    # display some kind of error.  No problem: just take the URL from
    # the console window and paste it into a browser that is logged in
    # to an @epiphanycatholicchurch.org account.

    apis = {
        'drive'   : { 'scope'       : Google.scopes['drive'],
                      'api_name'    : 'drive',
                      'api_version' : 'v3' },
        'reports' : { 'scope'       : Google.scopes['reports'],
                      'api_name'    : 'admin',
                      'api_version' : 'reports_v1' },
    }
    services = GoogleAuth.service_oauth_login(apis,
                                              app_json=args.app_id,
                                              user_json=args.user_credentials)
    service_drive   = services['drive']
    service_reports = services['reports']

    # Make sure that the target ID we got from the command line is actually a folder
    verify_target_google_folder(service_drive,
                                args.target_google_folder, log)

    # Generate the report / download the activities
    activities = generate_calendar_audit_report(service_reports, log)
    if len(activities) == 0:
        log.debug("Calendar audit data is empty; nothing to do!")
        return

    # Write it to a JSON file
    json_filename = write_temp_json_file(activities, log)

    # Upload that JSON file to the target ID folder
    upload_to_google(service_drive, json_filename,
                     args.target_google_folder, log)

    # Done; remove the temporary JSON file
    os.unlink(json_filename)

if __name__ == '__main__':
    main()
