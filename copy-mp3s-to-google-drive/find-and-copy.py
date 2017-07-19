#!/usr/bin/env python

"""Script to upload specific MP3 files to Google Drive.

This script developed and tested with Python 3.6.x.  It has not been
tested with other versions (e.g., Python 2.7.x).

- Watch a directory for new MP3 files named of the form
  Txxx-YYYYMMDD-HHMMSS.mp3.
- If the file size of the file doesn't change for 30 seconds, assume
  that the file has finished uploading to this directory, and upload
  it to a Google Team Drive folder.
- Put the uploaded MP3 file in a YYYY/MM-MONTHNAME folder, just to
  break it up.  Create those folders in the Google Team Drive if they
  don't exist.
- If the upload fails, it should just try again later.
- If the upload succeeds, the MP3 file will be moved to the "Uploaded"
  sub-folder.  Someday, we can likely remove the file altogether, but
  until we run this script in real-world conditions for a while, we
  don't know what the failure conditions will be.  So save the MP3s on
  the local disk for now.

Various names and constants are hard-coded into this script, which may
well be sufficient.

Things that still need to be done:

- This script errors out in a few places.  Since this script is
  intended to be run non-interactively, it should probably send an
  alert of some kind (email?) to humans when that happens.  I.e., fill
  in the notification part in diediedie().

-----

This script requires a "client_id.json" file with the app credentials
from the Google App dashboard.  This file is not committed here in git
for obvious reasons (!).

This script will create a "user-credentials.json" file in the same
directory with the result of getting user consent for the Google
Account being used to authenticate.

Note that this script works on Windows, Linux, and OS X.  But first,
you need to install the Google API python client:

    pip install --upgrade google-api-python-client

Regarding Google Drive / Google Python API documentation:

1. In terms of authentication, this is very helpful to read:

    https://developers.google.com/identity/protocols/OAuth2

This script is using the "Installed Applications" scheme.

2. In terms of the Google Python docs, this is very helpful to read:

    https://developers.google.com/api-client-library/python/start/get_started

We are using Authorized API access (OAuth 2.0).

Steps:

2a. Request a(n application) token
2b. Provider user consent
2c. Get an authorization code from Google
2d. Send the code to Google
2e. Receive access token and refresh token
2f. Can make API calls with the access token
2g. If the access token is expired, use the refresh token.  If the
    refresh token doesn't work, go back to step 2 (or step 1?).

"""

import json
import sys
import os
import re
import time
import httplib2
import calendar
import smtplib
import logging
import traceback
from email.message import EmailMessage

from pprint import pprint

from apiclient.discovery import build
from apiclient.http import MediaFileUpload
from oauth2client import tools
from oauth2client.file import Storage
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import OAuth2WebServerFlow

# Globals
user_cred_file = 'user-credentials.json'
user_agent = 'py_mp3_uploader'
folder_mime_type = 'application/vnd.google-apps.folder'
mp3_mime_type = 'audio/mpeg'
dir_check_frequency = 60
auth_grace_period = 60
auth_max_attempts = 3
args = None
# Scopes documented here:
# https://developers.google.com/drive/v3/web/about-auth
scope = 'https://www.googleapis.com/auth/drive'

#-------------------------------------------------------------------

def send_mail(subject, message_body, html=False):
    if args.smtp_to == '' or args.smtp_from == '' or args.smtp_host == '':
        logging.debug('Not sending email "{0}" because SMTP to, from, and/or host node defined'.format(subject))
        return

    logging.info('Sending email to {0}, subject "{1}"'
                 .format(args.smtp_to, subject))
    with smtplib.SMTP_SSL(host=args.smtp_host) as smtp:
        logging.info("Got smtp ssl connection")
        if args.debug:
            smtp.set_debuglevel(2)

        msg = EmailMessage()
        msg.set_content(message_body)
        msg['Subject'] = subject
        msg['From'] = args.smtp_from
        msg['To'] = args.smtp_to
        if html:
            msg.replace_header('Content-Type', 'text/html')
        else:
            msg.replace_header('Content-Type', 'text/plain')

        logging.info("Sending message")
        smtp.send_message(msg)
        logging.info("Done Sending message")

    logging.debug('sent email to {0}, subject "{1}"'
                 .format(args.smtp_to, subject))

#-------------------------------------------------------------------

def diediedie(msg):
    logging.error(msg)
    logging.error("Aborting")

    send_mail('Fatal error from MP3 uploader', msg)

    exit(1)

#-------------------------------------------------------------------

def setup_logging(args):
    level=logging.ERROR

    if args.debug:
        level=logging.DEBUG
    elif args.verbose:
        level=logging.INFO

    logging.basicConfig(level=level)

#-------------------------------------------------------------------

def load_app_credentials():
    # Read in the JSON file to get the client ID and client secret
    cwd  = os.getcwd()
    file = os.path.join(cwd, args.app_id)
    if not os.path.isfile(file):
        diediedie("Error: JSON file {0} does not exist".format(file))
    if not os.access(file, os.R_OK):
        diediedie("Error: JSON file {0} is not readable".format(file))

    with open(file) as data_file:
        app_cred = json.load(data_file)

    logging.debug('=== Loaded application credentials from {0}'
                  .format(file))
    return app_cred

#-------------------------------------------------------------------

def load_user_credentials(scope, app_cred):
    # Get user consent
    client_id       = app_cred['installed']['client_id']
    client_secret   = app_cred['installed']['client_secret']
    flow            = OAuth2WebServerFlow(client_id, client_secret, scope)
    flow.user_agent = user_agent

    cwd       = os.getcwd()
    file      = os.path.join(cwd, user_cred_file)
    storage   = Storage(file)
    user_cred = storage.get()

    # If no credentials are able to be loaded, fire up a web
    # browser to get a user login, etc.  Then save those
    # credentials in the file listed above so that next time we
    # run, those credentials are available.
    if user_cred is None or user_cred.invalid:
        user_cred = tools.run_flow(flow, storage,
                                        tools.argparser.parse_args())

    logging.debug('=== Loaded user credentials from {0}'
                  .format(file))
    return user_cred

#-------------------------------------------------------------------

def authorize(user_cred):
    http    = httplib2.Http()
    http    = user_cred.authorize(http)
    service = build('drive', 'v3', http=http)

    logging.debug('=== Authorized to Google')
    return service

####################################################################

def upload_file(service, team_drive, dest_folder, upload_filename):
    try:
        logging.info('=== Uploading file "{0}" (parent: {1})'
                     .format(upload_filename, dest_folder['id']))
        metadata = {
            'name' : upload_filename,
            'mimeType' : mp3_mime_type,
            'parents' : [ dest_folder['id'] ]
            }
        media = MediaFileUpload(upload_filename,
                                mimetype=mp3_mime_type,
                                resumable=True)
        file = service.files().create(body=metadata,
                                      media_body=media,
                                      supportsTeamDrives=True,
                                      fields='id').execute()
        logging.info('=== Successfully uploaded file: "{0}" (ID: {1})'
                     .format(upload_filename, file.get('id')))
        return True

    except:
        traceback.print_exc(file=sys.stdout)
        logging.info('=== Google upload failed for some reason -- will try again later')

        return False

#-------------------------------------------------------------------

def create_folder(service, team_drive, folder_name, parent_id):
    logging.debug("=== Creating folder {0}, parent {1}".format(folder_name, parent_id))
    metadata = {
        'name' : folder_name,
        'mimeType' : folder_mime_type,
        'parents' : [ parent_id ]
        }
    folder = service.files().create(body=metadata,
                                    supportsTeamDrives=True,
                                    fields='name,id').execute()
    logging.debug('=== Created folder: "{0}" (ID: {1})'
                  .format(folder_name, folder.get('id')))
    return folder

#-------------------------------------------------------------------

def find_or_create_folder(service, team_drive, folder_name, parent_id):
    # Find a folder identified by this name/parent.  If it doesn't
    # exist, create it.
    # Don't worry about pagination, because we expect to only get
    # 0 or 1 results back.
    query = ("name='{0}' and mimeType='{1}' and trashed=false"
             .format(folder_name, folder_mime_type))
    if parent_id is not None:
        query = query + (" and '{0}' in parents"
                         .format(parent_id))
    logging.debug("=== Folder query: {0}".format(query))
    response = (service.files()
                .list(q=query,
                      spaces='drive',
                      corpora='teamDrive',
                      fields='files(name,id,parents)',
                      teamDriveId=team_drive['id'],
                      includeTeamDriveItems=True,
                      supportsTeamDrives=True).execute())
    folders = response.get('files', [])

    # If we got more than 1 result back, let a human figure it out
    if len(folders) > 1:
        diediedie("""Error: found more than one folder matching name="{0}"
Error: a human should fix this in the Google Drive web interface."""
                  .format(folder_name, parent_id))

    # If we got 0 results back, then go create that folder
    elif len(folders) == 0:
        logging.debug("=== Folder not found -- need to create it")
        return create_folder(service, team_drive, folder_name,
                             parent_id)

    # Otherwise, we found it.  Yay!
    else:
        folder = folders[0]
        logging.debug('=== Found target folder: "{0}" (ID: {1})'
                      .format(folder_name, folder['id']))
        return folder

#-------------------------------------------------------------------

def create_dest_folder(service, team_drive, year, month):
    # Look for the year folder at the top of the team drive
    year_folder = find_or_create_folder(service, team_drive, year,
                                        team_drive['id'])

    # Look for the month folder in the year folder
    month_folder = find_or_create_folder(service, team_drive, month,
                                         year_folder['id'])

    return month_folder

#-------------------------------------------------------------------

def upload_mp3(service, team_drive, year, month, file):
    folder = create_dest_folder(service, team_drive, year, month)
    success = upload_file(service, team_drive, folder, file)

    # If we succeeded, remove the file from the local filesystem
    if success:
        if args.verbose:
            send_mail(html=True,
                      subject='Successful MP3 upload',
                      message_body='''<p>Successfully uploaded file to Google drive:<p>

<p>
<table border="0">
<tr>
<td>Team Drive:</td>
<td>{0} (ID: {1})</td>
</tr>

<tr>
<td>File:</td>
<td>{2}/{3}/{4}</td>
</tr>
</table>

<p>- Marvin the MP3 Daemon</p>'''
                      .format(team_drive['name'],
                              team_drive['id'],
                              year,
                              month,
                              file))

        logging.debug('=== Moved {0} to "Uploaded" folder'.format(file))
        try:
            os.mkdir("Uploaded")
        except:
            pass
        os.rename(file, os.path.join("Uploaded", file))

    # If we failed, update a count and notify a human

#-------------------------------------------------------------------

def watch_for_new_mp3s(service, team_drive, source_dir):
    seen_files = {}
    while True:
        logging.debug('=== Checking {0} at {1}'.format(source_dir,
                                                       time.asctime(time.localtime())))
        files = os.listdir(source_dir)
        for file in files:
            m = re.match(pattern='^T\d+-(\d\d\d\d)(\d\d)\d\d-\d\d\d\d\d\d.mp3$',
                         flags=re.IGNORECASE,
                         string=file)
            if m is None:
                continue

            year = m.group(1)
            month_num = m.group(2)
            month = "{0}-{1}".format(month_num,
                                     calendar.month_name[int(month_num)])

            # If the filename matches the pattern, first check to see
            # if the file is still being uploaded to us.  Check by
            # file size.
            s = os.stat(file)

            # If the filename matches the pattern,
            # check to see if it's file size is still changing.
            if file not in seen_files:
                logging.debug("=== Found MP3 {0} with file size {1}"
                              .format(file, s.st_size))
                seen_files[file] = s.st_size
                continue

            else:
                # If the file size is the same, then it's probably no
                # longer changing, and it's safe to upload.
                if seen_files[file] != s.st_size:
                    logging.debug("=== Found MP3 {0}; file size changed to {1}"
                                  .format(file, s.st_size))
                    seen_files[file] = s.st_size
                    continue

                else:
                    logging.debug("=== Found MP3 {0}; file size did not change"
                                  .format(file))
                    upload_mp3(service, team_drive, year, month, file)
                    del seen_files[file]

        # Once we're done traversing the files in the directory, clean
        # up any files in seen_files that no longer exist (must do
        # this in 2 loops: it's not safe to remove a key from a
        # dictionary that you're iterating over).
        to_remove = []
        for file in seen_files:
            if not os.path.isfile(file):
                to_remove.append(file)
        for file in to_remove:
            del seen_files[file]

        # Wait a little bit, and then check again
        time.sleep(dir_check_frequency)

#-------------------------------------------------------------------

def find_team_drive(service, target_name):
    page_token = None
    while True:
        response = (service.teamdrives()
                    .list(pageToken=page_token).execute())
        for team_drive in response.get('teamDrives', []):
            if team_drive['name'] == target_name:
                logging.debug('=== Found target Team Drive: "{0}" (ID: {1})'
                              .format(target_name, team_drive['id']))
                return team_drive

        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break

    # If we get here, we didn't find the target team drive
    diediedie("Error: Could not find the target Team Drive ({0})"
              .format(args.target_team_drive))

#-------------------------------------------------------------------

def add_cli_args():
    tools.argparser.add_argument('--smtp-to',
                                 required=False,
                                 help='Who to send status mails')
    tools.argparser.add_argument('--smtp-from',
                                 required=False,
                                 default='no-reply@epiphanycatholicchurch.org',
                                 help='Who to send status from')
    tools.argparser.add_argument('--smtp-host',
                                 required=False,
                                 default='smtp-relay.gmail.com',
                                 help='SMTP server hostname')

    tools.argparser.add_argument('--source-dir',
                                 required=False,
                                 default='C:\ftp\ecc-recordings',
                                 help='Directory to watch for incoming MP3s')

    tools.argparser.add_argument('--app-id',
                                 required=False,
                                 default='client_id.json',
                                 help='Filename containing Google application credentials')
    tools.argparser.add_argument('--target-team-drive',
                                 required=False,
                                 default='ECC Recordings',
                                 help='Name of Team Drive to upload the found MP3 files to')

    tools.argparser.add_argument('--verbose',
                                 required=False,
                                 action='store_true',
                                 help='If enabled, emit extra status messages during run')
    tools.argparser.add_argument('--debug',
                                 required=False,
                                 action='store_true',
                                 help='If enabled, emit even more extra status messages during run')

    global args
    args = tools.argparser.parse_args()

    # --debug also implies --verbose
    if args.debug:
        args.verbose = True
    setup_logging(args)

#-------------------------------------------------------------------

def main():
    add_cli_args()

    # Put a loop around the whole program so that it can
    # re-authenticate via the OAuth refresh token when possible.  Real
    # errors will cause the script to abort, which will notify a human
    # to fix whatever the problem.

    last_auth = 0
    auth_count = 0
    while True:
        try:
            # Authorize the app and provide user consent to Google
            app_cred = load_app_credentials()
            user_cred = load_user_credentials(scope, app_cred)
            service = authorize(user_cred)

            last_auth = time.clock()

            # Find the target team drive to which we want to upload
            team_drive = find_team_drive(service, args.target_team_drive)

            # Endlessly watch for new files to appear in the source
            # directory, and upload them to Google
            watch_for_new_mp3s(service, team_drive, args.source_dir)

        except AccessTokenRefreshError:
            # The AccessTokenRefreshError exception is raised if the
            # credentials have been revoked by the user or they have
            # expired.
            # Try to re-auth.  If we fail to re-auth 3 times within 60
            # seconds, abort and let a human figure it out.
            now = time.clock()
            if (now - last_auth) > auth_grace_period:
                last_auth = now
                auth_count = 0
                continue

            else:
                auth_count = auth_count + 1
                if auth_count > auth_max_attempts:
                    diediedie("Failed to authenticate to Google {0} times in {1} seconds.\nA human needs to figure this out."
                              .format(auth_max_attempts, auth_grace_period))

if __name__ == '__main__':
    main()
