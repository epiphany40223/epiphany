#!/usr/bin/env python

"""


NOTE: A lot of this functionality has been subsumed into Google.py and
friends.  You should be using those modules rather than blindly
copying from this file!!



Script to upload specific MP3 files to Google Drive.

This script developed and tested with Python 3.6.x.  It has not been
tested with other versions (e.g., Python 2.7.x).

- This script takes a single pass through the incoming FTP dir, the
  outgoing Google Shared Drive dir, and the outgoing FTP dir.  It is
  intended to be launched periodically via some external mechanism
  (e.g., every 5 minutes via cron or the Windows scheduler).
- Watch a directory for new MP3 files named of the form
  Txxx-YYYYMMDD-HHMMSS.mp3.
  --> As of Nov 2018, the recorder spontaneously decided to rename the
      files from Txxx to Rxxx.  So I've upaded the regular expression
      below to just ignore the first character of the filename.
- If the file size of the file hasn't changed for 60 seconds, assume
  that the file has finished uploading to this directory, and upload
  it to both a Google Shared Drive folder.
- In Google, put the uploaded MP3 file in a YYYY/MM-MONTHNAME folder,
  just to break it up.  Create those folders in the Google Shared Drive
  if they don't exist.
- Connection+authentication to Google is only done if necessary (i.e.,
  if there are files to upload to either one of them).
- Send email summaries of the results:
  - Google email will contain links to the Shared Drive, destination
    folder, and each uploaded MP3.
  - Both emails will contain success/failure indications.
- If an upload fails, it is abandoned and will be re-tried at the next
  invocation.
- A lockfile is used to ensure that only one copy of this script runs
  at a time.  If the script cannot obtain the lockfile, it simply
  exits immediately (this is not an error, it just does nothing and
  exits).

-----

This script requires a "client_id.json" file with the app credentials
from the Google App dashboard.  This file is not committed here in git
for obvious reasons (!).

This script will create a "user-credentials.json" file in the same
directory with the result of getting user consent for the Google
Account being used to authenticate.

Note that this script works on Windows, Linux, and OS X.  But first,
you need to install some Python classes:

    pip install --upgrade google-api-python-client
    pip install --upgrade recordclass

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
import logging.handlers
import traceback
import shutil
from email.message import EmailMessage
from recordclass import recordclass

from pprint import pprint

from apiclient.discovery import build
from apiclient.http import MediaFileUpload
from oauth2client import tools
from oauth2client.file import Storage
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import OAuth2WebServerFlow

# Globals
guser_cred_file = 'user-credentials.json'
guser_agent = 'py_mp3_uploader'
gauth_grace_period = 60
gauth_max_attempts = 3
# Scopes documented here:
# https://developers.google.com/drive/v3/web/about-auth
gscope = 'https://www.googleapis.com/auth/drive'

folder_mime_type = 'application/vnd.google-apps.folder'
mp3_mime_type = 'audio/mpeg'

args = None
log = None

to_gtd_dir = None
archive_dir = None

# Default for CLI arguments
smtp = ["smtp-relay.gmail.com",
        "jsquyres@epiphanycatholicchurch.org",
        "no-reply@epiphanycatholicchurch.org"]
incoming_ftp_dir = 'C:\\ftp\\ecc-recordings'
data_dir = 'data'
app_id='client_id.json'
target_team_drive = 'ECC Recordings'
verbose = True
debug = False
logfile = "log.txt"
file_stable_secs = 60

ScannedFile = recordclass('ScannedFile',
                         ['filename',
                          'year',
                          'month',
                          'size',
                          'mtime',
                          'uploaded'])

GTDFile = recordclass('GTDFile',
                      ['scannedfile',
                       'folder_webviewlink',
                       'file_webviewlink'])

#-------------------------------------------------------------------

def send_mail(subject, message_body, html=False):
    if not args.smtp:
        log.debug('Not sending email "{0}" because SMTP not setup'.format(subject))
        return

    smtp_server = args.smtp[0]
    smtp_to = args.smtp[1]
    smtp_from = args.smtp[2]

    log.info('Sending email to {0}, subject "{1}"'
                 .format(smtp_to, subject))
    with smtplib.SMTP_SSL(host=smtp_server) as smtp:
        if args.debug:
            smtp.set_debuglevel(2)

        msg = EmailMessage()
        msg.set_content(message_body)
        msg['Subject'] = subject
        msg['From'] = smtp_from
        msg['To'] = smtp_to
        if html:
            msg.replace_header('Content-Type', 'text/html')
        else:
            msg.replace_header('Content-Type', 'text/plain')

        smtp.send_message(msg)

#-------------------------------------------------------------------

def diediedie(msg):
    log.error(msg)
    log.error("Aborting")

    send_mail('Fatal error from MP3 uploader', msg)

    exit(1)

#-------------------------------------------------------------------

def find_mp3_files(dir):
    scan = os.scandir(dir)
    scanned_files = []
    for entry in scan:
        # Only accept files
        if not entry.is_file():
            continue

        # Only a specific name format
        m = re.match(pattern='^.\d+-(\d\d\d\d)(\d\d)\d\d-\d\d\d\d\d\d.mp3$',
                     flags=re.IGNORECASE,
                     string=entry.name)
        if m is None:
            continue

        # Parse the filename
        year = m.group(1)
        month_num = m.group(2)
        month = "{0}-{1}".format(month_num,
                                 calendar.month_name[int(month_num)])

        s = entry.stat()

        # Save the found file in a list
        sfile = ScannedFile(filename=entry.name,
                            year=year,
                            month=month,
                            size=s.st_size,
                            mtime=s.st_mtime,
                            uploaded=False)
        scanned_files.append(sfile)

    return scanned_files

####################################################################
#
# Google Shared Drive functions
#
####################################################################

def gtd_load_app_credentials():
    # Read in the JSON file to get the client ID and client secret
    cwd  = os.getcwd()
    file = os.path.join(cwd, args.app_id)
    if not os.path.isfile(file):
        diediedie("Error: JSON file {0} does not exist".format(file))
    if not os.access(file, os.R_OK):
        diediedie("Error: JSON file {0} is not readable".format(file))

    with open(file) as data_file:
        app_cred = json.load(data_file)

    log.debug('Loaded application credentials from {0}'
                  .format(file))
    return app_cred

#-------------------------------------------------------------------

def gtd_load_user_credentials(scope, app_cred):
    # Get user consent
    client_id       = app_cred['installed']['client_id']
    client_secret   = app_cred['installed']['client_secret']
    flow            = OAuth2WebServerFlow(client_id, client_secret, scope)
    flow.user_agent = guser_agent

    cwd       = os.getcwd()
    file      = os.path.join(cwd, guser_cred_file)
    storage   = Storage(file)
    user_cred = storage.get()

    # If no credentials are able to be loaded, fire up a web
    # browser to get a user login, etc.  Then save those
    # credentials in the file listed above so that next time we
    # run, those credentials are available.
    if user_cred is None or user_cred.invalid:
        user_cred = tools.run_flow(flow, storage,
                                        tools.argparser.parse_args())

    log.debug('Loaded user credentials from {0}'
                  .format(file))
    return user_cred

#-------------------------------------------------------------------

def gtd_authorize(user_cred):
    http    = httplib2.Http()
    http    = user_cred.authorize(http)
    service = build('drive', 'v3', http=http)

    log.debug('Authorized to Google')
    return service

#-------------------------------------------------------------------

def gtd_login():
    # Put a loop around this so that it can re-authenticate via the
    # OAuth refresh token when possible.  Real errors will cause the
    # script to abort, which will notify a human to fix whatever the
    # problem was.
    auth_count = 0
    while auth_count < gauth_max_attempts:
        try:
            # Authorize the app and provide user consent to Google
            log.debug("Authenticating to Google...")
            app_cred = gtd_load_app_credentials()
            user_cred = gtd_load_user_credentials(gscope, app_cred)
            service = gtd_authorize(user_cred)
            log.info("Authenticated to Google")
            break

        except AccessTokenRefreshError:
            # The AccessTokenRefreshError exception is raised if the
            # credentials have been revoked by the user or they have
            # expired.
            log.error("Failed to authenticate to Google (will sleep and try again)")

            # Delay a little and try to authenticate again
            time.sleep(10)

        auth_count = auth_count + 1

    if auth_count > gauth_max_attempts:
        diediedie("Failed to authenticate to Google {0} times.\nA human needs to figure this out."
                  .format(gauth_max_attempts))

    return service

#===================================================================

def gtd_find_team_drive(service, target_name):
    # Iterate over all (pages of) Shared Drives, looking for one in
    # particular
    page_token = None
    while True:
        response = (service.teamdrives()
                    .list(pageToken=page_token).execute())
        for team_drive in response.get('teamDrives', []):
            if team_drive['name'] == target_name:
                log.debug('Found target Shared Drive: "{0}" (ID: {1})'
                          .format(target_name, team_drive['id']))
                return team_drive

        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break

    # If we get here, we didn't find the target team drive
    diediedie("Error: Could not find the target Shared Drive ({0})"
              .format(args.target_team_drive))

#===================================================================

def gtd_upload_file(service, team_drive, dest_folder, upload_filename):
    log.debug('Uploading GTD file "{0}" (parent: {1})'
              .format(upload_filename, dest_folder['id']))
    metadata = {
        'name' : os.path.basename(upload_filename),
        'mimeType' : mp3_mime_type,
        'parents' : [ dest_folder['id'] ]
    }
    media = MediaFileUpload(upload_filename,
                            mimetype=mp3_mime_type,
                            resumable=True)
    file = service.files().create(body=metadata,
                                  media_body=media,
                                  supportsTeamDrives=True,
                                  fields='name,id,webContentLink,webViewLink').execute()
    log.debug('Successfully uploaded GTD file: "{0}" (ID: {1})'
              .format(os.path.basename(upload_filename),
                      file['id']))
    return file

#-------------------------------------------------------------------

def gtd_create_folder(service, team_drive, folder_name, parent_id):
    log.debug("Creating GTD folder {0}, parent {1}".format(folder_name, parent_id))
    metadata = {
        'name' : folder_name,
        'mimeType' : folder_mime_type,
        'parents' : [ parent_id ]
        }
    folder = service.files().create(body=metadata,
                                    supportsTeamDrives=True,
                                    fields='name,id,webContentLink,webViewLink').execute()
    log.debug('Created GTD folder: "{0}" (ID: {1})'
              .format(folder_name, folder.get('id')))

    return folder

#-------------------------------------------------------------------

def gtd_find_or_create_folder(service, team_drive, folder_name, parent_id):
    # Find a folder identified by this name/parent.  If it doesn't
    # exist, create it.
    # Don't worry about pagination, because we expect to only get
    # 0 or 1 results back.
    log.debug("Finding / making GTD folder: {0}/{1}..."
              .format(team_drive['name'],
                      folder_name))

    query = ("name='{0}' and mimeType='{1}' and trashed=false"
             .format(folder_name, folder_mime_type))
    if parent_id is not None:
        query = query + (" and '{0}' in parents"
                         .format(parent_id))
    log.debug("GTD folder query: {0}".format(query))
    response = (service.files()
                .list(q=query,
                      spaces='drive',
                      corpora='teamDrive',
                      fields='files(name,id,parents,webContentLink,webViewLink)',
                      teamDriveId=team_drive['id'],
                      includeTeamDriveItems=True,
                      supportsTeamDrives=True).execute())
    folders = response.get('files', [])

    # If we got more than 1 result back, let a human figure it out
    if len(folders) > 1:
        diediedie('''Error: found more than one folder matching name="{0}"
Error: a human should fix this in the Google Drive web interface.'''
                  .format(folder_name, parent_id))

    # If we got 0 results back, then go create that folder
    elif len(folders) == 0:
        log.debug("GTD folder not found -- need to create it")
        return gtd_create_folder(service, team_drive, folder_name,
                                 parent_id)

    # Otherwise, we found it.  Yay!
    else:
        folder = folders[0]
        log.debug('Found GTD target folder: "{0}" (ID: {1})'
                      .format(folder_name, folder['id']))
        return folder

#-------------------------------------------------------------------

def gtd_create_dest_folder(service, team_drive, year, month):
    # Look for the year folder at the top of the team drive
    year_folder = gtd_find_or_create_folder(service, team_drive, year,
                                            team_drive['id'])

    # Look for the month folder in the year folder
    month_folder = gtd_find_or_create_folder(service, team_drive, month,
                                             year_folder['id'])

    return month_folder

#-------------------------------------------------------------------

def gtd_email_results(team_drive, gtded_files):
    # Send an email with all the results.
    subject = "all succeeded"
    message = '''<p>Uploaded files to the Google Shared Drive:</p>

<p>
<table border="0">
<tr>
<td colspan="2"><hr></td>
</tr>

<tr>
<td>Shared Drive:</td>
<td><a href="{0}">{1}</a></td>
</tr>

<tr>
<td colspan="2"><hr></td>
</tr>\n\n'''.format("https://drive.google.com/drive/u/0/folders/" + team_drive['id'],
                    team_drive['name'])

    count_failed = 0
    for file in gtded_files:
        if file.scannedfile.uploaded:
            status = "Success"
        else:
            status = "Failed (will try again later)"
            count_failed = count_failed + 1
            subject = 'some failed'

        msg = '''<tr>
<td>Folder:</td>
<td><a href="{0}">{1}/{2}</a></td>
</tr>

<tr>
<td>File:</td>
<td><a href="{3}">{4}</a></td>
</tr>

<tr>
<td>Upload status:</td>
<td>{5}</td>
</tr>

<tr>
<td colspan="2"><hr></td>
</tr>\n\n'''.format(file.folder_webviewlink,
                   file.scannedfile.year,
                   file.scannedfile.month,
                   file.file_webviewlink,
                   file.scannedfile.filename,
                   status)

        message = message + msg

    if count_failed == len(gtded_files):
        subject = "all failed!"

    message = message + '''</table>
</p>

<p>Your friendly Google Shared Drive daemon,<br />
Greg</p>'''

    send_mail(subject="Google Shared Drive upload results ({0})".format(subject),
              message_body=message,
              html=True)

#-------------------------------------------------------------------

def gtd_upload_files(service, team_drive, scanned_files):
    gtded_files = []
    for file in scanned_files:
        gtdfile = GTDFile(scannedfile=file,
                          folder_webviewlink=None,
                          file_webviewlink=None)

        # Try to upload the file
        src_filename = os.path.join(to_gtd_dir, file.filename)
        try:
            folder = gtd_create_dest_folder(service, team_drive,
                                            file.year, file.month)
            gtdfile.folder_webviewlink = folder['webViewLink']

            uploaded_file = gtd_upload_file(service, team_drive,
                                            folder, src_filename)
            gtdfile.file_webviewlink = uploaded_file['webViewLink']

            log.info("Uploaded {0} to GTD successfully".format(file.filename))

            # From this file from the "to GTD" dir so that we
            # don't try to upload it again the next time through
            os.unlink(src_filename)

            # Happiness!
            file.uploaded = True

        except:
            # Sadness :-(
            file.uploaded = False
            log.error(traceback.format_exc())
            log.error("Unsuccessful GTD upload of {0}!".format(file.filename))

        gtded_files.append(gtdfile)

    # Send a single email with the results of all the GTD uploads
    gtd_email_results(team_drive, gtded_files)

#-------------------------------------------------------------------

def upload_to_gtd():
    # If there's nothing to do, return (scandir does not return "." or
    # "..").  It's necessary to save the results from iterating
    # through the scandir() results because the iterator cannot be
    # reset.
    scanned_files = find_mp3_files(to_gtd_dir)
    if len(scanned_files) == 0:
        return

    # There's something to do!  So login to Google.
    service = gtd_login()

    # Find the target team drive to which we want to upload
    team_drive = gtd_find_team_drive(service, args.target_team_drive)

    # Go through all the files we found in the "to GTD" directory
    gtd_upload_files(service, team_drive, scanned_files)

####################################################################
#
# Watch for incoming FTP files functions
#
####################################################################

def check_for_incoming_ftp():
    log.debug('Checking incoming FTP directory {0}'.format(args.incoming_ftp_dir))

    scanned_files = find_mp3_files(args.incoming_ftp_dir)
    if len(scanned_files) == 0:
        return

    for file in scanned_files:
        log.debug("Checking file: {0}".format(file.filename))
        # If the file size is 0, skip it
        if file.size == 0:
            log.debug("File size is 0 -- skipping")
            continue

        # If the file is still being uploaded to us (i.e., if the last
        # file modification time is too recent), skip it.
        log.debug("File: time now: {0}".format(time.time()))
        log.debug("File: mtime:    {0}".format(file.mtime))
        if (time.time() - file.mtime) < int(args.file_stable_secs):
            continue

        # If we got here, the file is good! Copy it to the "to FTP"
        # and "to Google Shared Drive" directories so that they will be
        # processed.
        log.info("Found incoming FTP file: {0}".format(file.filename))
        filename = os.path.join(args.incoming_ftp_dir, file.filename)
        shutil.copy2(src=filename, dst=to_gtd_dir)

        # Finally, move the file to the archive directory for a
        # "permanent" record (and so that we won't see it again on
        # future passes through this directory).
        global archive_dir
        archive_filename = os.path.join(archive_dir, file.filename)
        log.info("Checking to make sure archive file does not already exist: {}".format(archive_filename))
        if os.path.exists(archive_filename):
            log.info("Removing already-existing archive file: {}".format(archive_filename))
            os.remove(archive_filename)
        shutil.move(src=filename, dst=archive_dir)
        log.info("Moved file to archive: {}".format(file.filename))

####################################################################
#
# Setup functions
#
####################################################################

def setup_logging(args):
    level=logging.ERROR

    if args.debug:
        level="DEBUG"
    elif args.verbose:
        level="INFO"

    global log
    log = logging.getLogger('mp3')
    log.setLevel(level)

    # Make sure to include the timestamp in each message
    f = logging.Formatter('%(asctime)s %(levelname)-8s: %(message)s')

    # Default log output to stdout
    s = logging.StreamHandler()
    s.setFormatter(f)
    log.addHandler(s)

    # Optionally save to a rotating logfile
    if args.logfile:
        s = logging.handlers.RotatingFileHandler(filename=args.logfile,
                                                 maxBytes=(pow(2,20) * 10),
                                                 backupCount=10)
        s.setFormatter(f)
        log.addHandler(s)

#-------------------------------------------------------------------

def add_cli_args():
    # Be sure to check the Google SMTP relay documentation for
    # non-authenticated relaying instructions:
    # https://support.google.com/a/answer/2956491
    tools.argparser.add_argument('--smtp',
                                 nargs=3,
                                 required=False,
                                 help='SMTP server hostname, to, and from addresses')

    tools.argparser.add_argument('--data-dir',
                                 required=False,
                                 default=data_dir,
                                 help='Directory to store internal data')
    tools.argparser.add_argument('--file-stable-secs',
                                 required=False,
                                 default=file_stable_secs,
                                 help='Number of seconds for an incoming FTP file to not change before considered "complete"')

    tools.argparser.add_argument('--incoming-ftp-dir',
                                 required=False,
                                 default=incoming_ftp_dir,
                                 help='Directory to watch for incoming MP3s')

    tools.argparser.add_argument('--app-id',
                                 required=False,
                                 default=app_id,
                                 help='Filename containing Google application credentials')
    tools.argparser.add_argument('--target-team-drive',
                                 required=False,
                                 default=target_team_drive,
                                 help='Name of Shared Drive to upload the found MP3 files to')

    tools.argparser.add_argument('--verbose',
                                 required=False,
                                 action='store_true',
                                 default=verbose,
                                 help='If enabled, emit extra status messages during run')
    tools.argparser.add_argument('--debug',
                                 required=False,
                                 action='store_true',
                                 default=debug,
                                 help='If enabled, emit even more extra status messages during run')
    tools.argparser.add_argument('--logfile',
                                 required=False,
                                 default=logfile,
                                 help='Store verbose/debug logging to the specified file')

    global args
    args = tools.argparser.parse_args()

    # --debug also implies --verbose
    if args.debug:
        args.verbose = True
    setup_logging(args)

    # Sanity check args
    l = 0
    if args.smtp:
        l = len(args.smtp)
    if l > 0 and l != 3:
        log.error("Need exactly 3 arguments to --smtp: server to from")
        exit(1)

    if not os.path.isdir(args.data_dir):
        log.error('Data directory "{0}" does not exist or is not accessible'
                  .format(args.data_dir))
        exit(1)

    if not os.path.isdir(args.incoming_ftp_dir):
        log.error('Incoming FTP directory "{0}" does not exist or is not accessible'
                  .format(args.incoming_ftp_dir))
        exit(1)

#-------------------------------------------------------------------

def setup():
    # Make the subdirs in the data dir
    global to_gtd_dir
    to_gtd_dir = os.path.join(args.data_dir, "to-gtd")
    safe_mkdir(to_gtd_dir)

    global archive_dir
    archive_dir = os.path.join(args.data_dir, "archive")
    safe_mkdir(archive_dir)

#-------------------------------------------------------------------

def safe_mkdir(dir):
    if not os.path.isdir(dir):
        log.debug("Making dir: {0}".format(dir))
        if os.path.exists(dir):
            os.unlink(dir)
        os.makedirs(dir, exist_ok=True)

#-------------------------------------------------------------------

# A lockfile class so that we can use this lockfile in a context
# manager (so that we can guarantee that the lockfile is removed
# whenever the process exits, for any reason).
class LockFile:
    def __init__(self, lockfile):
        self.lockfile = lockfile
        self.opened = False

    def __enter__(self):
        try:
            fp = open(self.lockfile, mode='x')
            fp.write(time.ctime())
            fp.close()
            log.debug("Locked!")
            self.opened = True
        except:
            # We weren't able to create the file, so that means
            # someone else has it locked.  This is not an error -- we
            # just exit.
            log.debug("Unable to obtain lockfile -- exiting")
            exit(0)

    def __exit__(self, exception_type, exception_value, exeception_traceback):
        if self.opened:
            os.unlink(self.lockfile)
            log.debug("Unlocked")

####################################################################
#
# Main
#
####################################################################

def main():
    add_cli_args()

    filename = os.path.join(args.data_dir, "lockfile")
    with LockFile(filename) as lockfile:
        setup()
        check_for_incoming_ftp()
        upload_to_gtd()

    exit(0)

if __name__ == '__main__':
    main()
