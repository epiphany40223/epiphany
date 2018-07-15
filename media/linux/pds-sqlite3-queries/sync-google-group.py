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

import sys
sys.path.insert(0, '../../../python')

import logging.handlers
import httplib2
import smtplib
import logging
import sqlite3
import json
import time
import os

import ECC
import PDSChurch
import GoogleAuth

from email.message import EmailMessage

from pprint import pprint
from pprint import pformat

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
        "no-reply@epiphanycatholicchurch.org"]
gapp_id='client_id.json'
guser_cred_file = 'user-credentials.json'
verbose = True
debug = False
logfile = "log.txt"

# JMS Change me to itadmin
fatal_notify_to = 'jsquyres@gmail.com'

#-------------------------------------------------------------------

def send_mail(to, subject, message_body, html=False, log=None):
    if not args.smtp:
        log.debug('Not sending email "{0}" because SMTP not setup'.format(subject))
        return

    smtp_server = args.smtp[0]
    smtp_from = args.smtp[1]

    if log:
        log.info('Sending email to {to}, subject "{subject}"'
                 .format(to=to, subject=subject))
    with smtplib.SMTP_SSL(host=smtp_server) as smtp:
        if args.debug:
            smtp.set_debuglevel(2)

        msg = EmailMessage()
        msg.set_content(message_body)
        msg['Subject'] = subject
        msg['From'] = smtp_from
        msg['To'] = to
        if html:
            msg.replace_header('Content-Type', 'text/html')
        else:
            msg.replace_header('Content-Type', 'text/plain')

        smtp.send_message(msg)

#-------------------------------------------------------------------

def email_and_die(msg):
    sys.stderr.write(msg)
    sys.stderr.write("Aborting")

    send_mail(fatal_notify_to,
              'Fatal error from PDS<-->Google Group sync', msg)

    exit(1)


####################################################################
#
# Google setup / auth functions
#
####################################################################

def google_login(scope, log):
    # Put a loop around this so that it can re-authenticate via the
    # OAuth refresh token when possible.  Real errors will cause the
    # script to abort, which will notify a human to fix whatever the
    # problem was.
    auth_count = 0
    while auth_count < gauth_max_attempts:
        try:
            # Authorize the app and provide user consent to Google
            app_cred = GoogleAuth.load_app_credentials(args.app_id)
            user_cred = GoogleAuth.load_user_credentials(scope, app_cred,
                                                         args.user_credentials)
            service = GoogleAuth.authorize(user_cred, 'admin',
                                           'directory_v1')
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
        email_and_die("Failed to authenticate to Google {0} times.\nA human needs to figure this out."
                  .format(gauth_max_attempts))

    return service

####################################################################
#
# Sync functions
#
####################################################################

def compute_sync(sync, pds_emails, group_emails, log=None):
    # Find all the addresses to add to the google group, and also find
    # all the addresses to remove from the google group.

    to_add_to_group      = list()
    to_delete_from_group = group_emails.copy()
    for pds_email in pds_emails:
        log.debug("Checking PDS mail: {}".format(pds_email))

        found = False
        if pds_email in group_emails:
            found = True

            # Note: we *may* have already deleted this email
            # address from to_delete_from_group (i.e., if multiple
            # people are in the group who share an email address)
            if pds_email in to_delete_from_group:
                to_delete_from_group.remove(pds_email)

        if not found and pds_email not in to_add_to_group:
            to_add_to_group.append(pds_email)

    if log:
        log.info("To delete from Google Group {group}:"
                 .format(group=sync['ggroup']))
        log.info(to_delete_from_group)
        log.info("To add to Google Group {group}:"
                 .format(group=sync['ggroup']))
        log.info(to_add_to_group)

    return to_add_to_group, to_delete_from_group

#-------------------------------------------------------------------

def do_sync(sync, service, to_add, to_delete, log=None):
    email_message = list()

    if sync['skip']:
        return

    # Entries in the "to_delete" list are just email addresses (i.e.,
    # a plain list of strings -- not dictionaries).
    for email in to_delete:
        str = "DELETING: {email}".format(email=email)

        if log:
            log.info(str)
        email_message.append(str)

        service.members().delete(groupKey=sync['ggroup'],
                                 memberKey=email).execute()

    # Entries in the "to_add" list are dictionaries with a name and
    # email (the name is there solely so that we can include it in the
    # email).
    for email in to_add:
        str = ("ADDING: {email}"
               .format(email=email))

        if log:
            log.info(str)
        email_message.append(str)

        group_entry = {
            'email' : email,
            'role'  : 'MEMBER'
        }
        service.members().insert(groupKey=sync['ggroup'],
                                 body=group_entry).execute()

    # Do we need to send an email?
    if len(email_message) > 0:
        subject = 'Update to Google Group for '
        body = ("""Updates to the Google Group {email}:

{lines}

These email addresses were obtained from PDS:

"""
                .format(email=sync['ggroup'],
                        lines='\n'.join(email_message)))

        count    = 1
        subj_add = list()
        if 'ministries' in sync:
            for m in sync['ministries']:
                body  = body + ('{i}. Members in the "{m}" ministry\n'
                                .format(i=count, m=m))
                count = count + 1
                subj_add.append(m)

        if 'keywords' in sync:
            for k in sync['keywords']:
                body  = body + ('{i}. Members with the "{k}" keyword\n'
                                .format(i=count, k=k))
                count = count + 1
                subj_add.append(k)

        subject = subject + ', '.join(subj_add)

        send_mail(to=sync['notify'], subject=subject, message_body=body)

####################################################################
#
# Google queries
#
####################################################################

def google_group_find_emails(service, sync, log=None):
    emails = list()

    # Iterate over all (pages of) group members
    page_token = None
    while True:
        response = (service
                    .members()
                    .list(pageToken=page_token,
                          groupKey=sync['ggroup'],
                          fields='members(email)').execute())
        for group in response.get('members', []):
            emails.append(group['email'].lower())

        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break

    if log:
        log.info("Google Group membership for {group}"
                 .format(group=sync['ggroup']))
        log.info(emails)

    return emails

####################################################################
#
# PDS queries
#
####################################################################

def _member_in_any_ministry(member, ministries):
    if 'active_ministries' not in member:
        return False

    for m in member['active_ministries']:
        mname = m['Description']
        if mname in ministries:
            return True

    return False

def _member_has_any_keyword(member, keywords):
    if 'keywords' not in member:
        return False

    for k in member['keywords']:
        if k in keywords:
            return True

    return False

def pds_find_ministry_emails(members, sync, log=None):
    emails     = list()
    ministries = list()
    keywords   = list()

    # Make the sync ministries be an array
    if 'ministries' in sync:
        if type(sync['ministries']) is list:
            ministries = sync['ministries']
        else:
            ministries = [ sync['ministries'] ]

    # Make the sync keywords be a group
    if 'keywords' in sync:
        if type(sync['keywords']) is list:
            keywords = sync['keywords']
        else:
            keywords = [ sync['keywords'] ]

    # Walk all members looking for those in any of the ministries or
    # those that have any of the keywords.
    for mid, member in members.items():
        if (_member_in_any_ministry(member, ministries) or
            _member_has_any_keyword(member, keywords)):
            em = PDSChurch.find_any_email(member)
            log.info("Found PDS email: {}".format(em))
            if em:
                emails.extend(em)

    if log:
        log.info("PDS emails for ministries {m} and keywords {k}"
                 .format(m=ministries, k=keywords))
        log.info(emails)

    return emails

####################################################################
#
# Setup functions
#
####################################################################

def setup_cli_args():
    # Be sure to check the Google SMTP relay documentation for
    # non-authenticated relaying instructions:
    # https://support.google.com/a/answer/2956491
    global smtp
    tools.argparser.add_argument('--smtp',
                                 nargs=2,
                                 default=smtp,
                                 help='SMTP server hostname and from addresses')

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

    # Sanity check args
    l = 0
    if args.smtp:
        l = len(args.smtp)
    if l > 0 and l != 2:
        log.error("Need exactly 2 arguments to --smtp: server from")
        exit(1)

    return args

####################################################################
#
# Main
#
####################################################################

def main():
    args = setup_cli_args()

    log = ECC.setup_logging(info=args.verbose,
                            debug=args.verbose,
                            logfile=args.logfile)

    (pds, pds_families,
     pds_members) = PDSChurch.load_families_and_members(filename=args.sqlite3_db,
                                                        parishioners_only=False,
                                                        log=log)

    google = google_login(gscope, log)

    ecc = '@epiphanycatholicchurch.org'
    synchronizations = [
        {
            'ministries' : [ '18-Technology Committee' ],
            'ggroup'     : 'tech-committee{ecc}'.format(ecc=ecc),
            'notify'     : 'business-manager{ecc},jeff@squyres.com'.format(ecc=ecc),
            'skip'       : False
        },
        {
            'ministries' : [ '99-Homebound MP3 Recordings' ],
            'ggroup'     : 'mp3-uploads-group{ecc}'.format(ecc=ecc),
            'notify'     : 'business-manager{ecc},jeff@squyres.com'.format(ecc=ecc),
            'skip'       : False
        },
        {
            'ministries' : [ 'L-Parish Pastoral Council' ],
            'ggroup'     : 'ppc{ecc}'.format(ecc=ecc),
            'notify'     : 'lynne{ecc},jeff@squyres.com'.format(ecc=ecc),
            'skip'       : False,
        },
        {
            'ministries' : [ '13-Finance Advisory Council' ],
            'ggroup'     : 'administration-committee{ecc}'.format(ecc=ecc),
            'notify'     : 'business-manager{ecc},jeff@squyres.com'.format(ecc=ecc),
            'skip'       : False
        },
        {
            'ministries' : [ '64-Singles Explore Life (SEL)' ],
            'ggroup'     : 'sel{ecc}'.format(ecc=ecc),
            'notify'     : 'lynne{ecc},jeff@squyres.com'.format(ecc=ecc),
            'skip'       : False
        },
        {
            'keywords'   : [ 'ECC Sheet Music access' ],
            'ggroup'     : 'music-ministry-sheet-music-access{ecc}'.format(ecc=ecc),
            'notify'     : 'linda{ecc},jsquyres@gmail.com'.format(ecc=ecc),
            'skip'       : False
        },
    ]

    for sync in synchronizations:
        pds_emails = pds_find_ministry_emails(pds_members, sync, log=log)
        group_emails = google_group_find_emails(google, sync, log=log)

        to_add, to_delete = compute_sync(sync, pds_emails, group_emails,
                                         log=log)
        if not args.dry_run:
            do_sync(sync, google, to_add, to_delete, log=log)

    # All done
    pds.connection.close()

if __name__ == '__main__':
    main()
