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

from constants import gapp_id
from constants import guser_cred_file
from constants import jotform_gfile_id

from constants import title

from constants import smtp_server
from constants import smtp_from

from constants import email_image_url
from constants import api_base_url
from constants import jotform_base_url

from constants import jotform_household_fields
from constants import jotform_household_functions
from constants import jotform_member_fields
from constants import jotform_member_functions

from constants import already_submitted_fam_status

smtp_subject = 'Epiphany ' + title

#--------------------------------------------------------------------------

# JMS Kinda yukky that "args" is global
args = None

###########################################################################

def _pkey(env_id):
    return "' {0}".format(str(env_id).strip())

def _mem_value(key, m):
    if key in m:
        return m[key]
    else:
        return None

def _mem_marital_status(mem):
    value = _mem_value('marital_status', mem)
    if value:
        return value
    else:
        return 'Single'

def _mem_cell_phone(mem):
    if 'phones' not in mem:
        return ''

    # Be deterministic in ordering
    pids = sorted(mem['phones'])
    for pid in pids:
        phone = mem['phones'][pid]
        if phone['type'] == 'Cell':
            return phone['number']

    return ''

# PDS dates are yyyy-mm-dd; Jotform breaks this into 3 fields
def _make_date(val, key):
    if not val:
        return None

    result = re.match('(\d{4})-(\d{2})-(\d{2})', val)
    year   = result.group(1)
    month  = result.group(2)
    day    = result.group(3)

    dates = {
        'month' : month,
        'day'   : day,
        'year'  : year,
    }
    return dates[key]

###########################################################################

def _make_url(base_url, household_fields, household_functions,
              member_fields, member_functions,
              data, cookies, suffix=None, log=None):

    def _add_fields(url, member, fields, functions):
        for index, jotform_field in fields.items():
            func  = functions[index]
            value = func(member)
            if value is not None and value != '':
                url += f"&{jotform_field}={value}"
        return url

    #----------------------------------------------------------------------

    url = base_url + "?"
    url = _add_fields(url, data, household_fields, household_functions)

    # Neutral field names
    fields = member_functions.keys()

    for member, fields in zip(data['family']['members'], member_fields):
        url = _add_fields(url, member, fields, member_functions)

    if suffix:
        url += '&' + suffix

    # Insert the URL in the cookies database
    cookie      = uuid.uuid4()
    url_escaped = url.replace("'", "''")
    fid         = data['family']['FamRecNum']
    ts          = int(calendar.timegm(time.gmtime()))
    query       = ("INSERT INTO cookies "
                   "(cookie,fid,url,creation_timestamp) "
                   f"VALUES ('{cookie}','{fid}','{url_escaped}',{ts});")
    log.info(query)
    cookies.execute(query)

    # Write the cookie to the DB immediately (in case someone is
    # reading/copying the sqlite3 database behind the scenes).
    cookies.connection.commit()

    if log:
        log.debug("URL is: {}".format(url))
        log.debug("SQL query: {}".format(query))

    return '{url}{cookie}'.format(url=api_base_url, cookie=cookie)

#--------------------------------------------------------------------------

def make_census_url(family, to_names, to_emails, cookies, log):

    # Separate the city and state from the Family address
    city   = ''
    state  = ''
    if 'city_state' in family:
        tokens = family['city_state'].split(',')
        if len(tokens) == 1:
            tokens = family['city_state'].split(' ')
        if len(tokens) > 1:
            city  = tokens[0].strip()
            state = tokens[1].strip()

    # Separate land line phone number into area code and phone number
    area_code = ''
    phone     = ''
    if 'phones' in family:
        for ph in family['phones']:
            if ph['type'] == 'Home':
                match = re.search("\((\d\d\d)\) (\d\d\d-\d\d\d\d)",
                                ph['number'])
                if match:
                    area_code = match.group(1)
                    phone     = match.group(2)

    #-------------------------------------------------------------

    data = {
        'family' : family,
        'calc'   : {
            'to_names'       : ' / '.join(sorted(to_names)),
            'to_emails'      : ','.join(sorted(to_emails)),
            'city'           : city,
            'state'          : state,
            'landline-area'  : area_code,
            'landline-phone' : phone,
        },
    }

    return _make_url(jotform_base_url,
                     jotform_household_fields,
                     jotform_household_functions,
                     jotform_member_fields,
                     jotform_member_functions,
                     data, cookies,
                     suffix=None, log=log)

#--------------------------------------------------------------------------

def send_family_email(message_body, to_addresses,
                      to_names, family, log=None):

    # We won't get here unless there's at least one email address to
    # which to send.  But do a sanity check anyway.
    if len(to_addresses) == 0:
        return 0

    #---------------------------------------------------------------------

    smtp_to = ",".join(to_addresses)

    #---------------------------------------------------------------------
    # JMS DEBUG
    was = smtp_to
    smtp_to = "Jeff Squyres <jsquyres@gmail.com>"
    log.info("Sending to (OVERRIDE): {to} (was {was})".format(to=smtp_to, was=was))
    #---------------------------------------------------------------------

    if log:
        log.info("    Sending to Family {names} at {emails}"
                 .format(names=' / '.join(to_names), emails=smtp_to))

    # JMS kinda yukky that "args" is global
    global args
    if args.do_not_send:
        log.info("NOT SENDING EMAIL (--do-not-send)")
    else:
        try:
            with smtplib.SMTP_SSL(host=smtp_server) as smtp:
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

    return len(to_addresses)

###########################################################################

def make_message_body(template, family, to_names, census_url):
    # Make a sorted list of last names in this Family

    # Note: we can't use the normal string.format() to substitute in
    # values because the HTML/CSS includes a bunch of instances of {}.
    message_body = template
    message_body = message_body.replace("{img}", email_image_url)
    message_body = message_body.replace("{family_names}", " / ".join(sorted(to_names)))
    message_body = message_body.replace("{census_url}", census_url)

    return message_body

###########################################################################

def _send_family_emails(template_message_body, families,
                        census_submissions,
                        cookies, log=None):
    # Send one email to the head-of-household + spouse in each family
    # in the dictionary.  Send them in fid order so that if we get
    # interrupted and have to start again, we can do so
    # deterministically.

    email_sent = list()
    email_not_sent = list()

    fids = sorted(families)
    for fid in fids:
        f = families[fid]

        log.info("=== Family: {name}".format(name=f['Name']))

        # Some families have too many members, and we can't make a URL for them.
        # Sorry Charlie.
        if len(f['members']) > len(jotform_member_fields):
            log.error(f"Too many Members in Family {f['Name']}")
            log.error("SKIPPED!")
            continue

        to_names  = dict()
        to_emails = list()
        for m in f['members']:
            to_names[m['last']] = True
            if helpers.member_is_hoh_or_spouse(m):
                em = PDSChurch.find_any_email(m)
                to_emails.extend(em)

        if len(to_emails) > 0:
            census_url   = make_census_url(f, to_names, to_emails, cookies, log)
            message_body = make_message_body(template_message_body, f,
                                            to_names, census_url)
            send_count   = send_family_email(message_body,
                                           to_emails, to_names,
                                           f, log=log)

            email_sent.append({
                'family'     : f,
                'census_url' : census_url,
                'to_names'   : to_names,
                'to_emails'  : to_emails,
            })

        elif len(to_emails) == 0:
            if log:
                log.info("    *** Have no HoH/Spouse emails for Family {family}"
                         .format(family=f['Name']))
            email_not_sent.append({
                'family'     : f,
                'census_url' : '',
                'to_names'   : to_names,
                'to_email'   : ''
            })

    return email_sent, email_not_sent

###########################################################################

def send_all_family_emails(args, families,
                            census_submissions,
                            cookies, log=None):
    return _send_family_emails(args.email_content,
                               families, census_submissions,
                               cookies, log)

#--------------------------------------------------------------------------

def send_file_family_emails(args, families,
                            census_submissions,
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

    return _send_family_emails(args.email_content, some_families,
                                census_submissions, cookies, log)

#--------------------------------------------------------------------------

def send_unsubmitted_family_emails(args, families,
                            census_submissions,
                            cookies, log=None):
    # Find all families that have not yet submitted.
    #
    # Then also remove any Family that has "2020 Census" set as their Family status.  This means that someone manually put this keyword on the
    # Family, probably indicating that they have submitted their stewardship
    # data on paper.

    log.info("Looking for Families with incomplete submissions...")
    some_families = dict()
    for fid, f in families.items():
        want = False

        if fid not in census_submissions:
            log.info("Family {n} (fid {fid}) not in submissions"
                    .format(n=f['Name'], fid=fid))
            want = True

        # This keyword trumps everything: if it is set on the Family, they do not get a reminder email.
        if 'status' in f and f['status'] == already_submitted_fam_status:
            want = False

        if want:
            log.info("Unsubmitted family (fid {fid}): {n}"
                    .format(n=f['Name'], fid=fid))
            some_families[fid] = f
        else:
            log.info("Compleded family (fid {fid}): {n} -- skipping"
                    .format(n=f['Name'], fid=fid))

    return _send_family_emails(args.email_content, some_families,
                                census_submissions, cookies, log)

#--------------------------------------------------------------------------

def send_some_family_emails(args, families,
                            census_submissions,
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

    return _send_family_emails(args.email_content, some_families,
                                census_submissions, cookies, log)

###########################################################################

def cookiedb_create(filename, log=None):
    cur = cookiedb_open(filename)
    query = ('CREATE TABLE cookies ('
             'cookie text primary key not null,'
             'fid not null,'
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

def write_csv(data, filename, log=None):
    fields = {
        'Envelope ID'     : lambda data: "'" + str(data['family']['ParKey'].strip()),
        'FID'             : lambda data: data['family']['FamRecNum'],
        'Household names' : lambda data: ' / '.join(data['to_names']) if 'to_names' in data else '',
        'Emails'          : lambda data: ', '.join(data['to_emails']) if 'to_emails' in data else '',
    }

    if log:
        log.info("Writing result CSV: {filename}"
                 .format(filename=filename))

    with open(filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields,
                                quoting=csv.QUOTE_ALL)
        writer.writeheader()

        for entry in data:
            row = dict()

            for field in fields:
                func       = fields[field]
                value      = func(entry)
                row[field] = value

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
            'parishioner',
            'email_reply',
            'fid',
            'jotform_id',
            # There are other fields in these spreadsheets, but we only care about
            # the 1st three
        ]

        csvreader = csv.DictReader(response.decode('utf-8').splitlines(),
                                   fieldnames=fields)
        return csvreader

    log.info("Loading census Google submissions spreadsheet")
    jotform_csv = _read_jotform_gsheet(google, jotform_gfile_id)

    #---------------------------------------------------------------------
    # All we need are quick-lookup dictionaries to know if:
    #
    # - A given Family FID (FID) has submitted
    #
    # So convert the CSV data structure to thus quick-lookup dictionary.
    def _convert(csv_data, log):
        output_data = dict()

        first = True
        for row in csv_data:
            # Skip the first / title row
            if first:
                first = False
                continue

            id = int(row['fid'])
            output_data[id] = True

        return output_data

    census_submissions = _convert(jotform_csv, log=log)

    return census_submissions

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

    log = ECC.setup_logging(debug=False)

    # We need Google if the email content contains a *_reminder template
    # (i.e., we need to login to Google and download some data)
    if need_google:
        census_submissions = setup_google(args, log=log)
    else:
        census_submissions = dict()

    # Read in all the PDS data
    log.info("Reading PDS data...")
    (pds, families,
     members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    log=log)

    # Remove non-parishioner families
    families = helpers.filter_parishioner_families_only(families, log=log)

    # Open the cookies DB
    if not args.append or not os.path.exists(args.cookie_db):
        fn = cookiedb_create
    else:
        fn = cookiedb_open
    cookies = fn(args.cookie_db)

    # Send the desired emails
    if args.all:
        func = send_all_family_emails
    elif args.env_id_file:
        func = send_file_family_emails
    elif args.unsubmitted:
        func = send_unsubmitted_family_emails
    else:
        func = send_some_family_emails

    sent, not_sent = func(args, families, census_submissions,
                        cookies, log)

    # Record who/what we sent
    ts = datetime.datetime.now().strftime('%Y-%m-%d-%H%M%S')
    write_csv(sent,     'emails-sent-{ts}.csv'.format(ts=ts),     log=log)
    write_csv(not_sent, 'emails-not-sent-{ts}.csv'.format(ts=ts), log=log)

    # Close the databases
    cookies.connection.close()
    pds.connection.close()

# Need to make these global for the lambda functions
members = 1
families = 1

last_updated = datetime.datetime.now().strftime('%A %B %d, %Y at %I:%M%p')

main()
