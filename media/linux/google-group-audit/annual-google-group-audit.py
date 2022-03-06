#!/usr/bin/env python3
#
# This script makes a trivial CSV containing a list of all the Google
# Groups in the epiphanycatholicchurch.org Google Workspace domain.
# It includes columns for:
#
# - group email address
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

def write_csv(groups, log):
    filename = 'groups-listing.csv'
    with open(filename, "w") as fp:
        fieldnames = ['Group email address', 'Description', 'Number of members']
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()

        for group in groups:
            writer.writerow({
                'Group email address' : group['email'],
                'Description' : group['name'],
                'Number of members' : group['directMembersCount'],
            })

    log.info(f"Wrote: {filename}")


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
    service_admin = services['admin']
    service_group = services['group']

    groups = find_all_groups(service_admin, log)
    write_csv(groups, log)

    print("Hello")

if __name__ == '__main__':
    main()
