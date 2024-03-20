#!/usr/bin/env python3

#####################################################################
# THIS SCRIPT CAN TAKE A VERY LONG TIME TO RUN -- e.g., 2-3 hours.
#####################################################################
#
# This script makes a trivial CSV containing a list of all the Google
# Groups in the epiphanycatholicchurch.org Google Workspace domain.
# It includes columns for:
#
# - group email address
# - number of google shared drives using this group for permissions
# - list of google shared drives using this group for permissions
#   --> NOTE: itadmin doesn't have access to *all* ECC Google Shared
#       Drives.  So this is not a 100% comprehensive list.  But it's a
#       pretty good approximation.
# - group description
# - number of members
#
# Upload this CSV, make it look a little pretty, and create a few more
# empty columns (see prior years for the columns to make).
#
# Look at
# https://drive.google.com/drive/folders/0B9JBC25MGsp3RjVOR3dWbkM1TFE
# for the folder containing the previous audits.  E.g., the 2022 audit
# sheet is
# https://docs.google.com/spreadsheets/d/1agrM5f6IMefyfrpLU7H_VyDDNo6Jun1B0DQTu1zHvlY/edit.
#
# Enjoy.


import os
import csv
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

import googleapiclient
from google.api_core import retry

from oauth2client import tools

from pprint import pprint

# Globals

args = None
log = None

# Default for CLI arguments
gapp_id='client_id.json'
guser_cred_file = 'user-credentials.json'
verbose = True
debug = False
logfile = "log.txt"

####################################################################
#
# Google queries
#
####################################################################

@retry.Retry(predicate=Google.retry_errors)
def find_all_google_shared_drives(service, log):
    log.debug(f"Looking for all ECC Google Shared Drives")

    drives = list()

    # Iterate over all (pages of) drives
    page_token = None
    while True:
        response = (service
                    .drives()
                    .list(pageToken=page_token,
                          pageSize=100,
                          # This gets ALL the Google Shared Drives,
                          # even the ones we don't have access to.
                          useDomainAdminAccess=True)
                    .execute())
        for drive in response.get('drives', []):
            log.debug(f"Got drive: {drive}")
            drives.append(drive)

        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break

    return drives

#-------------------------------------------------------------------

# See if a given email address has "read" access to any files in a
# specific Google Shared Drive.
#
# Return a list of the first 10 files that this email address has
# "read" access to.
@retry.Retry(predicate=Google.retry_errors)
def query_shared_drive_for_reader(service, drive, address, log):
    log.info(f"Searching contents of Google Shared Drive: {drive['name']} ({drive['id']}) for {address}")

    # We could iterate over all the pages of data, but really, we only
    # need to know that a given email address is used in the
    # permissions by *any* files.  As a courtesy, get the first 10
    # files, but don't bother getting any more.

    files = list()
    try:
        response = (service
                    .files()
                    .list(pageToken=None,
                          pageSize=10,
                          corpora='drive',
                          q=f"trashed=false and '{address}' in readers",
                          driveId=drive['id'],
                          includeItemsFromAllDrives=True,
                          supportsAllDrives=True)
                    .execute())
        files.extend(response.get('files', []))
    except googleapiclient.errors.HttpError as e:
        log.error(f"Got permission denied {drive['name']} ({drive['id']}) -- skipping")

    log.debug(f"Found {len(files)} files in {drive['name']} ({drive['id']})")
    return files

#-------------------------------------------------------------------

@retry.Retry(predicate=Google.retry_errors)
def find_all_groups(service, log):
    groups = list()

    log.debug(f"Looking for all Google Groups")

    # Iterate over all (pages of) groups
    page_token = None
    while True:
        response = (service
                    .groups()
                    .list(pageToken=page_token,
                          domain='epiphanycatholicchurch.org')
                    .execute())
        for group in response.get('groups', []):
            log.debug(f"Got group: {group}")
            groups.append(group)

        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break

    return groups

#-------------------------------------------------------------------

def write_csv(groups, log_type, log):
    filename = 'groups-listing.csv'
    key = 'drives'
    with open(filename, "w") as fp:
        fieldnames = ['Group email address', 'Description', 'Number of members',

                      # This is the number of Google Shared Drives
                      # where this Google Group is used as a
                      # permission.
                      'Num Google Shared Drives',
                      'Google Shared Drives']
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()

        for group in groups:
            num_gsd = ''
            gsd = 'not yet discovered'
            if key in group:
                num_gsd = group['drives']['num drives']
                gsd = ', '.join([drive['name'] for drive in group['drives']['drives found']])

            writer.writerow({
                'Group email address' : group['email'],
                'Description' : group['name'],
                'Number of members' : group['directMembersCount'],
                'Num Google Shared Drives' : num_gsd,
                'Google Shared Drives' : gsd,
            })

    log.info(f"Wrote {log_type}: {filename}")


####################################################################
#
# Setup functions
#
####################################################################

def setup_cli_args():
    global gapp_id
    tools.argparser.add_argument('--app-id',
                                 default=gapp_id,
                                 help='Filename containing Google application credentials')
    global guser_cred_file
    tools.argparser.add_argument('--user-credentials',
                                 default=guser_cred_file,
                                 help='Filename containing Google user credentials')

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

    # --debug also implies --verbose
    if args.debug:
        args.verbose = True

    return args

####################################################################
#
# Main
#
####################################################################

def main():
    args = setup_cli_args()

    log = ECC.setup_logging(info=args.verbose,
                            debug=args.debug,
                            logfile=args.logfile,
                            rotate=True)

    apis = {
        'drive' : { 'scope'       : Google.scopes['drive'],
                    'api_name'    : 'drive',
                    'api_version' : 'v3', },
        'admin' : { 'scope'       : Google.scopes['admin'],
                    'api_name'    : 'admin',
                    'api_version' : 'directory_v1', },
        'group' : { 'scope'       : Google.scopes['group'],
                    'api_name'    : 'groupssettings',
                    'api_version' : 'v1', },
    }
    services = GoogleAuth.service_oauth_login(apis,
                                              app_json=args.app_id,
                                              user_json=args.user_credentials,
                                              log=log)
    service_drive = services['drive']
    service_admin = services['admin']
    service_group = services['group']

    groups = find_all_groups(service_admin, log)
    log.info(f"Found {len(groups)} Google Groups")

    # For each Group, see if we can find any Google Shared Drives
    # where they are used as permissions.  This is just a helpful
    # datapoint to know if this Google Groups is still being used or
    # not.

    # First, find all the Google Shared Drives (note that this finds
    # *all* Google Shared Drives, even if this particular user doesn't
    # have access to read them).
    shared_drives = find_all_google_shared_drives(service_drive, log)
    log.info(f"Found {len(shared_drives)} Google Shared Drives")

    log.warning("=================================================================")
    log.warning("This may take a LONG time to run!")
    log.warning("It may take an hour or three")
    log.warning("=================================================================")

    # For each of the Google Groups, check each shared drive and see
    # if that Group has read access (which is the lowest access) to
    # any files in that Google Shared Drive.
    for group in groups:
        num_drives = 0
        num_files = 0
        drives_found = list()
        for drive in shared_drives:
            # Remember: we're only bothering to get the first 10 files
            # in the drive that this group has access to (no need to
            # get *all* files -- we really only care if there are >0
            # files; we get the first 10 files just as a matter of
            # course).
            contents = query_shared_drive_for_reader(service_drive, drive,
                                                     group['email'], log)
            if len(contents) > 0:
                num_drives += 1
                num_files += len(contents)
                drives_found.append(drive)

        group['drives'] = {
            'num files' : num_files,
            'num drives' : num_drives,
            'drives found' : drives_found,
        }
        if num_files == 0:
            log.info(f"Did not find any Google Shared Drives readable by {group['email']}")
        else:
            log.info(f"Found {num_drives} Google Shared Drives / {num_files} files readable by {group['email']}")

        # Write out the results to a CSV as we go along.  This process
        # takes a long time, so write out partial results as we go
        # along, just in case something happens and this script aborts
        # before it is able to complete the entire
        # (num_groups*num_drives) examination process.
        write_csv(groups, "partial results", log)

    # Write out the final results.  This should be no different than
    # the last CSV we wrote, but emit something slightly different for
    # the log message.
    write_csv(groups, "final results", log)

if __name__ == '__main__':
    main()
