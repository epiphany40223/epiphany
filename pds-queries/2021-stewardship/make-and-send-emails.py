#!/usr/bin/env python3

import sys
sys.path.insert(0, '../../python')

import traceback
import datetime
import calendar
import argparse
import smtplib
import sqlite3
import uuid
import time
import csv
import os
import re

import ECC
import Google
import PDSChurch
import GoogleAuth

import helpers

from oauth2client import tools

from pprint import pprint
from pprint import pformat
from email.message import EmailMessage

#--------------------------------------------------------------------------

from constants import already_submitted_fam_status

from constants import gapp_id
from constants import guser_cred_file
from constants import jotform_gsheet_gfile_id

from constants import stewardship_year
from constants import title

from constants import smtp_server
from constants import smtp_from

smtp_subject = 'Epiphany ' + title

from constants import email_image_url
from constants import api_base_url

from constants import jotform

from constants import MINISTRY_SQL_TYPE
from constants import PLEDGE_SQL_TYPE

from constants import COL_AM_INVOLVED
from constants import COL_NOT_INVOLVED

from constants import MAX_PDS_FAMILY_MEMBER_NUM

#--------------------------------------------------------------------------

# JMS Kinda yukky that "args" is global
args = None

###########################################################################

# Returns the redirect URL
def insert_url_cookie(uid, type, url, cookies, log=None):
    # Insert the URL in the cookies database
    cookie      = uuid.uuid4()
    url_escaped = url.replace("'", "''")
    query       = ("INSERT INTO cookies "
             "(cookie,type,uid,url,creation_timestamp) "
             "VALUES ('{cookie}','{type}','{uid}','{url}',{ts});"
             .format(cookie=cookie, type=type, uid=uid, url=url_escaped,
                     ts=int(calendar.timegm(time.gmtime()))))
    cookies.execute(query)

    # Write the cookie to the DB immediately (in case someone is
    # reading/copying the sqlite3 database behind the scenes).
    cookies.connection.commit()

    if log:
        log.debug(f"SQL query: {query}")

    return f'{api_base_url}{cookie}'

##############################################################################

# The ministry URL is comprised of three sections:
#
# 1. The base jotform URL
# 2. Some Family-specific field data
# 3. N sets of Member-specific field data
#
# This routine constructs #1 and #2.
def make_ministry_jotform_base_url(family, log=None):
    # Calculate the family values if they have not already done so
    if 'calculated' not in family:
        year = f'{stewardship_year - 2000 - 1:02}'
        helpers.calculate_family_values(family, year=year, log=log)

    char = '?'
    url  = jotform.url
    for entry in jotform.pre_fill_data['family']:
        # Recall: the "fields" entry will be a single field for global data
        field  = entry['fields']
        value  = entry['value_func'](family)
        next   = f'{char}{field}={value}'
        url   += next
        char   = '&'

        if log:
            log.debug(f"Ministry base URL added: {next}")

    return url

# This routine constructs #3 (from above)
def make_ministries_url_portion(member, member_number, log=None):
    def _check(ministry, member):
        for member_ministry in member['active_ministries']:
            if ministry == member_ministry['Description']:
                return True
        return False

    #-----------------------------------------------------------------------

    # First, add some per-Member non-minstry data
    url = ''
    for entry in jotform.pre_fill_data['per_member']:
        # The "fields" member will contain an array of fields; we
        # want the (member_number)th one.
        field = entry['fields'][member_number]
        value = entry['value_func'](member)
        next  = f'&{field}={value}'
        url  += next

        if log:
            log.debug(f"Ministry member URL portion: {next}")

    #-----------------------------------------------------------------------

    # Now add in all the per-Member ministry data
    for grid in jotform.ministry_grids:
        field = grid.member_fields[member_number]

        for row_num, row in enumerate(grid.rows):
            column       = COL_NOT_INVOLVED
            pds_ministry = row['pds_ministry']

            match = False
            if type(pds_ministry) is list:
                for m in pds_ministry:
                    match = _check(m, member)
                    if match:
                        break
            else:
                match = _check(pds_ministry, member)

            if match:
                column = COL_AM_INVOLVED

            url += f"&{field}[{row_num}][{column}]=true"
            # Example: parishLeadership[1][2]`=true`

    return url

#--------------------------------------------------------------------------

def send_family_email(message_body, family, submissions,
                      cookies, smtp, log=None):
    # We won't get here unless there's at least one email address to
    # which to send.  But do a sanity check anyway.
    data = family['stewardship']
    if len(data['to_addresses']) == 0:
        return 0

    bounce_url    = data['bounce_url']
    text          = f'{stewardship_year} Epiphany Stewardship Renewal'
    ministry_link = f'<a href="{bounce_url}">{text}</a>'

    #---------------------------------------------------------------------

    smtp_to = ",".join(data['to_addresses'])

    # JMS DEBUG
    #was = smtp_to
    #smtp_to = "Jeff Squyres <jsquyres@gmail.com>"
    #log.info(f"Sending to (OVERRIDE): {smtp_to} (was {was})")
    #---------------------------------------------------------------------

    if log:
        log.info("    Sending to Family {names} at {emails}"
                 .format(names=' / '.join(data['to_names']), emails=smtp_to))

    # Note: we can't use the normal string.format() to substitute in
    # values because the HTML/CSS includes a bunch of instances of {}.
    #message_body = message_initial()
    message_body = message_body.replace("{img}", email_image_url)
    message_body = message_body.replace("{family_names}",
                        family['hoh_and_spouse_salutation'])
    message_body = message_body.replace("{bounce_url}", ministry_link)

    # JMS kinda yukky that "args" is global
    global args
    if args.do_not_send:
        log.info("NOT SENDING EMAIL (--do-not-send)")
    else:
        try:
            msg = EmailMessage()
            msg['Subject'] = smtp_subject
            msg['From'] = smtp_from
            msg['To'] = smtp_to
            msg.set_content(message_body)
            msg.replace_header('Content-Type', 'text/html')

            smtp.send_message(msg)
        except:
            log.error("==== Error with {email}"
                      .format(email=smtp_to))
            log.error(traceback.format_exc())

    return len(data['to_addresses'])

###########################################################################

def _send_family_emails(message_body, families, submissions,
                        cookies, log=None):
    # Send one email to the head-of-household + spouse in each family
    # in the dictionary.  Send them in fid order so that if we get
    # interrupted and have to start again, we can do so
    # deterministically.

    email_sent = list()
    email_not_sent = list()

    # This assumes that the file has a single line in the format of username:password.
    with open(args.smtp_auth_file) as f:
        line = f.read()
        smtp_username, smtp_password = line.split(':')

    # Open just one connection to the SMTP server
    with smtplib.SMTP_SSL(host=smtp_server,
                          local_hostname='api.epiphanycatholicchurch.org') as smtp:
        # Login; we can't rely on being IP whitelisted.
        try:
            smtp.login(smtp_username, smtp_password)
        except Exception as e:
            log.error(f'Error: failed to SMTP login: {e}')
            exit(1)

        # Iterate through all the family emails that we need to send
        sorted_fids = sorted(families)
        for fid in sorted_fids:
            family = families[fid]
            log.info(f"=== Family: {family['Name']}")

            to_names              = dict()
            to_addresses          = list()
            members_by_mid        = dict()
            family['stewardship'] = {
                'sent_email' : True
            }

            # Scan through the Members and generate a list of names and
            # email addresses that we need.
            for member in family['members']:
                members_by_mid[member['MemRecNum']] = member
                log.info(f"    Member: {member['Name']}")
                if helpers.member_is_hoh_or_spouse(member):
                    em = PDSChurch.find_any_email(member)
                    to_addresses.extend(em)

                to_names[member['last']] = True

            if len(to_addresses) == 0:
                family['stewardship']['sent_email'] = False
                family['stewardship']['reason not sent'] = 'No HoH/Spouse emails'
                if log:
                    log.info(f"    *** Have no HoH/Spouse emails for Family {family['Name']}")

            # As of September 2021, Jotform cannot handle more than 6 Members'
            # worth of data in a single form (except with Chrome on a
            # laptop/desktop -- all other cases fail on the final submit).  So
            # if this Family has more than 6 Members, do not send to them.
            if len(family['members']) > MAX_PDS_FAMILY_MEMBER_NUM:
                family['stewardship']['sent_email'] = False
                family['stewardship']['reason not sent'] = 'Too many Members in Family'
                if log:
                    log.info(f"    *** Too many Members in Family ({len(family['members'])} > {MAX_PDS_FAMILY_MEMBER_NUM}) -- will not send")

            #----------------------------------------------------------------

            # We *always* need 'stewardship' set on the family.  So set it
            # before potentially bailing out if we're not going to send to
            # this family.

            # Save the things we have computed to far on the family
            # (we use this data in making the ministry jotform base URL, below)
            family['stewardship']['to_addresses'] = to_addresses
            family['stewardship']['to_names'] = to_names

            # Check if we're going to send
            if not family['stewardship']['sent_email']:
                email_not_sent.append(family)
                continue

            #----------------------------------------------------------------

            # Construct the base ministry jotform URL with the Family-global data
            jotform_url = make_ministry_jotform_base_url(family, log)

            # Now add to the ministry jotform URL all the Member data
            # Since we might truncate the number of family members, do them in
            # a deterministic order.
            for member_number, mid in enumerate(sorted(members_by_mid)):
                member = members_by_mid[mid]

                # Add to the overall ministry URL with data for this Member
                jotform_url += make_ministries_url_portion(member,
                                                            member_number, log)

            # Now that we have the entire ministry jotform URL,
            # make a bounce URL for it
            bounce_url  = insert_url_cookie(fid, MINISTRY_SQL_TYPE,
                                            jotform_url, cookies)
            family['stewardship']['bounce_url'] = bounce_url

            send_count = send_family_email(message_body, family,
                                           submissions,
                                           cookies, smtp, log=log)
            email_sent.append(family)

    return email_sent, email_not_sent

###########################################################################

def send_all_family_emails(args, families, submissions,
                            cookies, log=None):
    return _send_family_emails(args.email_content, families, submissions,
                               cookies, log)

#--------------------------------------------------------------------------

def send_file_family_emails(args, families, submissions,
                            cookies, log=None):
    some_families = dict()

    log.info("Reading Envelope ID file...")
    env_ids = list()
    with open(args.env_id_file, "r") as ef:
        lines = ef.readlines()
        for line in lines:
            env_ids.append(line.strip())
    log.info(env_ids)

    log.debug("Looking for Envelope IDs...")
    for fid, f in families.items():
        env = f['ParKey'].strip()
        if env in env_ids:
            log.info("Found Envelope ID {eid} in list (Family: {name})"
                     .format(eid=env, name=f['Name']))
            some_families[fid] = f

    return _send_family_emails(args.email_content, some_families, submissions,
                                cookies, log)

#--------------------------------------------------------------------------

def send_unsubmitted_family_emails(args, families, submissions,
                            cookies, log=None):
    # Find all families that have not *completely* submitted everything.
    # I.e., any family that has not yet submitted:
    # - all Family Member ministry forms
    # - a Family pledge form
    #
    # Then also remove any Family that has "2021 Stewardship" set as
    # their Family status.  This means that someone manually put this
    # keyword on the Family, probably indicating that they have
    # submitted their stewardship data on paper.

    log.info("Looking for Families with incomplete submissions...")
    some_families = dict()
    for fid, f in families.items():
        want = False

        if fid not in submissions:
            log.info("Family {n} (fid {fid}) no electronic submission"
                    .format(n=f['Name'], fid=fid))
            want = True

        # This keyword trumps everything: if it is set on the Family, they do not get a reminder email.
        if 'status' in f and f['status'] == already_submitted_fam_status:
            log.info(f"Family {f['Name']} (fid {fid}) has status {already_submitted_fam_status}")
            want = False

        if want:
            log.info("Unsubmitted family (fid {fid}): {n}"
                    .format(n=f['Name'], fid=fid))
            some_families[fid] = f
        else:
            log.info("Completed family (fid {fid}): {n} -- skipping"
                    .format(n=f['Name'], fid=fid))

    return _send_family_emails(args.email_content, some_families, submissions,
                                cookies, log)

#--------------------------------------------------------------------------

def send_some_family_emails(args, families, submissions,
                            cookies, log=None):
    target = args.email
    some_families = dict()

    keys = [ PDSChurch.pkey, PDSChurch.npkey ]

    log.info("Looking for email addresses: {e}".format(e=target))

    for fid, f in families.items():
        found = False

        for m in f['members']:
            for key in keys:
                for e in m[key]:
                    if type(target) is list:
                        for target_email in target:
                            if e['EMailAddress'] == target_email:
                                log.info("Found family for email address: {email}".format(email=target_email))
                                found = True
                                break
                    else:
                        if e['EMailAddress'] == target:
                            log.info("Found family for email address: {email}".format(email=target))
                            found = True
                            break

        if found:
            some_families[fid] = f

    return _send_family_emails(args.email_content, some_families, submissions,
                                cookies, log)

###########################################################################

def cookiedb_create(filename, log=None):
    cur = cookiedb_open(filename)
    query = ('CREATE TABLE cookies ('
             'cookie text primary key not null,'
             'uid not null,'
             'type integer not null,'
             'url text not null,'
             'creation_timestamp integer not null'
             ')')

    cur.execute(query)

    if log:
        log.debug("Initialized cookie db: {file}"
                  .format(file=filename))

    return cur

def cookiedb_open(filename, log=None):
    conn = sqlite3.connect(filename)
    cur = conn.cursor()

    if log:
        log.debug("Opened cookie db: {file}"
                  .format(file=filename))

    return cur

###########################################################################

def write_csv(family_list, filename, extra, log=None):
    csv_family_fields = {
        "parishKey"          : 'Envelope ID',
        "fid"                : 'FID',
        "household"          : 'Household names',
        'email'              : 'Email addresses',
        "previousPledge"     : '2020 total pledge',
        "soFarThisYear"      : 'CY2020 giving so far',
    }

    csv_extra_family_fields = {
        'Salulation'            : lambda fam: fam['MailingName'],
        'Street Address 1'      : lambda fam: fam['StreetAddress1'],
        'Street Address 2'      : lambda fam: fam['StreetAddress2'],
        'City/State'            : lambda fam: fam['city_state'],
        'Zip Code'              : lambda fam: fam['StreetZip'],
        'Send no mail'          : lambda fam: fam['SendNoMail'],
        'Num Family Members'    : lambda fam: len(fam['members']),
        'Reason email not sent' : lambda fam: fam['stewardship']['reason not sent'],
    }

    csv_member_fields = {
        "mid"                : 'MID',
        "name"               : 'Name',
    }

    fieldnames = list()

    # Add the fields from both forms
    fieldnames.extend(csv_family_fields.values())
    if extra:
        fieldnames.extend(csv_extra_family_fields.keys())
    fieldnames.extend(csv_member_fields.values())

    csv_fieldnames = fieldnames.copy()

    if log:
        log.info("Writing result CSV: {filename}"
                 .format(filename=filename))

    with open(filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_fieldnames)
        writer.writeheader()

        for family in family_list:
            row = dict()

            for ff, column in csv_family_fields.items():
                log.debug(f"Looking for: {ff}")
                for item in jotform.pre_fill_data['family']:
                    if item['fields'] == ff:
                        func = item['value_func']
                        value = func(family)

                        # The pledge values will have HTML-ized "%24" instead of "$".
                        if isinstance(value, str):
                            value = value.replace("%24", "$")

                        row[column] = value

            if extra:
                for column, func in csv_extra_family_fields.items():
                    row[column] = func(family)

            for member in family['members']:
                for mf, column in csv_member_fields.items():
                    log.debug(f"Looking for member item: {mf}")
                    for item in jotform.pre_fill_data['per_member']:
                        for field in item['fields']:
                            if field.startswith(mf):
                                func = item['value_func']
                                row[column] = func(member)

                log.debug(f"Writing row: {row}")
                writer.writerow(row)

###########################################################################

def setup_google(args, log):
    apis = {
        'drive' : { 'scope'       : Google.scopes['drive'],
                    'api_name'    : 'drive',
                    'api_version' : 'v3', },
    }
    services = GoogleAuth.service_oauth_login(apis,
                                              app_json=args.app_id,
                                              user_json=args.user_credentials,
                                              log=log)
    google = services['drive']

    #---------------------------------------------------------------------

    def _read_jotform_gsheet(google, gfile_id):
        response = google.files().export(fileId=gfile_id,
                                          mimeType=Google.mime_types['csv']).execute()

        # The ordering of these fields is critical, although the names are not
        fields = [
            'SubmitDate',
            'EnvId',
            'fid',
            # There are other fields in these spreadsheets, but we only care about
            # the 1st three
        ]

        csvreader = csv.DictReader(response.decode('utf-8').splitlines(),
                                   fieldnames=fields)
        return csvreader

    #---------------------------------------------------------------------
    # All we need are quick-lookup dictionaries to know if a given FID
    # has submitted or not.
    #
    # So convert the CSV data structures to a quick-lookup dictionary.
    def _convert(csv_data, log):
        output_data = dict()

        first = True
        for row in csv_data:
            # Skip the first / title row
            if first:
                first = False
                continue

            fid = row['fid']
            if fid:
                fid = int(fid)
            else:
                fid = 0
            output_data[fid] = True

        return output_data

    log.info("Loading Jotform submissions Google sheet")
    jotform_csv = _read_jotform_gsheet(google, jotform_gsheet_gfile_id)
    submissions = _convert(jotform_csv, log=log)

    return submissions

###########################################################################

def setup_args():
    # These options control which emails are sent.
    # You can only use one of these options at a time.
    group = tools.argparser.add_mutually_exclusive_group()
    group.add_argument('--all', action='store_true',
                        help='Send all emails')
    group.add_argument('--email',
                        action='append',
                        help='Send only to this email address')
    group.add_argument('--env-id-file',
                        help='Send only to families with envelope IDs in the file')
    group.add_argument('--unsubmitted',
                        action='store_true',
                        help='Send only to families who have not yet submitted all their data (i.e., all Members have submitted ministry, and a Family pledge has been recorded)')

    tools.argparser.add_argument('--do-not-send',
                                action='store_true',
                                help='If specified, do not actually send any emails, but do everything else')
    tools.argparser.add_argument('--email-content',
                                required=True,
                                help='File containing the templated content of the email to be sent')

    tools.argparser.add_argument('--smtp-auth-file',
                                 required=True,
                                 help='File containing SMTP AUTH username:password')

    # These options are for Google Authentication
    global gapp_id
    tools.argparser.add_argument('--app-id',
                                 default=gapp_id,
                                 help='Filename containing Google application credentials.  Only necessary if sending an email that contains a {*_reminder} tag.')
    global guser_cred_file
    tools.argparser.add_argument('--user-credentials',
                                 default=guser_cred_file,
                                 help='Filename containing Google user credentials.  Only necessary if sending an email that contains a {*_reminder} tag.')

    # These options control the generated cookie database
    tools.argparser.add_argument('--cookie-db', required=True,
                        help='Name of the SQLite3 database to output to')
    tools.argparser.add_argument('--append', action='store_true',
                        help='If specified, append to the existing SQLite3 database')

    args = tools.argparser.parse_args()

    # If a database already exists and --append was not specified, barf
    if os.path.exists(args.cookie_db) and not args.append:
        print("Error: database {db} already exists and --append was not specified"
              .format(db=args.cookie_db))
        print("Cowardly refusing to do anything")
        exit(1)

    # Need either --all or --email or --env-id-file or --ubsibmitted
    if (not args.all and not args.email and
        not args.env_id_file and not args.unsubmitted):
        print("Error: must specify either --all, --email, --env-id-file, or --unsubmitted")
        print("Cowardly refusing to do anything")
        exit(1)

    # Helper to check if a path exists
    def _check_path(filename):
        if not os.path.exists(filename):
            print("Error: file '{file}' is not readable"
                .format(file=filename))
            exit(1)

    # Check to make sure the env ID file is valid
    if args.env_id_file:
        _check_path(args.env_id_file)

    # Check to make sure the email content file is valid
    _check_path(args.email_content)

    # Read the email content
    with open(args.email_content, 'r') as f:
        args.email_content = f.read()

    # If the email content contains any of the "_reminder" tags, then check the
    # Google arguments, too.
    need_google = False
    if args.unsubmitted or re.search("_reminder[s]*}", args.email_content):
        need_google = True
        if (args.app_id is None or
            args.user_credentials is None):
            print("Error: email content file contains a *_reminder template, but not all of --app-id, --user-credentials were specified")
            exit(1)

        _check_path(args.app_id)
        _check_path(args.user_credentials)

    return args, need_google

###########################################################################

def main():
    global families, members

    # JMS Kinda yukky that "args" is global
    global args
    args, need_google = setup_args()

    logfilename = 'log.txt'
    try:
        os.unlink(logfilename)
    except:
        pass
    log = ECC.setup_logging(debug=False, logfile=logfilename)

    # We need Google if the email content contains a *_reminder template
    # (i.e., we need to login to Google and download some data)
    if need_google:
        submissions = setup_google(args, log=log)
    else:
        submissions = dict()

    # Read in all the PDS data
    log.info("Reading PDS data...")
    (pds, families,
     members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    parishioners_only=True,
                                                    log=log)

    # Open the cookies DB
    if not args.append or not os.path.exists(args.cookie_db):
        func = cookiedb_create
    else:
        func = cookiedb_open
    cookies = func(args.cookie_db)

    # Send the desired emails
    if args.all:
        func = send_all_family_emails
    elif args.env_id_file:
        func = send_file_family_emails
    elif args.unsubmitted:
        func = send_unsubmitted_family_emails
    else:
        func = send_some_family_emails

    sent, not_sent = func(args, families, submissions, cookies, log)

    # Record who/what we sent
    ts = datetime.datetime.now().strftime('%Y-%m-%d-%H%M%S')
    write_csv(sent,     f'emails-sent-{ts}.csv',     extra=False, log=log)
    write_csv(not_sent, f'emails-not-sent-{ts}.csv', extra=True,  log=log)

    # Close the databases
    cookies.connection.close()
    pds.connection.close()

# Need to make these global for the lambda functions
members = 1
families = 1

main()
