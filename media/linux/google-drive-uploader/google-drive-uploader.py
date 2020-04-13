#!/usr/bin/env python3.6

"""Script to upload specific files to Google Drive.

This script developed and tested with Python 3.6.x.  It has not been
tested with other versions (e.g., Python 2.7.x).

"""

import sys
sys.path.insert(0, '../../../python')

import os
import mimetypes

import ECC
import Google
import GoogleAuth

from apiclient.http import MediaFileUpload
from oauth2client import tools

#===================================================================

def gd_find_folder(service, folder_id, log):
    # See if this folder ID exists (and is a folder)
    try:
        response = (service.files()
                    .get(fileId=folder_id,
                         supportsTeamDrives=True).execute())
    except:
        all = sys.exc_info()
        log.error("Failed to find Google Drive ID {f}: {a} {b} {c}"
                  .format(f=folder_id,a=all[0], b=all[1], c=all[2]))
        exit(1)

    log.debug("Validated Google Drive destination ID exists: {id}"
              .format(id=folder_id))

    mime = response.get('mimeType', [])
    if not mime:
        log.error("Failed to verify that Google Drive ID is a folder")
        exit(1)

    if mime != Google.mime_types['folder']:
        log.error("Destination Google Drive ID is not a folder")
        log.error("It's actually: {m}".format(m=mime))
        exit(1)

    log.debug("Validated Google Drive destination ID is a folder")

    return response

#===================================================================

def gd_upload_file(service, dest_folder, upload_filename, log):
    basename = os.path.basename(upload_filename)
    mime     = mimetypes.guess_type('file://{f}'
                                    .format(f=upload_filename))
    if mime == (None, None):
        if '.sqlite3' in upload_filename:
            mime = 'application/x-sqlite3'
        else:
            mime = 'text/plain'
        log.debug('Got no mime type: assume {m}'.format(m=mime))

    log.debug('Uploading file "{base}" (Google Drive folder ID: {folder}, MIME type {m})'
              .format(base=basename,
                      folder=dest_folder['id'],
                      m=mime))
    metadata = {
        'name'     : basename,
        'mimeType' : mime,
        'parents'  : [ dest_folder['id'] ]
    }
    media = MediaFileUpload(upload_filename,
                            mimetype=mime,
                            resumable=True)
    file = service.files().create(body=metadata,
                                  media_body=media,
                                  supportsTeamDrives=True,
                                  fields='name,id,webContentLink,webViewLink').execute()
    log.debug('Successfully uploaded file: "{f}" --> Google Drive file ID {id}'
              .format(f=basename, id=file['id']))

####################################################################
#
# Setup functions
#
####################################################################

def add_cli_args():
    tools.argparser.add_argument('--app-id',
                                 default='client_id.json',
                                 help='Filename containing Google application credentials')
    tools.argparser.add_argument('--user-credentials',
                                 default='user-credentials.json',
                                 help='Filename containing Google user credentials')

    tools.argparser.add_argument('files',
                                 metavar='file',
                                 nargs='+',
                                 help='File (or files) to upload to Google Drive')

    tools.argparser.add_argument('--dest',
                                 required=True,
                                 help='ID of target Google Folder')

    tools.argparser.add_argument('--verbose',
                                 required=False,
                                 action='store_true',
                                 default=True,
                                 help='If enabled, emit extra status messages during run')
    tools.argparser.add_argument('--debug',
                                 required=False,
                                 action='store_true',
                                 default=False,
                                 help='If enabled, emit even more extra status messages during run')

    args = tools.argparser.parse_args()

    # --debug also implies --verbose
    if args.debug:
        args.verbose = True

    # Sanity check that the specified files all exist
    for f in args.files:
        if not os.path.exists(f):
            print("File does not exist: {f}".format(f=f))
            exit(1)

    return args

####################################################################
#
# Main
#
####################################################################

def main():
    args = add_cli_args()
    log  = ECC.setup_logging(info=args.verbose,
                             debug=args.verbose,
                             logfile=None)

    apis = {
        'drive' : { 'scope'       : Google.scopes['drive'],
                    'api_name'    : 'drive',
                    'api_version' : 'v3',
        }
    }
    services = GoogleAuth.service_oauth_login(apis,
                                              app_json=args.app_id,
                                              user_json=args.user_credentials,
                                              log=log)
    service  = services['drive']

    dest_folder = gd_find_folder(service, args.dest, log)

    for f in args.files:
        log.info("Uploading file: {f}".format(f=f))
        gd_upload_file(service, dest_folder, f, log)

    log.info("Finished uploading files")

if __name__ == '__main__':
    main()
