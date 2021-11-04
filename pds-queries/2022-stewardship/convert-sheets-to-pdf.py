#!/usr/bin/env python3

# Make sure to pip install everything in requirements.txt.
#
# This script is a hack.  A beautiful hack.  :-)
#
# The problem that this script solves is getting PDFs for a whole bunch of
# Google Sheets in a folder (about 70 of them).  All we do is use the Google
# Drive API to get the ID's for all the sheets in the target folder and then use
# the macOS "open" command to open a specific form of URL -- with that google
# sheet file ID -- that will export/download the PDF in landscape format.  This
# results in opening a browser tab for each file, but who cares?  The PDF will
# be downloaded to the browser's default location (e.g., ~/Downloads) -- that's
# the important part.

import sys
sys.path.insert(0, '../../python')

import argparse
import os

import ECC
import Google
import GoogleAuth

import subprocess

from oauth2client import tools
from apiclient.http import MediaFileUpload
from email.message import EmailMessage

##############################################################################

gapp_id         = 'client_id.json'
guser_cred_file = 'user-credentials.json'

source_google_shared_drive = '0AHQEqKijqXcFUk9PVA'
source_google_drive_folder = '1ukc65NcJDbOIGZebmhR-l-1l83uPQY4T'

# jms folder
source_google_drive_folder = '1SXxYpO6nH9B5kikGSdZ41yCL8qZLmXP2'

##############################################################################

def download_google_sheets(google, args, log):
    log.info(f"Finding Google Sheets in Team Drive {args.shared_drive_id}, folder {args.gdrive_folder_id}")

    mime = Google.mime_types['sheet']
    q = f'"{args.gdrive_folder_id}" in parents and mimeType="{mime}" and trashed=false'
    response = google.files().list(corpora='drive',
                                   driveId=args.shared_drive_id,
                                   includeTeamDriveItems=True,
                                   supportsAllDrives=True,
                                   q=q,
                                   fields='files(name,id)').execute()
    gfiles = response.get('files', [])

    # Download the file as a PDF
    log.info(f"Opening PDFs in web browser that is already authenticated to Google...")
    # The format of this URL came from
    # https://support.google.com/docs/thread/3457043?hl=en.  There are many
    # more parameters that can be passed in this URL, too -- I just
    # used the ones that were relevant for exporting the PDF in landscape
    # mode.
    base   = 'https://docs.google.com/a/mydomain.org/spreadsheets/d/'
    suffix = '/export?exportFormat=pdf&format=pdf&portrait=false'
    for gfile in gfiles:
        log.info(f"Opening Sheet {gfile['name']}...")
        subprocess.run(args=["open", f"{base}{gfile['id']}{suffix}"])

##############################################################################

def setup_args():
    tools.argparser.add_argument('--shared-drive-id',
                                 default=source_google_shared_drive,
                                 help='Google Shared Drive ID')

    tools.argparser.add_argument('--gdrive-folder-id',
                                 default=source_google_drive_folder,
                                 help='Google Drive folder from which to download/load the Sheets (must be in the indicated shared drive)')

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
    args = setup_args()
    log = ECC.setup_logging(debug=False)

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

    download_google_sheets(google, args, log)

main()
