#!/usr/bin/env python3

"""

This script reads a simple Google Sheet that has two columns in it:

1. Date
2. Comma-delimited list of email addresses

This script downloads the sheet, finds the row with the most recently-past date,
and sets the membership of the Google Group to the comma-delimited list of email
addresses on that row.

For any email address that is added to the group, they get a "You have been
added!" email notifying them of that fact.  Similarly, for any email address
that is removed from the group, they get a "You have been removed" email.

"""

import os
import sys
import csv
import json
import time
import argparse
import httplib2
import datetime
import googleapiclient
from google.api_core import retry

from oauth2client import tools
from io import StringIO
from dateutil.parser import parse as dateutil_parse

# We assume that there is a "ecc-python-modules" sym link in this
# directory that points to the directory with ECC.py and friends.
moddir = os.path.join(os.getcwd(), 'ecc-python-modules')
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)

sys.path.insert(0, moddir)

import ECC
import GoogleAuth
import Google

#-------------------------------------------------------------------

# Globals
args = None
log  = None

# Default for CLI arguments
gapp_id         = 'client_id-ppc-feedback.json'
guser_cred_file = 'user-credentials-ppc-feedback.json'
verbose         = True
debug           = False
logfile         = None

groups = [
    {
        'name' : 'PPC Feedback',
        'group' : 'ppc-feedback@epiphanycatholicchurch.org',
        'gsheet_id' : '1s9guctll5_E21uVCnamEVkkN6_91KkHxozwNy9WaMBg',
        'contact' : 'Angie Fox <angie@epiphanycatholicchurch.org>',
    },
    {
        'name' : 'FAC Feedback',
        'group' : 'fac-feedback@epiphanycatholicchurch.org',
        'gsheet_id' : '1VX4DpQQxHDw76G96OhpH1Ra6rmH_WjN4eJyKSRVln4I',
        'contact' : 'Mary Downs <mary@epiphanycatholicchurch.org>',
    },
]

# This group is useful for testing
groups_testing = [
    {
        'name' : 'Google sheet-driven Google Group testing',
        'group' : 'test@epiphanycatholicchurch.org',
        'gsheet_id' : '1CRVoNTMIomzk5UymCcovWZ3cDd9HjB7-jVRTSryFWhc',
        'contact' : 'Jeff Squyres <jsquyres@epiphanycatholicchurch.org>',
    },
]
# JMS Uncomment this line to use the above test group (and not the production
# groups)
#groups = groups_testing

#-------------------------------------------------------------------

@retry.Retry(predicate=Google.retry_errors)
def add_google_group_member(google, google_group, email, log):
    log.info(f"Adding {email} to Google Group {google_group}")

    group_entry = {
        'email' : email,
        'role'  : 'MEMBER'
    }
    try:
        google.members().insert(groupKey=google_group,
                                 body=group_entry).execute()

    except googleapiclient.errors.HttpError as e:
        # NOTE: If we failed because this is a duplicate, then don't
        # worry about it.
        j = json.loads(e.content)
        for err in j['error']['errors']:
            if err['reason'] == 'duplicate':
                log.warning(f"Google says a duplicate of {email} already in the group -- ignoring")
                return

        log.error(f"Failed to add {email} to {google_group}: unknown Google error! {e}")
        raise e

    except Exception as e:
        log.error(f"Failed to add {email} to {google_group}: unknown Google error! {e}")
        raise e

@retry.Retry(predicate=Google.retry_errors)
def delete_google_group_member(google, google_group, email, id, log):
    # We delete by ID (instead of by email address) because of a weird
    # corner case:
    #
    # - foo@example.com (a non-gmail address) is in a google group,
    #   but has no Google account
    # - later, foo@example.com visits
    #   https://accounts.google.com/SignupWithoutGmail and gets a
    #   Google account associated with that email address
    #
    # In this case, Google seems to be somewhat confused:
    # foo@example.com is still associated with the Group, but it's the
    # non-Google-account foo@example.com.  But if we attempt to move
    # that email address, it'll try to remove the Google-account
    # foo@example.com (and therefore fail).
    #
    # So we remove by ID, and that unambiguously removes the correct
    # member from the Group.
    log.info(f"Deleting {email} (ID {id})) from group {google_group}")

    google.members().delete(groupKey=google_group,
                             memberKey=id).execute()

def sync_members(google, data, current_members, desired_members, log):
    # Compute which members should be added and which members should be
    # deleted.
    to_add    = list()
    to_delete = list()

    current_emails = [ x['email'].strip() for x in current_members ]
    desired_emails = [ x.strip() for x in desired_members['emails'].split(',') ]

    log.debug(f"Sync: current_members: {current_emails}")
    log.debug(f"Sync: desired_members: {desired_emails}")

    # Compute who should be added
    # We *add* to the group first so that we never have an empty Google Group
    for desired in desired_emails:
        if desired not in current_emails:
            to_add.append(desired)
            add_google_group_member(google, data['group'], desired, log)

    # Compure who should be deleted
    for current in current_members:
        if current['email'] not in desired_emails:
            to_delete.append(current['email'])
            delete_google_group_member(google, data['group'], current['email'], current['id'], log)

    if len(to_add) == 0 and len(to_delete) == 0:
        log.info("No changes necessary")
        return

    if len(to_add) > 0:
        subject = f"Starting: Your {data['name']} email rotation has begun"
        addrs   = ','.join(to_add)
        content = f"""Your rotation on {data['name']} emails has started!

This means that emails sent to {data['group']} will be forwarded to {addrs} during this rotation.

When you reply to these emails, the email will come from your email address.  Please be sure to CC {data['group']} so that your reply is shared with others in this rotation with you and recorded in our archive.  If you have any questions about a response, please contact {data['contact']}.

Keep track of the emails and topics that you are hearing; you are asked to share them as part of our next meeting.

You’ll receive another email when your rotation completes.

Thank you for your time and dedication to Epiphany!"""
        ECC.send_email(','.join(to_add), subject, content, log)

    if len(to_delete) > 0:
        subject = f"Your {data['name']} email rotation: completed!"
        addrs   = ','.join(to_delete)
        content = f"""Your rotation to respond to respond to {data['name']} emails has completed.

This means that emails sent to {data['group']} will NO LONGER be forwarded to {addrs}.

Thank you for your time and dedication to Epiphany!"""
        ECC.send_email(','.join(to_delete), subject, content, log)

####################################################################
#
# Google queries
#
####################################################################

@retry.Retry(predicate=Google.retry_errors)
def google_group_find_members(google, google_group, log):
    group_members = list()

    # Iterate over all (pages of) group members
    page_token = None
    while True:
        response = (google
                    .members()
                    .list(pageToken=page_token,
                          groupKey=google_group,
                          fields='nextPageToken,members(email,id)').execute())
        for entry in response.get('members', []):
            group_members.append(entry)

        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break

    log.debug(f"Google Group membership for {google_group}: {group_members}")

    return group_members

# Find the row from the spreadsheet that pertains to now
def find_desired(sheet_data, log):
    today   = datetime.datetime.now().date()
    desired = {
        'date'   : datetime.date(year=1, month=1, day=1),
        'emails' : '',
    }

    for row in sheet_data:
        if row['date'] > desired['date'] and row['date'] <= today:
            desired = row

    log.debug(f"Found desired: {desired}")
    return desired

# Download the data from Google Sheet, and convert all the dates to
# Python datetime.date's
def download_google_sheet(google, gfile, log):
    log.info(f"Downloading Sheet {gfile}...")

    # Make this a subroutine so that we can wrap it in retry.Retry()
    @retry.Retry(predicate=Google.retry_errors)
    def _download_csv_sheet():
        return google.files().export(fileId=gfile,
                                         mimeType=Google.mime_types['csv']).execute()

    csv_content = _download_csv_sheet()

    out       = list()
    fakefile  = StringIO(csv_content.decode('utf-8'))
    csvreader = csv.reader(fakefile)
    for row in csvreader:
        date_str  = row[0]
        email_str = row[1].strip().lower()

        # Check to make sure that the date string is actually a date.
        # Skip it if it does not.
        if not date_str:
            continue

        # If there's a date but not corresponding email address, skip
        # this entry.
        if email_str == "":
            continue

        try:
            date = dateutil_parse(date_str).date()
            out.append({
                'date'   : dateutil_parse(date_str).date(),
                'emails' : email_str,
            })
        except Exception as e:
            log.warning(f'Cannot parse date "{date_str}"; skipping')

    return out

####################################################################
#
# Setup functions
#
####################################################################

def setup_cli_args():
    tools.argparser.add_argument('--smtp-auth-file',
                                 required=True,
                                 help='File containing SMTP AUTH username:password')

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

    # --debug implies --verbose
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
                            logfile=args.logfile)
    ECC.setup_email(args.smtp_auth_file, smtp_debug=args.debug, log=log)

    apis = {
        'admin' : { 'scope'       : Google.scopes['admin'],
                    'api_name'    : 'admin',
                    'api_version' : 'directory_v1', },
        'drive' : { 'scope'       : Google.scopes['drive'],
                    'api_name'    : 'drive',
                    'api_version' : 'v3', },
    }
    services = GoogleAuth.service_oauth_login(apis,
                                              app_json=args.app_id,
                                              user_json=args.user_credentials,
                                              log=log)
    service_admin = services['admin']
    service_drive = services['drive']

    for item in groups:
        log.info(f"Synchronizing: {item['name']}")
        sheet_data = download_google_sheet(service_drive, item['gsheet_id'], log)
        desired    = find_desired(sheet_data, log)
        current    = google_group_find_members(service_admin, item['group'], log)

        sync_members(service_admin, item, current, desired, log)

if __name__ == '__main__':
    main()
