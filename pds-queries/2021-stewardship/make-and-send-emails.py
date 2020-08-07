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

from constants import jotform_member_ministries
from constants import already_submitted_fam_status

from constants import gapp_id
from constants import guser_cred_file
from constants import jotform_member_gfile_id
from constants import jotform_family_gfile_id

from constants import title

from constants import smtp_server
from constants import smtp_from

smtp_subject = 'Epiphany ' + title

from constants import email_image_url
from constants import api_base_url

#--------------------------------------------------------------------------

# JMS Kinda yukky that "args" is global
args = None

#--------------------------------------------------------------------------

def _escape(s):
    ret = s.replace('\"', '\\"')
    return ret

# These fields are in the highly specific to the Jotform!
family_form_url = 'https://form.jotform.com/91945543203153'
family_fields = {
    # Parish key / envelope number
    "parishKey"        : lambda fam: _pkey(fam['ParKey']),

    # Member ID
    "fid"              : lambda fam: fam['FamRecNum'],

    # Family name
    "names"            : lambda fam: fam['calculated']['household_name'] if 'calculated' in fam else fam['MailingName'],

    # Family annual pledge for 2019
    # "%24" is "$"
    "forYour"          : lambda fam: "%24{val}".format(val=fam['calculated']['pledged']) if 'calculated' in fam else "%240",

    # Family contributed so far in CY2019
    # "%24" is "$"
    "forYour83"        : lambda fam: "%24{val}".format(val=fam['calculated']['contributed']) if 'calculated' in fam else "%240",
}

# These fields are in the highly specific to the Jotform!
member_form_url = 'https://form.jotform.com/91944902477164'
member_fields = {
    # Parish key / envelope number
    "parishKey"        : lambda mem: _pkey(mem['family']['ParKey']),

    # Member ID
    "mid"              : lambda mem: mem['MemRecNum'],

    # Name
    "name"             : lambda mem: _escape(mem['full_name']),

    # This data last updated...
    "thisData"         : lambda fam: last_updated,
}

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

def _make_url(base_url, fields, thing, cookies, suffix=None, log=None):
    url = base_url + "?"

    for html_id in fields:
        func = fields[html_id]
        value = func(thing)
        if value is not None:
            url += "&{id}={value}".format(id=html_id, value=value)

    if suffix:
        url += '&' + suffix

    # Is this a family or a member?
    key = 'MemRecNum'
    if key in thing:
        uid = 'm{mid}'.format(mid=thing[key])
    else:
        uid = 'f{fid}'.format(fid=thing['FamRecNum'])

    # Insert the URL in the cookies database
    cookie = uuid.uuid4()
    url_escaped = url.replace("'", "''")
    query = ("INSERT INTO cookies "
             "(cookie,uid,url,creation_timestamp) "
             "VALUES ('{cookie}','{uid}','{url}',{ts});"
             .format(cookie=cookie, uid=uid, url=url_escaped,
                     ts=int(calendar.timegm(time.gmtime()))))
    cookies.execute(query)

    # Write the cookie to the DB immediately (in case someone is
    # reading/copying the sqlite3 database behind the scenes).
    cookies.connection.commit()

    if log:
        log.debug("URL is: {}".format(url))
        log.debug("SQL query: {}".format(query))

    return '{url}{cookie}'.format(url=api_base_url, cookie=cookie)

def calculate_family_values(family, year):

    #-----------------------------------------------------

    if 'funds' in family and year in family['funds']:
        funds = family['funds'][year]
    else:
        funds = dict()

    # Calculate 3 values:
    # 1. Pledge amount for CY2019
    # 2. Total amount given in CY2019 so far
    # 3. Family names
    pledged = 0
    for fund in funds.values():
        fund_rate = fund['fund_rate']
        if fund_rate:
            pledged += int(fund_rate['FDTotal'])

    contributed = 0
    for fund in funds.values():
        for item in fund['history']:
            contributed += item['item']['FEAmt']

    family['calculated'] = {
        "pledged"        : pledged,
        "contributed"    : contributed,
        "household_name" : helpers.household_name(family),
    }

def make_family_form_url(family, cookies, log=None):
    # Calculate the family values if they have not already done so
    if 'calculated' not in family:
        calculate_family_values(family, year='19')

    return _make_url(family_form_url, family_fields, family, cookies, log=log)

#
# Make a pre-filled URL for the matrix of ministries.
#
# The list of PDS ministries corresponding to the rows in the Jotform
# matrix are in jotform_member_ministries.  We pre-fill values of this
# URL via FIELDNAME[row][col]=true for any radio button that we want
# to be active (only one radio button can be active for any given
# row).  The columns are:
#
# 0: I am already involved
# 1: Yes, please contact me about becoming involved
# 2: I do not wish to be involved
def _make_ministries_url(member):
    def _check(ministry, member):
        for member_ministry in member['active_ministries']:
            if ministry == member_ministry['Description']:
                return True
        return False

    #-----------------------------------------------------------------------

    url = ''

    col_am_involved  = 0
    col_not_involved = 2

    for base_field in jotform_member_ministries:
        for row, ministry in enumerate(jotform_member_ministries[base_field]):
            column = col_not_involved

            match = False
            if type(ministry) is list:
                for m in ministry:
                    match = _check(ministry, member)
                    if match:
                        break
            else:
                match = _check(ministry, member)

            if match:
                column = col_am_involved

            url += ("&{field}[{row}][{col}]=true"
                    .format(field=base_field,
                            row=row,
                            col=column))

    return url

def make_member_form_url(member, cookies, log=None):
    suffix = _make_ministries_url(member)
    return _make_url(member_form_url, member_fields, member, cookies,
                     suffix=suffix, log=log)

#--------------------------------------------------------------------------

def member_name_and_age(member):
    name = member['email_name']
    if member['YearOfBirth'] > 0:
        birthday = datetime.datetime.strptime(member['DateOfBirth'], "%Y-%m-%d")
        now = datetime.datetime.now()
        delta = now - birthday

        # This is an approximation, because timedelta doesn't express in years (!)
        age = int(abs(delta.days / 365))
        name += ' (age {age})'.format(age=age)

    return name

def member_name_and_occupation(member):
    name = member['email_name']
    key = 'occupation'
    if key in member and member[key] != '':
        name += ' ({value})'.format(value=member[key])

    return name

def member_name_and_type(member):
    name = member['email_name']
    key = 'type'
    if key in member and member[key] != '':
        name += ' ({value})'.format(value=member[key])

    return name

def family_member_unique_names(family_member_data, value_func):
    family_members = dict()
    for member_data in family_member_data:
        # Get the name for this Family Member
        name = value_func(member_data['member'])

        # If we found a duplicate, abort
        if name in family_members:
            return None

        # Otherwise, save this name
        family_members[name] = member_data

    return family_members

def send_family_email(message_body, to_addresses,
                      family, family_pledge_url, family_member_data,
                      ministry_submissions, pledge_submissions,
                      log=None):
    # We won't get here unless there's at least one email address to
    # which to send.  But do a sanity check anyway.
    if len(to_addresses) == 0:
        return 0

    regular_style = 'style="font-size: 16px; color: rgb(0, 112, 192);"'
    red_style     = 'style="font-size: 16px; color: rgb(255, 0, 0); font-style: italic; font-weight: bold;"'

    #---------------------------------------------------------------------
    # Make a sorted list of member names in the family
    # Some families have multiple Members with the same name!
    family_members = family_member_unique_names(family_member_data,
            lambda member: member['email_name'])
    if family_members is None:
        family_members = family_member_unique_names(family_member_data,
                lambda member: member['full_name'])
    if family_members is None:
        family_members = family_member_unique_names(family_member_data,
                member_name_and_age)
    if family_members is None:
        family_members = family_member_unique_names(family_member_data,
                member_name_and_occupation)
    if family_members is None:
        family_members = family_member_unique_names(family_member_data,
                member_name_and_type)
    if family_members is None:
        log.error("Could not generate unique names for Family {f} (fid {fid})"
                    .format(f=family['Name'], fid=f['FamRecNum']))
        return 0

    # Make the individual family member <LI> HTML items
    to_names = dict()
    member_links = ''
    member_links_reminders = ''

    for name in sorted(family_members):
        member_data = family_members[name]
        m           = member_data['member']
        url         = member_data['url']

        to_names[m['last']] = True

        # This HTML/CSS format taken from Jordan's email source code
        member_links += ('<li {style}><span {style}><a href="{url}">{name}</a></span></li>'
                         .format(url=url, name=name, style=regular_style))

        # Has this one already been submitted?
        log.debug("Making member link for MID {mid}; ministry submissions"
                    .format(mid=m['MemRecNum']))
        if m['MemRecNum'] in ministry_submissions:
            additional = ('<span {style}>(already submitted)</span>'
                            .format(style=regular_style))
        else:
            additional = ('<span {style}>(not yet submitted)</span>'
                            .format(style=red_style))

        member_links_reminders += ('<li {style}><span {style}><a href="{url}">{name}</a></span> {additional}</li>'
                                .format(url=url, name=name, style=regular_style,
                                        additional=additional))

    #---------------------------------------------------------------------
    # Make the Family pledge link
    # (base it off the last Member we traversed in the loop above -- they're all
    # in the same Family, so this is ok)
    family_pledge_link = ('<a href="{url}">2020 Financial Stewardship Covenant</a>'
                        .format(url=family_pledge_url))
    fid = m['FamRecNum']
    if fid in pledge_submissions:
        additional = ('<span {style}>(already submitted)</span>'
                        .format(style=regular_style))
    else:
        additional = ('<span {style}>(not yet submitted)</span>'
                        .format(style=red_style))
    family_pledge_link_reminder = ('<a href="{url}">2020 Financial Stewardship Covenant</a><br>{additional}'
                                    .format(url=family_pledge_url,
                                    additional=additional))

    smtp_to = ",".join(to_addresses)

    #---------------------------------------------------------------------
    # JMS DEBUG
    #was = smtp_to
    #smtp_to = "Jeff Squyres <jsquyres@gmail.com>"
    #log.info("Sending to (OVERRIDE): {to} (was {was})".format(to=smtp_to, was=was))
    #---------------------------------------------------------------------

    if log:
        log.info("    Sending to Family {names} at {emails}"
                 .format(names=' / '.join(to_names), emails=smtp_to))

    # Note: we can't use the normal string.format() to substitute in
    # values because the HTML/CSS includes a bunch of instances of {}.
    #message_body = message_initial()
    message_body = message_body.replace("{img}", email_image_url)
    message_body = message_body.replace("{family_names}", " / ".join(to_names))
    message_body = message_body.replace("{family_pledge_link}", family_pledge_link)
    message_body = message_body.replace("{family_pledge_link_reminder}", family_pledge_link_reminder)
    message_body = message_body.replace("{member_links}", member_links)
    message_body = message_body.replace("{member_links_reminders}", member_links_reminders)

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
            log.error("==== Error with {email}"
                      .format(email=smtp_to))
            log.error(traceback.format_exc())

    return len(to_addresses)

###########################################################################

def _send_family_emails(message_body, families,
                        ministry_submissions, pledge_submissions,
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
        first = True

        to_emails = list()
        family_member_data = list()
        for m in f['members']:
            if helpers.member_is_hoh_or_spouse(m):
                em = PDSChurch.find_any_email(m)
                to_emails.extend(em)

            if first:
                log.info("=== Family: {name}".format(name=f['Name']))
                first = False
                fam_pledge_url = make_family_form_url(f, cookies, log)
            log.info("    Member: {mem}".format(mem=m['Name']))

            mem_url = make_member_form_url(m, cookies, log)

            family_member_data.append({
                "member" : m,
                "url"    : mem_url,
            })

        family_data = {
            'family'             : f,
            'family_pledge_url'  : fam_pledge_url,
            'family_member_data' : family_member_data,

            'to_emails'          : to_emails,
        }

        if len(to_emails) > 0:
            send_count = send_family_email(message_body,
                                           to_emails, f, fam_pledge_url,
                                           family_member_data,
                                           ministry_submissions,
                                           pledge_submissions,
                                           log=log)
            email_sent.append(family_data)

        elif len(to_emails) == 0:
            if log:
                log.info("    *** Have no HoH/Spouse emails for Family {family}"
                         .format(family=f['Name']))
            email_not_sent.append(family_data)

    return email_sent, email_not_sent

###########################################################################

def send_all_family_emails(args, families,
                            ministry_submissions, pledge_submissions,
                            cookies, log=None):
    return _send_family_emails(args.email_content,
                               families, ministry_submissions,
                               pledge_submissions, cookies, log)

#--------------------------------------------------------------------------

def send_file_family_emails(args, families,
                            ministry_submissions, pledge_submissions,
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

    return _send_family_emails(args.email_content, some_families, ministry_submissions,
                                pledge_submissions, cookies, log)

#--------------------------------------------------------------------------

def send_unsubmitted_family_emails(args, families,
                            ministry_submissions, pledge_submissions,
                            cookies, log=None):
    # Find all families that have not *completely* submitted everything.
    # I.e., any family that has not yet submitted:
    # - all Family Member ministry forms
    # - a Family pledge form
    #
    # Then also remove any Family that has "2020 Stewardship" set as their Family status.  This means that someone manually put this keyword on the
    # Family, probably indicating that they have submitted their stewardship
    # data on paper.

    log.info("Looking for Families with incomplete submissions...")
    some_families = dict()
    for fid, f in families.items():
        want = False

        if fid not in pledge_submissions:
            log.info("Family {n} (fid {fid}) not in pledges"
                    .format(n=f['Name'], fid=fid))
            want = True

        for m in f['members']:
            mid = m['MemRecNum']
            if mid not in ministry_submissions:
                log.info("Member {mm} (mid: {mid}) of family {n} (fid {fid}) not in ministry"
                        .format(mm=m['email_name'], mid=mid, n=f['Name'], fid=fid))
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

    return _send_family_emails(args.email_content, some_families, ministry_submissions,
                                pledge_submissions, cookies, log)

#--------------------------------------------------------------------------

def send_some_family_emails(args, families,
                            ministry_submissions, pledge_submissions,
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

    return _send_family_emails(args.email_content, some_families, ministry_submissions,
                                pledge_submissions, cookies, log)

###########################################################################

def cookiedb_create(filename, log=None):
    cur = cookiedb_open(filename)
    query = ('CREATE TABLE cookies ('
             'cookie text primary key not null,'
             'uid not null,'
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

def write_csv(family_data, filename, log=None):
    csv_family_fields = {
        "parishKey"          : 'Envelope ID',
        "fid"                : 'FID',
        "names"              : 'Household names',
        "forYour"            : '2019 total pledge',
        "forYour83"          : 'CY2019 giving so far',
    }

    csv_member_fields = {
        "parishKey"          : 'Envelope ID',
        "mid"                : 'MID',
        "name"               : 'Name',
        "thisData"           : "This data last updated",
    }

    fieldnames = list()
    # This field is not in either of the forms
    fieldnames.append('Member type')

    # Add the fields from both forms
    fieldnames.extend(csv_family_fields.values())
    fieldnames.extend(csv_member_fields.values())

    csv_fieldnames = fieldnames.copy()
    csv_fieldnames.append("Saluation")
    csv_fieldnames.append("Street1")
    csv_fieldnames.append("Street2")
    csv_fieldnames.append("CityState")
    csv_fieldnames.append("Zip")

    if log:
        log.info("Writing result CSV: {filename}"
                 .format(filename=filename))

    with open(filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_fieldnames,
                                quoting=csv.QUOTE_ALL)
        writer.writeheader()

        for fentry in family_data:
            row = dict()

            family             = fentry['family']
            family_member_data = fentry['family_member_data']

            for ff, cff in csv_family_fields.items():
                func = family_fields[ff]
                value = func(family)

                # The pledge values will have HTML-ized "%24" instead of "$".
                if isinstance(value, str):
                    value = value.replace("%24", "$")

                row[cff] = value

            # Add in mailing label values
            if 'MailingName' in family:
                row['Saluation'] = family['MailingName']
            if 'StreetAddress1' in family:
                row['Street1'] = family['StreetAddress1']
            if 'StreetAddress2' in family:
                row['Street2'] = family['StreetAddress2']
            if 'city_state' in family:
                row['CityState'] = family['city_state']
            if 'StreetZip' in family:
                row['Zip'] = family['StreetZip']

            for fmd in family_member_data:
                member = fmd['member']

                row['Member type'] = member['type']

                for mf, cmf in csv_member_fields.items():
                    func = member_fields[mf]
                    row[cmf] = func(member)

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
            'id',
            # There are other fields in these spreadsheets, but we only care about
            # the 1st three
        ]

        csvreader = csv.DictReader(response.decode('utf-8').splitlines(),
                                   fieldnames=fields)
        return csvreader

    log.info("Loading ministry Google ministry submissions spreadsheet")
    jotform_ministry_csv = _read_jotform_gsheet(google, jotform_member_gfile_id)
    log.info("Loading ministry Google pledge submissions spreadsheet")
    jotform_pledge_csv = _read_jotform_gsheet(google, jotform_family_gfile_id)

    #---------------------------------------------------------------------
    # All we need are quick-lookup dictionaries to know if:
    #
    # - A given Member ID (MID) has submitted a ministry form
    # - A given Family FID (FID) has submitted a pledge form
    #
    # So convert the two CSV data structures to these quick-lookup dictionaries.
    def _convert(csv_data, log):
        output_data = dict()

        first = True
        for row in csv_data:
            # Skip the first / title row
            if first:
                first = False
                continue

            id = int(row['id'])
            output_data[id] = True

        return output_data

    ministry_submissions = _convert(jotform_ministry_csv, log=log)
    pledge_submissions = _convert(jotform_pledge_csv, log=log)

    return ministry_submissions, pledge_submissions

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

    log = ECC.setup_logging(debug=True)

    # We need Google if the email content contains a *_reminder template
    # (i.e., we need to login to Google and download some data)
    if need_google:
        ministry_submissions, pledge_submissions = setup_google(args, log=log)
    else:
        ministry_submissions = dict()
        pledge_submissions = dict()

    # Read in all the PDS data
    log.info("Reading PDS data...")
    (pds, families,
     members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    log=log)

    # Remove non-parishioner families
    families = helpers.filter_parishioner_families_only(families)

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

    sent, not_sent = func(args, families, ministry_submissions,
                        pledge_submissions, cookies, log)

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
