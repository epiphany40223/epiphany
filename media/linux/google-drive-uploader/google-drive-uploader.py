#!/usr/bin/env python3

"""
This is a fairly dumb script to upload specific files to a specific
folder/location on Google Drive.  It has no additional intelligence /
logic.
"""

import os
import sys
import mimetypes

# We assume that there is a "ecc-python-modules" sym link in this
# directory that points to the directory with ECC.py and friends.
moddir = os.path.join(os.getcwd(), 'ecc-python-modules')
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)
# On MS Windows, git checks out sym links as a file with a single-line
# string containing the name of the file that the sym link points to.
if os.path.isfile(moddir):
    with open(moddir) as fp:
        dir = fp.readlines()
    moddir = os.path.join(os.getcwd(), dir[0])

sys.path.insert(0, moddir)

import ECC
import Google

import argparse

from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

#===================================================================

def google_login(args, log):
    settings = {
        'client_config_backend' : 'file',
        'client_config_file'    : args.app_id,

        'save_credentials'         : True,
        'save_credentials_backend' : 'file',
        'save_credentials_file'    : args.user_credentials,

        'get_refresh_token' : True,
    }

    gauth = GoogleAuth(settings=settings)
    gauth.LocalWebserverAuth()

    drive = GoogleDrive(gauth)

    return gauth, drive

#===================================================================

def gd_upload_file(drive, dest_folder_id, upload_filename, log):
    data = {
        'parents' : [ {'id' : dest_folder_id } ],
    }
    file = drive.CreateFile(data)
    file.SetContentFile(upload_filename)
    try:
        file.Upload()
    except Exception as e:
        if 'File not found' in str(e):
            log.critical(f"ID {dest_folder_id} does not appear to be a folder")
            exit(1)
        else:
            raise

    basename = os.path.basename(upload_filename)
    log.debug(f'Successfully uploaded file: "{basename}" --> Google Drive file ID {file["id"]}')

####################################################################
#
# Setup functions
#
####################################################################

def add_cli_args():
    parser = argparse.ArgumentParser('upload-to-google')

    parser.add_argument('--app-id',
                        default='client_id.json',
                        help='Filename containing Google application credentials')
    parser.add_argument('--user-credentials',
                        default='user-credentials.json',
                        help='Filename containing Google user credentials')

    parser.add_argument('--slack-token-filename',
                        help='File containing the Slack bot authorization token')
    parser.add_argument('--logfile',
                        required=False,
                        help='Logfile filename')

    parser.add_argument('files',
                        metavar='file',
                        nargs='+',
                        help='File (or files) to upload to Google Drive')

    parser.add_argument('--dest',
                        required=True,
                        help='ID of target Google Folder')

    parser.add_argument('--verbose',
                        required=False,
                        action='store_true',
                        default=True,
                        help='If enabled, emit extra status messages during run')
    parser.add_argument('--debug',
                        required=False,
                        action='store_true',
                        default=False,
                        help='If enabled, emit even more extra status messages during run')

    args = parser.parse_args()

    # --debug also implies --verbose
    if args.debug:
        args.verbose = True

    return args

def check_cli_args(args, log):
    # Sanity check that the specified files all exist
    for f in args.files:
        if not os.path.exists(f):
            log.critical("File does not exist: {f}".format(f=f))
            exit(1)

    return args

####################################################################
#
# Main
#
####################################################################

def main():
    args = add_cli_args()
    global log
    log = ECC.setup_logging(info=args.verbose,
                            debug=args.debug,
                            logfile=args.logfile, rotate=True,
                            slack_token_filename=args.slack_token_filename)
    check_cli_args(args, log)

    gauth, drive = google_login(args, log)
    for f in args.files:
        log.info("Uploading file: {f}".format(f=f))
        gd_upload_file(drive, args.dest, f, log)

    log.info("Finished uploading files")

if __name__ == '__main__':
    main()
