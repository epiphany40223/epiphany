#!/usr/bin/env python3.7

import sys
sys.path.insert(0, '../../python')

import traceback
import datetime
import argparse
import smtplib
import csv
import os
import re

import ECC
import PDSChurch
import GoogleAuth

from pprint import pprint
from pprint import pformat
from datetime import datetime
from datetime import timedelta

from oauth2client import tools
from apiclient.http import MediaFileUpload
from email.message import EmailMessage

# SMTP / email basics
smtp_server  = 'smtp-relay.gmail.com'
smtp_from    = '"Epiphany Catholic Church" <email-update@epiphanycatholicchurch.org>'

# Copied from the Google Spreadsheets where Jotform is writing its
# results for the 2 forms
jotform_family_gfile_id = '1OzI7ENj763bcOYyUMRN-3htepHimtT7szAAdQXpsSSU'
jotform_member_gfile_id = '1KDOfNdVhgzSFqkVZBjqttrgdi8qLGpb5XBYF_bF72fQ'

# Team Drive folder where to upload the CSV/spreadsheet comparison
# output files
upload_team_drive_folder_id = '0ACmEer0DmBh4Uk9PVA'

gapp_id         = 'client_id.json'
guser_cred_file = 'user-credentials.json'
gsheet_mime_type= 'application/vnd.google-apps.spreadsheet'

# Scopes documented here:
# https://developers.google.com/drive/v3/web/about-auth
gscope = 'https://www.googleapis.com/auth/drive'

##############################################################################

def send_results_email(to, id, type, start, end, time_period, lines):
    body = list()

    body.append("""<html>
<body>
<h2>{type} data update</h2>
<h3>Time period: {start} through {end}</h3>
<p>Only showing results with changes compared to the data in the PDS database.</p>"""
                       .format(type=type, start=start, end=end))
    if id:
        url = 'https://docs.google.com/spreadsheets/d/{id}'.format(id=id)
        body.append('<p><a href="{url}">Link to spreadsheet containing these results</a>.</p>'
                     .format(url=url))
    body.append("<ol>")

    if lines is None or len(lines) == 0:
        body.append("<li>No {type} changes submitted during this time period</li>".format(type=type))
    else:
        body.extend(lines)

    body.append("""</ol>
</body>
</html>""")

    subject = '{type} census updates ({t})'.format(type=type, t=time_period)
    try:
        print('Sending "{subject}" email to {to}'
              .format(subject=subject, to=to))
        with smtplib.SMTP_SSL(host=smtp_server) as smtp:
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = smtp_from
            msg['To'] = to
            msg.set_content('\n'.join(body))
            msg.replace_header('Content-Type', 'text/html')

            smtp.send_message(msg)
    except:
        print("==== Error with {email}".format(email=to))
        print(traceback.format_exc())

##############################################################################

def export_gsheet_to_csv(service, google_sheet_id, fieldnames):
    response = service.files().export(fileId=google_sheet_id,
                                      mimeType='text/csv').execute()

    csvreader = csv.DictReader(response.decode('utf-8').splitlines(),
                               fieldnames=fieldnames)
    return csvreader

##############################################################################

def read_jotform(google, family_gfile_id, member_gfile_id):
    # The ordering of these fields is critical, although the names are not
    family_fields = [
        'SubmitDate',
	'EnvId',
	'fid',
	'AreYouStill',
	'DateCreated',
	'Street1',
	'Street2',
	'CityState',
	'Zip',
	'LandLine',
	'Comments',
	'IP',
	'JotformSubmissionID',
	'EditLink',
    ]
    family_csv = export_gsheet_to_csv(google, family_gfile_id,
                                      family_fields)

    # The ordering of these fields is critical, although the names are not
    member_fields = [
        'SubmitDate',
	'EnvId',
	'mid',
	'DateCreated',
	'Title',
	'First',
	'Nickname',
	'Middle',
	'Last',
	'Suffix',
	'BirthYear',
	'Email',
	'Cell',
	'MaritalStatus',
	'WeddingDate',
	'Occupation',
	'School',
	'EmergName',
	'EmergRelation',
	'EmergPhone',
	'Comments',
	'IP',
	'JotformSubmissionID',
	'EditLink',
    ]
    member_csv = export_gsheet_to_csv(google, member_gfile_id,
                                      member_fields)

    return family_csv, member_csv

##############################################################################

def setup_args():
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
    global families, members

    args = setup_args()

    log = ECC.setup_logging(debug=True)

    google = GoogleAuth.google_login(scope=gscope,
                                     app_json=args.app_id,
                                     user_json=args.user_credentials,
                                     api_name='drive',
                                     api_version='v3',
                                     log=log)

    jotform_family_csv, jotform_member_csv = read_jotform(google,
                                                          jotform_family_gfile_id,
                                                          jotform_member_gfile_id)

    (pds, pds_families,
     pds_members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                        log=log)

    #---------------------------------------------------------------
    # Debug
    for _, m in pds_members.items():
        if False and 'Squyres,Jeff' in m['Name']:
            log.debug("**** DEBUG: Jeff Squyres member")
            log.debug(pformat(m))

    log.debug("**** Looking for family...")
    for fid, f in pds_families.items():
        if False and 26561 == fid:
            log.debug("**** DEBUG: Family")
            log.debug(pformat(f))
    #---------------------------------------------------------------

    # Build a mapping of Env ID to FID
    envid_to_fid = dict()
    for fid, f in pds_families.items():
        envid_to_fid[f['ParKey'].strip()] = fid

    # Strategy: if a family replied to the home address link *or* any
    # of its member links, don't send them another email.
    families_who_responded = dict()

    # Delete all families and members of families who have already
    # responded
    for family in jotform_family_csv:
        env = family['EnvId'].strip()

        # First row is just the titles
        if 'Parish key' in env:
            continue

        if env not in envid_to_fid:
            continue

        fid = envid_to_fid[env]
        if fid in pds_families:
            families_who_responded[env] = True
            f = pds_families[fid]
            log.info("*** Family replied (home address): {eid} ({name})"
                     .format(eid=env, name=f['Name']))

            for m in f['members']:
                mid = m['MemRecNum']
                if mid in pds_members:
                    del pds_members[mid]

            del pds_families[fid]

    # Some people submitted members but not home addresses.  So go
    # delete all of them, too.
    for member in jotform_member_csv:
        env = member['EnvId'].strip()

        # First row is just the titles
        if 'Parish key' in env:
            continue

        if env not in envid_to_fid:
            continue

        fid = envid_to_fid[env]
        if fid in pds_families:
            families_who_responded[env] = True
            f = pds_families[fid]
            log.info("*** Family replied (member): {eid} ({name})"
                     .format(eid=env, name=f['Name']))

            for m in f['members']:
                mid = m['MemRecNum']
                if mid in pds_members:
                    del pds_members[mid]

            del pds_families[fid]

    #################################################################

    # All the families left are the ones who have not yet replied
    filename = 'families-who-have-not-yet-responded.csv'
    log.info("Writing: {f}".format(f=filename))
    with open(filename, 'w') as fwhnyr:
        for fid, f in pds_families.items():
            env = f['ParKey'].strip()

            log.info("Not responded: {env} ({name})"
                     .format(env=env, name=f['Name']))
            fwhnyr.write("{env}\n".format(env=env))

    filename = 'one-long-line-families-who-responded.txt'
    log.info("Number of families who responded: {num}"
             .format(num=len(families_who_responded)))
    log.info("Writing: {f}".format(f=filename))
    with open(filename, 'w') as f:
        first = True
        line = ''
        for env in sorted(families_who_responded):
            if first:
                first = False
                line  = env
            else:
                line += ', ' + env
        line += '\n'
        f.write(line)

    filename = 'one-long-line-families-who-did-not-respond.txt'
    log.info("Number of families who did not respond: {num}"
             .format(num=len(pds_families)))
    log.info("Writing: {f}".format(f=filename))
    with open(filename, 'w') as f:
        first = True
        line = ''
        for fid, family in pds_families.items():
            env = family['ParKey'].strip()
            if first:
                first = False
                line  = env
            else:
                line += ', ' + env
        line += '\n'
        f.write(line)

    # Close the databases
    pds.connection.close()

main()
