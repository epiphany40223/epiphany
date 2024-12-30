#!/usr/bin/env python3

import os
import sys

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

import re
import time
import calendar
import smtplib
import shutil
import argparse

from pprint import pprint

from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

# Globals
guser_cred_file = 'user-credentials.json'
guser_agent = 'py_mp3_uploader'
gauth_grace_period = 60
gauth_max_attempts = 3

args = None
log = None

to_gtd_dir = None
archive_dir = None

# Default for CLI arguments
smtp = ["smtp-relay.gmail.com",
        "jsquyres@epiphanycatholicchurch.org",
        "no-reply@epiphanycatholicchurch.org"]
incoming_ftp_dir = '/mnt/c/ftp/ECC-recordings'
data_dir = 'data'
app_id='client_id.json'
verbose = True
debug = False
logfile = "log.txt"
file_stable_secs = 60
# "ECC Recordings" Google Shared Drive ID
google_shared_drive_id = '0AJQlNh2zkxqWUk9PVA'

class ScannedFile:
    def __init__(self, filename, year, month, size, mtime, uploaded):
        self.filename = filename
        self.year     = year
        self.month    = month
        self.size     = size
        self.mtime    = mtime
        self.uploaded = uploaded

class GTDFile:
    def __init__(self, scannedfile, folder_webviewlink, file_webviewlink):
        self.scannedfile        = scannedfile
        self.folder_webviewlink = folder_webviewlink
        self.file_webviewlink   = file_webviewlink

#-------------------------------------------------------------------

def find_mp3_files(dir):
    scan = os.scandir(dir)
    scanned_files = []
    for entry in scan:
        # Only accept files
        if not entry.is_file():
            continue

        # Only a specific name format
        m = re.match(pattern=r'^.\d+-(\d\d\d\d)(\d\d)\d\d-\d\d\d\d\d\d.mp3$',
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

def google_login():
    settings = {
        'client_config_backend' : 'file',
        'client_config_file'    : args.app_id,

        'save_credentials'         : True,
        'save_credentials_backend' : 'file',
        'save_credentials_file'    : args.user_creds,

        'get_refresh_token' : True,
    }

    gauth = GoogleAuth(settings=settings)
    gauth.LocalWebserverAuth()

    drive = GoogleDrive(gauth)
    return drive

#===================================================================

def google_upload_file(drive, dest_folder, upload_filename):
    log.debug(f'Uploading GTD file "{upload_filename}" (parent: {dest_folder["id"]})')
    basename = os.path.basename(upload_filename)
    metadata = {
        'title'    : basename,
        'mimeType' : Google.mime_types['mp3'],
        'parents'  : [ {'id': dest_folder['id']} ],
    }

    file = drive.CreateFile(metadata)
    file.SetContentFile(upload_filename)
    file.Upload()

    log.debug(f'Successfully uploaded GTD file: "{basename}" (ID: {file["id"]})')

    return file

#-------------------------------------------------------------------

# Find a folder identified by this name/parent.  If it doesn't
# exist, create it.
def google_find_or_create_folder(drive, folder_name, parent_id):
    q = f"'{parent_id}' in parents"
    q += f" and title='{folder_name}'"
    q += f" and mimeType='{Google.mime_types['folder']}'"
    q += " and trashed=false"
    query = {
        'q': q,
        'corpora': 'allDrives',
    }
    file_list = drive.ListFile(query).GetList()
    for folder in file_list:
        if folder['title'] == folder_name:
            log.debug(f'Found GTD target folder: "{folder_name}" (ID: {folder["id"]})')
            return folder

    # If we didn't find it, then go create that folder
    log.debug("GTD target folder not found -- need to create it")
    data = {
        'title'    : folder_name,
        'parents'  : [ parent_id ],
        'mimeType' : Google.mime_types['folder'],
    }
    folder = drive.CreateFile(data)
    folder.Upload()
    log.debug("Created GTD target folder '{folder_name}' (ID: {folder['id']})")
    return folder

#-------------------------------------------------------------------

def google_create_dest_folder(drive, shared_drive, year, month):
    # Look for the year folder at the top of the shared drive
    year_folder = google_find_or_create_folder(drive, year, shared_drive['id'])

    # Look for the month folder in the year folder
    month_folder = google_find_or_create_folder(drive, month, year_folder['id'])

    return month_folder

#-------------------------------------------------------------------

def google_email_results(shared_drive, gtded_files):
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
</tr>\n\n'''.format("https://drive.google.com/drive/u/0/folders/" + shared_drive['id'],
                    shared_drive['name'])

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

    smtp_to   = args.smtp[1]
    smtp_from = args.smtp[2]
    ECC.send_email(to_addr=smtp_to,
                   subject=f"Google Shared Drive upload results ({subject})",
                   body=message,
                   log=log,
                   content_type='text/html',
                   from_addr=smtp_from)

#-------------------------------------------------------------------

def google_upload_files(drive, shared_drive, scanned_files):
    gtded_files = []
    for file in scanned_files:
        gtdfile = GTDFile(scannedfile=file,
                          folder_webviewlink=None,
                          file_webviewlink=None)

        src_filename = os.path.join(to_gtd_dir, file.filename)
        try:
            folder = google_create_dest_folder(drive, shared_drive,
                                            file.year, file.month)
            gtdfile.folder_webviewlink = folder['alternateLink']

            uploaded_file = google_upload_file(drive, folder, src_filename)
            gtdfile.file_webviewlink = uploaded_file['alternateLink']

            log.info(f"Uploaded {file.filename} to GTD successfully")

            # From this file from the "to GTD" dir so that we
            # don't try to upload it again the next time through
            os.unlink(src_filename)

            # Happiness!
            file.uploaded = True

        except:
            # Sadness :-(
            file.uploaded = False
            log.error("Unsuccessful GTD upload of {0}!".format(file.filename))
            raise

        gtded_files.append(gtdfile)

    # Send a single email with the results of all the GTD uploads
    google_email_results(shared_drive, gtded_files)

#-------------------------------------------------------------------

def upload_to_google():
    # If there's nothing to do, return (scandir does not return "." or
    # "..").  It's necessary to save the results from iterating
    # through the scandir() results because the iterator cannot be
    # reset.
    scanned_files = find_mp3_files(to_gtd_dir)
    if len(scanned_files) == 0:
        return

    # There's something to do!  So login to Google.
    drive = google_login()

    shared_drive = {
        'name' : 'Google Shared Drive',
        'id' : args.google_shared_drive_id,
    }

    # Go through all the files we found in the "to GTD" directory
    google_upload_files(drive, shared_drive, scanned_files)

####################################################################
#
# Watch for incoming FTP files functions
#
####################################################################

def check_for_incoming_ftp():
    scanned_files = find_mp3_files(args.incoming_ftp_dir)
    if len(scanned_files) == 0:
        log.info(f'No files found in FTP directory {args.incoming_ftp_dir}')
        return

    for file in scanned_files:
        log.info(f"Checking file: {args.incoming_ftp_dir}/{file.filename}")
        # If the file size is 0, skip it
        if file.size == 0:
            log.info("--> File size is 0 -- skipping")
            continue

        # If the file is still being uploaded to us (i.e., if the last
        # file modification time is too recent), skip it.
        log.debug("File: time now: {0}".format(time.time()))
        log.debug("File: mtime:    {0}".format(file.mtime))
        if (time.time() - file.mtime) < int(args.file_stable_secs):
            log.info("--> File is still changing -- skipping")
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

def add_cli_args():
    # Be sure to check the Google SMTP relay documentation for
    # non-authenticated relaying instructions:
    # https://support.google.com/a/answer/2956491
    parser = argparse.ArgumentParser('upload-mp3s')

    parser.add_argument('--smtp',
                        nargs=3,
                        required=False,
                        help='SMTP server hostname, to, and from addresses')
    parser.add_argument('--smtp-auth-file',
                        required=True,
                        help='File containing SMTP AUTH username:password')

    parser.add_argument('--data-dir',
                        required=False,
                        default=data_dir,
                        help='Directory to store internal data')
    parser.add_argument('--file-stable-secs',
                        required=False,
                        default=file_stable_secs,
                        help='Number of seconds for an incoming FTP file to not change before considered "complete"')

    parser.add_argument('--incoming-ftp-dir',
                        required=False,
                        default=incoming_ftp_dir,
                        help='Directory to watch for incoming MP3s')

    parser.add_argument('--google-shared-drive-id',
                        default=google_shared_drive_id,
                        help='ID of Google Shared Drive where to upload the files')
    parser.add_argument('--app-id',
                        required=False,
                        default=app_id,
                        help='Filename containing Google application ID')
    parser.add_argument('--user-creds',
                        required=False,
                        default=guser_cred_file,
                        help='Filename containing Google user credentials')

    parser.add_argument('--verbose',
                        required=False,
                        action='store_true',
                        default=verbose,
                        help='If enabled, emit extra status messages during run')
    parser.add_argument('--debug',
                        required=False,
                        action='store_true',
                        default=debug,
                        help='If enabled, emit even more extra status messages during run')
    parser.add_argument('--logfile',
                        required=False,
                        default=logfile,
                        help='Store verbose/debug logging to the specified file')

    global args
    args = parser.parse_args()

    # --debug also implies --verbose
    if args.debug:
        args.verbose = True
    log = ECC.setup_logging(info=args.verbose,
                            debug=args.debug,
                            logfile=args.logfile, rotate=True)

    # Sanity check args
    l = 0
    if args.smtp:
        l = len(args.smtp)
    if l > 0 and l != 3:
        log.error("Need exactly 3 arguments to --smtp: server to from")
        exit(1)

    smtp_server = args.smtp[0]
    ECC.setup_email(args.smtp_auth_file, smtp_server=smtp_server, log=log)

    if not os.path.isdir(args.data_dir):
        log.error('Data directory "{0}" does not exist or is not accessible'
                  .format(args.data_dir))
        exit(1)

    if not os.path.isdir(args.incoming_ftp_dir):
        log.error('Incoming FTP directory "{0}" does not exist or is not accessible'
                  .format(args.incoming_ftp_dir))
        exit(1)

    return log

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
            log.debug(f"Unable to obtain lockfile {self.lockfile} -- exiting")
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
    global log
    log = add_cli_args()

    filename = os.path.join(args.data_dir, "lockfile")
    with LockFile(filename) as lockfile:
        setup()
        check_for_incoming_ftp()
        upload_to_google()

    exit(0)

if __name__ == '__main__':
    main()
