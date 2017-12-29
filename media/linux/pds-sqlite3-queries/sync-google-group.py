#!/usr/bin/env python3.6

"""Script to iterate through ministries from PDS and sync the
membership of a Google Group to match.

- find all Members and Church Contacts (i.e., staff) in the ministry
  - there is a hard-coded list of Ministry names (which must exactly
    match the names in PDS) and their corresponding Google Group email
    address
  - Members must be in a Ministry of that exact name
  - Church Contacts must have a keyword of "LIST:<ministry_name>" or
    just "<ministry_name>" (because keywords have a max length, and
    sometimes "LIST:<ministry_name>" is too long).
- find the preferred email addresses for each of them
- make the associated Google Group be exactly that set of email addresses

No locking / lockfile is used in this script because it is assumed
that simultaneous access is prevented by locking at a higher level
(i.e., ../run-all.py).

-----

This script was developed and tested with Python 3.6.4.  It has not
been tested with other versions (e.g., Python 2.7.x).

-----

This script requires a "client_id.json" file with the app credentials
from the Google App dashboard.  This file is not committed here in git
for obvious reasons (!).

The client_id.json file is obtained from
console.developers.google.com, project name "PDS to Google Groups".
The project is owned by itadmin@epiphanycatholicchurch.org.

This script will create/fill a "user-credentials.json" file in the
same directory with the result of getting user consent for the Google
Account being used to authenticate.

Note that this script works on Windows, Linux, and OS X.  But first,
you need to install some Python classes:

    pip install --upgrade google-api-python-client
    pip install --upgrade httplib2
    ^^ NOTE: You may need to "sudo pip3.6 ..." instead of "sudo pip ..."

"""

import logging.handlers
import httplib2
import smtplib
import logging
import sqlite3
import json
import time
import os

from email.message import EmailMessage

from apiclient.discovery import build
from oauth2client import tools
from oauth2client.file import Storage
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import OAuth2WebServerFlow

# Globals
gauth_max_attempts = 3
guser_agent = 'pds_google_group_sync'
# Scopes documented here:
# https://developers.google.com/drive/v3/web/about-auth
gscope = 'https://www.googleapis.com/auth/admin.directory.group'

args = None
log = None

# Default for CLI arguments
smtp = ["smtp-relay.gmail.com",
        "jeff@squyres.com,business-manager@epiphanycatholicchurch.org",
        "no-reply@epiphanycatholicchurch.org"]
gapp_id='client_id.json'
guser_cred_file = 'user-credentials.json'
verbose = True
debug = False
logfile = "log.txt"

# Which database number to use?
# At ECC, the active database is 1.
database = 1

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

    send_mail('Fatal error from PDS<-->Google Group sync', msg)

    exit(1)


####################################################################
#
# Google setup / auth functions
#
####################################################################

def google_load_app_credentials(file):
    # Read in the JSON file to get the client ID and client secret
    with open(file) as data_file:
        app_cred = json.load(data_file)

    log.debug('Loaded application credentials from {0}'
                  .format(file))
    return app_cred

#-------------------------------------------------------------------

def google_load_user_credentials(scope, app_cred, user_cred_file):
    # Get user consent
    client_id       = app_cred['installed']['client_id']
    client_secret   = app_cred['installed']['client_secret']
    flow            = OAuth2WebServerFlow(client_id, client_secret, scope)
    flow.user_agent = guser_agent

    file      = user_cred_file
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

def google_authorize(user_cred):
    http    = httplib2.Http()
    http    = user_cred.authorize(http)
    service = build('admin', 'directory_v1', http=http)

    log.debug('Authorized to Google')
    return service

#-------------------------------------------------------------------

def google_login():
    # Put a loop around this so that it can re-authenticate via the
    # OAuth refresh token when possible.  Real errors will cause the
    # script to abort, which will notify a human to fix whatever the
    # problem was.
    auth_count = 0
    while auth_count < gauth_max_attempts:
        try:
            # Authorize the app and provide user consent to Google
            log.debug("Authenticating to Google...")
            app_cred = google_load_app_credentials(args.app_id)
            user_cred = google_load_user_credentials(gscope, app_cred,
                                                     args.user_credentials)
            service = google_authorize(user_cred)
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

####################################################################
#
# Sync functions
#
####################################################################

def compute_sync(pair, pds_emails, group_emails):
    # Find all the addresses to add to the google group, and also find
    # all the addresses to remove from the google group.

    to_add_to_group = list()
    for pds_email in pds_emails:
        log.debug("Checking PDS mail: {}".format(pds_email))

        found = False
        for group_email in group_emails:
            if pds_email['email'] == group_email:
                group_emails.remove(group_email)
                found = True
                break

        if not found and pds_email not in to_add_to_group:
            to_add_to_group.append(pds_email)

    to_delete_from_group = group_emails

    log.info("To delete from Google Group {group}:"
             .format(group=pair['ggroup']))
    log.info(to_delete_from_group)
    log.info("To add to Google Group {group}:"
             .format(group=pair['ggroup']))
    log.info(to_add_to_group)

    return to_add_to_group, to_delete_from_group

#-------------------------------------------------------------------

def do_sync(pair, service, to_add, to_delete):
    email_message = list()

    # Entries in the "to_delete" list are just email addresses (i.e.,
    # a plain list of strings -- not dictionaries).
    for email in to_delete:
        str = "DELETING: {email}".format(email=email)

        log.info(str)
        email_message.append(str)

        service.members().delete(groupKey=pair['ggroup'],
                                 memberKey=email).execute()

    # Entries in the "to_add" list are dictionaries with a name and
    # email (the name is there solely so that we can include it in the
    # email).
    for record in to_add:
        str = ("ADDING: {name} <{email}>"
               .format(name=record['name'],
                       email=record['email']))

        log.info(str)
        email_message.append(str)

        group_entry = {
            'email' : record['email'],
            'role'  : 'MEMBER'
        }
        service.members().insert(groupKey=pair['ggroup'],
                                 body=group_entry).execute()

    # Do we need to send an email?
    if len(email_message) > 0:
        subject = ('Update to Google Group for {ministry}'
                   .format(ministry=pair['ministry']))
        body = ("""Updates to the Google Group {email}:

{lines}

These email addresses were obtained from PDS:

1. Members in the "{ministry}" ministry
2. Church Contacts with the "LIST:{ministry}" keyword
   (or just "{ministry}")"""
                .format(email=pair['ggroup'],
                        ministry=pair['ministry'],
                        lines='\n'.join(email_message)))

        send_mail(subject=subject, message_body=body)

####################################################################
#
# Google queries
#
####################################################################

def group_find_emails(service, group_email_address):
    emails = list()

    # Iterate over all (pages of) group members
    page_token = None
    while True:
        response = (service
                    .members()
                    .list(pageToken=page_token,
                          groupKey=group_email_address,
                          fields='members(email)').execute())
        for group in response.get('members', []):
            emails.append(group['email'].lower())

        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break

    log.info("Google Group membership for {group}"
             .format(group=group_email_address))
    log.info(emails)

    return emails

####################################################################
#
# PDS queries
#
####################################################################

def _sort_by_email(record):
    # Helper for Python built-in "sorted()" function
    return record['email']

def pds_find_preferred_emails(pds, name, id, table, field):
    # PDS allows storing multiple emails per Member / Church Contact.
    # It has a secondary field "EmailOverMail" that is the "preferred"
    # checkmark in the PDS GUI: 0 or more of the email addresses
    # associated with a Member or Church Contact may be checked.  Our
    # algorithm will therefore be: take all the preferred email
    # addresses.  If no address is preferred, sort the (non-preferred)
    # addresses and take the first one.

    all_emails = list()
    results = list()

    query = ('SELECT EmailAddress,EmailOverMail '
             'FROM   {table} '
             'WHERE  {field}={id}'
             .format(id=id, table=table, field=field))

    log.debug(query)
    for row in pds.execute(query).fetchall():
        record = {
            'name'      : name,
            'email'     : row[0],
            'preferred' : row[1]
        }
        email = row[0].lower()
        preferred = row[1]

        all_emails.append(record)
        if preferred:
            results.append(record)

    # If we didn't find any preferred emails, sort the list and take
    # the first one.
    if len(results) == 0 and len(all_emails) > 0:
        sorted_emails = sorted(all_emails, key=_sort_by_email)
        first_record = sorted_emails[0]
        results.append(first_record)

    log.debug("Returning PDS results for {id} from {table}: {results}"
              .format(id=id, table=table, results=results))
    return results

#-------------------------------------------------------------------

def _list_unique_extend(source, new_entries):
    # Add all the entries from new_entries to the source list, but
    # only if they aren't already in the source list.
    for entry in new_entries:
        if entry not in source:
            source.append(entry)

    return source

#-------------------------------------------------------------------

def pds_find_ministry_emails(pds, ministry):
    emails = list()

    # First, we have to find the Members in this ministry.
    query = ('SELECT     Mem_DB.MemRecNum,Mem_DB.Name '
             'FROM       MemMin_DB '
             'INNER JOIN MinType_DB ON MinType_DB.MinDescRec=MemMin_DB.MinDescRec '
             'INNER JOIN Mem_DB ON Mem_DB.MemRecNum=MemMin_DB.MemRecNum '
             'INNER JOIN StatusType_DB ON StatusType_DB.StatusDescRec=MemMin_DB.StatusDescRec '
             'WHERE      MinType_DB.Description=\'{ministry}\' AND '
                        'StatusType_DB.Description NOT LIKE \'%occasional%\' AND '
                        'StatusType_DB.Active=1 AND '
                        'Mem_DB.CensusMember{db}=1 AND '
                        'Mem_DB.deceased=0'
             .format(ministry=ministry, db=database))

    # For each Member, we have to find their preferred email address(es)
    for row in pds.execute(query).fetchall():
        member_id   = row[0]
        member_name = row[1]

        preferred = pds_find_preferred_emails(pds=pds,
                                              name=member_name,
                                              table='MemEmail_DB',
                                              field='MemRecNum',
                                              id=member_id)

        # Make sure we don't get duplicate emails in the result list
        # (e.g., if we add Members with the same email address, such
        # as husband+wife that share an email account).
        emails = _list_unique_extend(emails, preferred)

    # Now find Church Contacts in this ministry (i.e., that have a
    # keyword "LIST:<ministry_name>" or "<ministry_name>")
    query = ('SELECT     ChurchContact_DB.CCRec,ChurchContact_DB.Name '
             'FROM       ChurchContact_DB '
             'INNER JOIN CCKW_DB ON CCKW_DB.CCRec = ChurchContact_DB.CCRec '
             'INNER JOIN CCKWType_DB ON CCKWType_DB.CCKWRec = CCKW_DB.CCKWRec '
             'WHERE      CCKWType_DB.Description = \'LIST:{ministry}\' OR '
                        'CCKWType_DB.Description = \'{ministry}\''
             .format(ministry=ministry))

    # Find the Church Contact preferred email address(es)
    for row in pds.execute(query).fetchall():
        cc_id   = row[0]
        cc_name = row[1]

        preferred = pds_find_preferred_emails(pds=pds,
                                              name=cc_name,
                                              table='CCEmail_DB',
                                              field='RecNum',
                                              id=cc_id)

        # Make sure we don't get duplicate emails in the result list
        # (e.g., if we add Church Contacts that are also Members).
        emails = _list_unique_extend(emails, preferred)

    global log
    log.info("PDS emails for ministry {ministry}".format(ministry=ministry))
    log.info(emails)

    return emails

####################################################################
#
# PDS setup functions
#
# (i.e., open/close SQLite3 database that was previously created from
# the PDS database)
#
####################################################################

def pds_connect():
    global args

    pds_conn = sqlite3.connect(args.sqlite3_db)
    pds_cur = pds_conn.cursor()

    return pds_cur

#-------------------------------------------------------------------

def pds_disconnect(pds):
    pds.close()

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

def setup_cli_args():
    # Be sure to check the Google SMTP relay documentation for
    # non-authenticated relaying instructions:
    # https://support.google.com/a/answer/2956491
    global smtp
    tools.argparser.add_argument('--smtp',
                                 nargs=3,
                                 default=smtp,
                                 help='SMTP server hostname, to, and from addresses')

    global gapp_id
    tools.argparser.add_argument('--app-id',
                                 default=gapp_id,
                                 help='Filename containing Google application credentials')
    global guser_cred_file
    tools.argparser.add_argument('--user-credentials',
                                 default=guser_cred_file,
                                 help='Filename containing Google user credentials')

    tools.argparser.add_argument('--dry-run',
                                 action='store_true',
                                 help='Do not actually update the Google Group; just show what would have been done')

    tools.argparser.add_argument('--sqlite3-db',
                                 required=True,
                                 help='SQLite3 database containing PDS data')

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

    # --dry-run implies --verbose
    if args.dry_run:
        args.verbose = True

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

    file = args.app_id
    if not os.path.isfile(file):
        diediedie("Error: App ID JSON file {0} does not exist"
                  .format(file))
    if not os.access(file, os.R_OK):
        diediedie("Error: App ID credentials JSON file {0} is not readable"
                  .format(file))

####################################################################
#
# Main
#
####################################################################

def main():
    setup_cli_args()

    pds = pds_connect()
    google = google_login()

    pairs = [
        { 'ministry' : '18-Technology Committee',
          'ggroup'   : 'tech-committee@epiphanycatholicchurch.org' },
        { 'ministry' : '99-Homebound MP3 Recordings',
          'ggroup'   : 'mp3-uploads-group@epiphanycatholicchurch.org' }
    ]

    for pair in pairs:
        pds_emails = pds_find_ministry_emails(pds, pair['ministry'])
        group_emails = group_find_emails(google, pair['ggroup'])
        to_add, to_delete = compute_sync(pair, pds_emails, group_emails)
        if not args.dry_run:
            do_sync(pair, google, to_add, to_delete)

    pds_disconnect(pds)

if __name__ == '__main__':
    main()
