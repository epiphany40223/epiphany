#!/usr/bin/env python3

# This script looks for everyone with the special PDS Family status
# that indicates that they participated in the ECC 2020 Stewardship
# drive, and sends them a "Thank you" email.
#
# For the 2020 drive, this script was run exactly once: after the
# drive.
#
# For the 2021 drive, it would probably be better to send "thank you"
# emails every night.  See the README.md file for thoughts on this.

import sys
sys.path.insert(0, '../../python')

import traceback
import datetime
import argparse
import smtplib
import os
import re

import ECC
import PDSChurch

import helpers

from pprint import pprint
from pprint import pformat

from oauth2client import tools
from apiclient.http import MediaFileUpload
from email.message import EmailMessage

#------------------------------------------------------------------------------

from constants import jotform_member_ministries
from constants import jotform_ministry_groups
from constants import jotform_member_fields
from constants import jotform_family_fields
from constants import already_submitted_fam_status

from constants import gapp_id
from constants import guser_cred_file
from constants import jotform_member_gfile_id
from constants import jotform_family_gfile_id
from constants import upload_team_drive_folder_id
from constants import gsheet_editors

from constants import ministry_start_date
from constants import ministry_end_date

from constants import title
from constants import stewardship_begin_date
from constants import stewardship_end_date

from constants import smtp_server
from constants import smtp_from

from constants import email_image_url
from constants import api_base_url

##############################################################################

ecc = '@epiphanycatholicchurch.org'

##############################################################################

# Send "thank you" emails to everyone with the "Stewardship 2020"
# Family status
def thank_you_emails(args, pds_families, pds_members, log):

    subject = 'Thank you for participating in Epiphany\'s 2020 Stewardship Drive!'
    # Read the email file
    with open('email-thank-you-and-survey.html', 'r') as f:
        msg_template = f.read()

    # Find Families with the right status
    for family in pds_families.values():
        if ('status' not in family or
            not family['status'] == already_submitted_fam_status):
            continue

        # Now found the spouse+HoH emails
        to_emails = list()
        to_names  = dict()
        for m in family['members']:
            if helpers.member_is_hoh_or_spouse(m):
                em = PDSChurch.find_any_email(m)
                to_emails.extend(em)
                to_names[m['last']] = True

        if len(to_emails) == 0:
            log.warning("Found Family {name}, but no email addresses -- skipping"
                        .format(name=family['Name']))

        # We found a Family!
        log.info("Found Family: {name}".format(name=family['Name']))

        # Personalize the emails
        # NOTE: can't use .format() because of CSS use of {}
        to    = ','.join(to_emails)
        names = ' and '.join(sorted(to_names))
        body  = msg_template.replace("{family_names}", names)

        # JMS OVERRIDE
        continue

        #---------------------------------------------------------------------

        try:
            log.info('Sending "{subject}" email to {to}'
                     .format(subject=subject, to=to))
            with smtplib.SMTP_SSL(host=smtp_server) as smtp:
                msg = EmailMessage()
                msg['Subject'] = subject
                msg['From'] = smtp_from
                msg['To'] = to
                msg.set_content(body)
                msg.replace_header('Content-Type', 'text/html')

                # This assumes that the file has a single line in the format of username:password.
                with open(args.smtp_auth_file) as f:
                    line = f.read()
                    smtp_username, smtp_password = line.split(':')

                # Login; we can't rely on being IP whitelisted.
                try:
                    smtp.login(smtp_username, smtp_password)
                except Exception as e:
                    log.error(f'Error: failed to SMTP login: {e}')
                    exit(1)

                smtp.send_message(msg)
        except:
            print("==== Error with {email}".format(email=to))
            print(traceback.format_exc())

##############################################################################

def setup_args():
    global gapp_id
    tools.argparser.add_argument('--app-id',
                                 default=gapp_id,
                                 help='Filename containing Google application credentials')
    tools.argparser.add_argument('--smtp-auth-file',
                                 required=True,
                                 help='File containing SMTP AUTH username:password')
    global guser_cred_file
    tools.argparser.add_argument('--user-credentials',
                                 default=guser_cred_file,
                                 help='Filename containing Google user credentials')

    args = tools.argparser.parse_args()

    return args

##############################################################################

def main():
    global families, members

    args = setup_args()
    log = ECC.setup_logging(debug=False)

    #---------------------------------------------------------------

    log.info("Reading PDS data...")
    (pds, pds_families,
     pds_members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                        log=log)

    # Close the databases
    pds.connection.close()

    # Remove non-parishioner families
    pds_families = helpers.filter_parishioner_families_only(pds_families)

    #---------------------------------------------------------------

    thank_you_emails(args, pds_families, pds_members, log)

main()
