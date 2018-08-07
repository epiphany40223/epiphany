#!/usr/bin/env python3.6

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

def upload_to_gsheet(google, folder_id, filename, csv_rows):
    if csv_rows is None or len(csv_rows) == 0:
        return None

    # First, write out a CSV file
    csv_filename = 'report-tmp.csv'
    try:
        os.remove(csv_filename)
    except:
        pass
    csvfile    = open(csv_filename, 'w')
    fieldnames = [ 'Envelope ID', 'Name', 'Field',
                   'Old value', 'New value' ]
    writer     = csv.DictWriter(csvfile, fieldnames=fieldnames,
                                quoting=csv.QUOTE_ALL)
    writer.writeheader()
    for row in csv_rows:
        writer.writerow(row)
    csvfile.close()

    # Now upload that file to Google Drive
    try:
        print('Uploading file to google "{file}"'
              .format(file=filename))
        metadata = {
            'name'     : filename,
            'mimeType' : gsheet_mime_type,
            'parents'  : [ folder_id ],
            'supportsTeamDrives' : True,
            }
        media = MediaFileUpload(csv_filename,
                                mimetype=gsheet_mime_type,
                                resumable=True)
        file = google.files().create(body=metadata,
                                     media_body=media,
                                     supportsTeamDrives=True,
                                     fields='id').execute()
        print('Successfully uploaded file: "{filename}" (ID: {id})'
              .format(filename=filename, id=file['id']))

    except:
        print('Google upload failed for some reason:')
        print(traceback.format_exc())
        exit(1)

    # Remove the temp file when we're done
    try:
        os.remove(csv_filename)
    except:
        pass

    return file['id']

##############################################################################

def _change(label, old_value, new_value, message):
    return {
        'label'     : label,
        'old_value' : old_value,
        'new_value' : new_value,
        'message'   : message,
    }

def _compare(changes, label, jot_value, pds_value):
    if jot_value is None:
        jot_value = ''
    if pds_value is None:
        pds_value = ''

    if jot_value.strip() == pds_value.strip():
        return

    message = ('{label}: {new_value}'
               .format(label=label, new_value=jot_value))
    changes.append(_change(label=label,
                           old_value=pds_value,
                           new_value=jot_value,
                           message=message))

def _convert_date(d):
    # Google is showing two different date formats.  Shug.  Handle
    # them both.
    result = re.match('(\d{4})-(\d{2})-(\d{2}) (\d{1,2}):(\d{2}):(\d{2})', d)
    if result is not None:
        submit_date = datetime(year   = int(result.group(1)),
                               month  = int(result.group(2)),
                               day    = int(result.group(3)),
                               hour   = int(result.group(4)),
                               minute = int(result.group(5)),
                               second = int(result.group(6)))

    else:
        result = re.match('(\d{1,2})/(\d{1,2})/(\d{4}) (\d{1,2}):(\d{2}):(\d{2})', d)
        submit_date = datetime(year   = int(result.group(3)),
                               month  = int(result.group(1)),
                               day    = int(result.group(2)),
                               hour   = int(result.group(4)),
                               minute = int(result.group(5)),
                               second = int(result.group(6)))


    return submit_date

def compare_families(google, start, end, pds_families, jotform_families):
    # First, take only the *last* family entry for any given family
    jf = dict()
    for row in jotform_families:
        # Skip the title row
        if row['fid'] == 'fid':
            continue

        jf[int(row['fid'])] = row

    # Now look at each family and compare their jotform data to their
    # PDS data
    email_lines = list()
    csv_rows    = list()
    blank       = dict()
    for fid, row in jf.items():
        family = pds_families[fid]

        # Is this submission between start and end?
        submit_date = _convert_date(row['SubmitDate'])
        if submit_date < start or submit_date > end:
            continue

        # If we got here, we have a submission within the window
        changes = list()
        if row['AreYouStill'] != 'Yes':
            changes.append(_change(label="Are you still a parishioner?",
                                   old_value="Yes",
                                   new_value=row['AreYouStill'],
                                   message=row['AreYouStill']))

        else:
            _compare(changes, 'Street address 1',
                     row['Street1'], family['StreetAddress1'])
            _compare(changes, 'Street address 2',
                     row['Street2'], family['StreetAddress2'])
            _compare(changes, 'City, State',
                     row['CityState'], family['city_state'])
            _compare(changes, 'Zip code',
                     row['Zip'], family['StreetZip'])

        if len(changes) > 0:
            env_id = family['ParKey'].strip()
            email_lines.append("<li><strong>ID {env}:</strong> {name}<br />"
                               .format(name=family['Name'],
                                       env=env_id))
            for c in changes:
                old_value = c['old_value']
                if old_value is None or len(old_value.strip()) == 0:
                    old_value = '&lt;blank&gt;'
                email_lines.append('<strong>{label}:</strong> {new} (<em>old: {old}</em>)<br />'
                                   .format(label=c['label'],
                                           new=c['new_value'],
                                           old=old_value))

                # CSV
                row = dict()
                row['Envelope ID'] = "' {}".format(str(env_id))
                row['Name']        = family['Name']
                row['Field']       = c['label']
                row['New value']   = c['new_value']
                row['Old value']   = c['old_value']
                csv_rows.append(row)

            csv_rows.append(blank)

            email_lines.append('</li><br />')

    return email_lines, csv_rows

##############################################################################

def compare_members(google, start, end, pds_members, jotform_members):
    # First, take only the *last* family entry for any given family
    jm = dict()
    for row in jotform_members:
        # Skip the title row
        if row['mid'] == 'mid':
            continue

        jm[int(row['mid'])] = row

    # Now look at each member and compare their jotform data to their
    # PDS data
    email_lines = list()
    csv_rows    = list()
    blank       = dict()
    for mid, row in jm.items():
        # Is this submission between start and end?
        submit_date = _convert_date(row['SubmitDate'])
        if submit_date < start or submit_date > end:
            continue

        # Here's something that can happen: the MID may not be found
        # because the member may actually have been deleted from PDS
        # since the census email was sent out (!).  So if we don't
        # find a MID, log it as an error.
        if mid not in pds_members:
            env_id = member['family']['ParKey'].strip()
            message = ("<li><strong>ID {env}:</strong> <font color=\"red\">{name} has been deleted from PDS and cannot be matched to their form submission</font><br />Stale member number: {mid}<br /></li><br />\n"
                   .format(name=member['Name'],
                           env=env_id,
                           mid=mid))
            print(message)
            email_lines.append(message)
            continue

        member = pds_members[mid]

        # If we got here, we have a submission within the window
        changes = list()
        if 'title' in member:
            val = member['title']
        else:
            val = ''
        _compare(changes, 'Title', row['Title'], val)
        _compare(changes, 'First', row['First'], member['first'])
        if 'nickname' in member:
            val = member['nickname']
        else:
            val = ''
        _compare(changes, 'Nickname', row['Nickname'], val)
        if 'middle' in member:
            val = member['middle']
        else:
            val = ''
        _compare(changes, 'Middle', row['Middle'], val)
        _compare(changes, 'Last', row['Last'], member['last'])
        if 'suffix' in member:
            val = member['suffix']
        else:
            val = ''
        _compare(changes, 'Suffix', row['Suffix'], val)

        if 'YearOfBirth' in member:
            val = member['YearOfBirth']
            if type(val) is int:
                val = str(val)
        else:
            val = ''
        _compare(changes, 'Birth Year', row['BirthYear'], val)

        emails = PDSChurch.find_preferred_email(member)
        email = None
        for em in emails:
            if em == row['Email']:
                email = em
                break
        if email is None:
            emails = PDSChurch.find_any_email(member)
            for em in emails:
                if em == row['Email']:
                    email = em + " (NOT PREFERRED)"
                    break
        _compare(changes, 'Preferred Email', row['Email'], email)

        phone = None
        if 'phones' in member:
            for pid in member['phones']:
                ph = member['phones'][pid]
                if ph['number'] == row['Cell']:
                    phone = ph['number']
        _compare(changes, 'Cell', row['Cell'], phone)

        if 'marital_status' in member:
            val = member['marital_status']
        else:
            val = ''
        _compare(changes, 'Marital Status', row['MaritalStatus'], val)
        if 'wedding_date' in member:
            val = member['wedding_date']
        else:
            val = ''
        _compare(changes, 'WeddingDate', row['WeddingDate'], val)
        if 'occupation' in member:
            val = member['occupation']
        else:
            val = ''
        _compare(changes, 'Occupation', row['Occupation'], val)

        # We don't have these in PDS yet
        _compare(changes, 'School',
                 row['School'], '')
        _compare(changes, 'Emergency Contact Name',
                 row['EmergName'], '')
        _compare(changes, 'Emergency Contact Relationship',
                 row['EmergRelation'], '')
        _compare(changes, 'Emergency Contact Phone',
                 row['EmergPhone'], '')

        if len(changes) > 0:
            env_id = member['family']['ParKey'].strip()
            email_lines.append("<li><strong>ID {env}:</strong> {name}<br />"
                               .format(name=member['Name'],
                                       env=env_id))
            for c in changes:
                old_value = c['old_value']
                if old_value is None or len(old_value.strip()) == 0:
                    old_value = '&lt;blank&gt;'
                email_lines.append('<strong>{label}:</strong> {new} (<em>old: {old}</em>)<br />'
                                   .format(label=c['label'],
                                           new=c['new_value'],
                                           old=old_value))

                # CSV
                row = dict()
                row['Envelope ID'] = "' {env}".format(env=env_id)
                row['Name']        =  member['Name']
                row['Field']       = c['label']
                row['New value']   = c['new_value']
                row['Old value']   = c['old_value']
                csv_rows.append(row)

            csv_rows.append(blank)

            email_lines.append('</li><br />')

    return email_lines, csv_rows

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
    tools.argparser.add_argument('--email',
                                 action='append',
                                 help='Send report to this email address')

    tools.argparser.add_argument('--gdrive-folder-id',
                                 help='If specified, upload a Google Sheet containing the results to this Team Drive folder')

    tools.argparser.add_argument('--all',
                                 action='store_const',
                                 const=True,
                                 help='If specified, run the comparison for all time (vs. running for the previous time period')

    global gapp_id
    tools.argparser.add_argument('--app-id',
                                 default=gapp_id,
                                 help='Filename containing Google application credentials')
    global guser_cred_file
    tools.argparser.add_argument('--user-credentials',
                                 default=guser_cred_file,
                                 help='Filename containing Google user credentials')

    args = tools.argparser.parse_args()

    if not args.email and not args.gdrive-folder-id:
        print("Must specify at least --email or --gdrive-folder-id")
        exit(1)

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
        if 'Squyres,Jeff' in m['Name']:
            log.debug("**** DEBUG: Jeff Squyres member")
            log.debug(pformat(m))

    log.debug("**** Looking for family...")
    for fid, f in pds_families.items():
        if 26561 == fid:
            log.debug("**** DEBUG: Family")
            log.debug(pformat(f))
    #---------------------------------------------------------------

    # Calculate the start and end of when we are analyzing in the
    # source data
    end = datetime.now()
    if args.all:
        start = datetime(year=1971, month=1, day=1)
    else:
        today = end.strftime('%a')
        if today == 'Sat' or today == 'Sun':
            print("It's the weekend.  Nothing to do!")
            exit(0)
        elif today == 'Mon':
            start = end - timedelta(days=3)
        else:
            start = end - timedelta(days=1)

    # No one wants to see the microseconds
    start = start - timedelta(microseconds=start.microsecond)
    end   = end   - timedelta(microseconds=end.microsecond)

    # Compare the data
    family_email_lines, family_csv_rows = compare_families(google,
                                                           start, end,
                                                           pds_families,
                                                           jotform_family_csv)
    member_email_lines, member_csv_rows = compare_members(google,
                                                          start, end,
                                                          pds_members,
                                                          jotform_member_csv)

    if args.all:
        time_period = 'all results to date'
    else:
        time_period = '{start} - {end}'.format(start=start, end=end)

    # Upload to a Google sheet?
    family_sheet_id = None
    member_sheet_id = None
    if args.gdrive_folder_id:
        filename = 'Family census updates {t}.csv'.format(t=time_period)
        family_sheet_id = upload_to_gsheet(google, args.gdrive_folder_id,
                                           filename, family_csv_rows)

        filename = 'Member census updates {t}.csv'.format(t=time_period)
        member_sheet_id = upload_to_gsheet(google, args.gdrive_folder_id,
                                           filename, member_csv_rows)

    # Email?
    if args.email:
        send_results_email(args.email, family_sheet_id, 'Family',
                           start, end, time_period, family_email_lines)
        send_results_email(args.email, member_sheet_id, 'Member',
                           start, end, time_period, member_email_lines)

    # Close the databases
    pds.connection.close()

main()
