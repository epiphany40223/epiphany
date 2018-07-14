#!/usr/bin/env python3

import sys
sys.path.insert(0, '../../python')

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
import PDSChurch

from pprint import pprint
from pprint import pformat
from email.message import EmailMessage

# SMTP / email basics
smtp_server  = 'smtp-relay.gmail.com'
smtp_from    = '"Epiphany Catholic Church" <email-update@epiphanycatholicchurch.org>'
smtp_subject = 'Epiphany Parishioner Information Update'

family_base_url  = 'https://form.jotform.com/81854311884159'
member_base_url  = 'https://form.jotform.com/80584122392152'
general_base_url = 'https://form.jotform.com/81908017038153'

api_base_url = 'http://api.epiphanycatholicchurch.org/summer2018/?key='

# This is the fields in the above Forms.  It is highly specific to the
# above Form -- you won't be able to re-use the values!  Python lambda
# function FTW!
family_fields = {
    # Parish key / envelope number
    "parishKey"        : lambda fam: _pkey(fam['ParKey']),

    # Family ID
    "fid"              : lambda fam: fam['FamRecNum'],

    # This data last updated...
    "thisData"         : lambda fam: last_updated,

    # Are you still a parishioner?
    "areYou"           : lambda fam: "Yes",

    # Street address
    "streetAddress59"  : lambda fam: fam['StreetAddress1'],

    # Street address 2
    "streetAddress58"  : lambda fam: fam['StreetAddress2'],

    # City + State
    "cityState"        : lambda fam: fam['city_state'],

    # Zip
    "zipCode"          : lambda fam: fam['StreetZip'],

    # Other comments (not pulling from PDS)
    "doYou"            : lambda fam: None,
}

member_fields = {
    # Parish key / envelope number
    "parishKey"        : lambda mem: _pkey(mem['family']['ParKey']),

    # Member ID
    "mid"              : lambda mem: mem['MemRecNum'],

    # This data last updated...
    "thisData"         : lambda fam: last_updated,

    # Title
    "titleif"          : lambda mem: mem['prefix'],

    # First name
    "legalFirst26"     : lambda mem: mem['first'],

    # Nickname
    "nicknameonly"     : lambda mem: mem['nickname'],

    # Middle name
    "middleName"       : lambda mem: mem['middle'],

    # Last name
    "lastName5"        : lambda mem: mem['last'],

    # Suffix
    "suffixif"         : lambda mem: mem['suffix'],

    # Birth year
    "inWhat"           : lambda mem: mem['YearOfBirth'],

    # Preferred email
    "preferredEmail"   : lambda mem: PDSChurch.find_any_email(mem),

    # Marital status
    "maritalStatus"    : lambda mem: _mem_marital_status(mem),

    # Wedding date
    "weddingDate[day]" : lambda mem: _make_date(_mem_value('marriage_date', mem), 'day'),
    "weddingDate[month]" : lambda mem: _make_date(_mem_value('marriage_date', mem), 'month'),
    "weddingDate[year]" : lambda mem: _make_date(_mem_value('marriage_date', mem), 'year'),

    # Cell phone
    "cellPhone13"      : lambda mem: _mem_cell_phone(mem),

    # Occupation
    "occupation"       : lambda mem: _mem_value('occupation', mem),

    # Emergency contact name, relationship, phone
    # Not pulling from PDS
    "emergencyContact34" : lambda mem: None,
    "emergencyContact35" : lambda mem: None,
    "emergencyContact33" : lambda mem: None,

    # K-12 schools (not pulling from PDS)
    "schoolAttending"  : lambda mem: None,
}

general_fields = {
    # Parish key / envelope number
    "parishKey"        : lambda mem: _pkey(mem['family']['ParKey']),

    # Family ID
    "fid"              : lambda fam: fam['FamRecNum'],

    # Member ID
    "mid"              : lambda mem: mem['MemRecNum'],
}

##############################################################################

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

##############################################################################

def _make_url(base_url, fields, thing, cookies, log=None):
    url = base_url + "?"

    for html_id in fields:
        func = fields[html_id]
        value = func(thing)
        if value is not None:
            url += "&{id}={value}".format(id=html_id, value=value)

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

def make_family_form_url(member, cookies, log=None):
    return _make_url(family_base_url, family_fields, member, cookies, log)

def make_member_form_url(member, cookies, log=None):
    return _make_url(member_base_url, member_fields, member, cookies, log)

##############################################################################

def send_family_email(to_addresses, family, family_url, family_member_data,
                      log=None):
    # We won't get here unless there's at least one email address to
    # which to send.  But do a sanity check anyway.
    if len(to_addresses) == 0:
        return 0

    to_names = dict()
    member_links = ''
    for member_data in family_member_data:
        m    = member_data['member']
        name = m['email_name']
        url  = member_data['url']

        to_names[m['last']] = True

        member_links += ("<li><a href=\"{url}\">{name}</a></li>\n"
                         .format(url=url, name=name))

    smtp_to = ",".join(to_addresses)
    # JMS DEBUG
    #log.info("Sending to: {to} (JMS OVERRIDDEN)".format(to=smtp_to))
    #smtp_to = "Jeff Squyres <jsquyres@gmail.com>"

    if log:
        log.info("    Sending to Family {names} at {emails}"
                 .format(names=' / '.join(to_names), emails=smtp_to))

    general_url = ("{base}?envelope_id={parKey}&fid={fid}"
                   .format(base=general_base_url,
                           parKey=_pkey(family['ParKey']),
                           fid=family['FamRecNum']))

    message_body = ("""<html><body>
<p><img src="http://api.epiphanycatholicchurch.org/summer2018/ecc-update-your-parishioner-info-summer-2018.jpeg"</p>

<p>Dear {family_names} household:</p>

<p>As mentioned in the bulletin, we are initiating Epiphany's "Summer
Clean-Up of Our Church Records".  As Epiphany continues to plan for
the future, looks for ways to better serve our parishioners, and
provide critical and useful reporting to leadership, it is clear that
we require more complete and accurate records.</p>

<p>We are asking our parishioners to review what we currently have on
file for them and their family, to make any corrections, and also to
"fill-in-the-blanks" for us.  Our hope is that this will be an easy
and streamlined process, and we ask for your help with this very
important undertaking!  This email was only sent to parishioners who
Epiphany has on record as "head of household" and the corresponding
spouse / partner.</p>

<p><em>We realize that you may have received this email in error</em>.
Even if you no longer attend Epiphany, please take a moment to click
on the "home address" link below to indicate that you no longer attend,
or simply send an email to <a
href="mailto:mindy@epiphanycatholicchurch.org">Mindy Locke</a> in our
parish office.</p>

<p
style="font-variant:small-caps;font-weight:bold;font-size:large;color:red">Please
update <span style="text-decoration:underline">three</span> sets
of information for us:</p>

<ol>

<p><li><a href="{family_url}">Click here to update your home
address</a>.</li></p>

<p><li>Click each of the links below to update your household members:</li>
<ul>
{member_links}
</ul></li>

<p><li><a href="{general_form_url}">Click here if you have any other updates</a>, such as adding or removing household members.</li></p>
</ol>
</p>

<p><strong>NOTE:</strong> We are hoping to have the updates completed
by the end of August; <em>these links will only work until August 27,
2018</em>.  Should you have any questions, please contact either
myself or Mindy Locke, our Administrative Assistant, at +1
502-245-9733, extension 26.</p>

<p>Thanks again for your time in helping us update our records.</p>

<p>Sincerely,</p>

<p>Mary A. Downs<br />
<em>Business Manager</em><br />
Epiphany Catholic Church<br />
+1 502-245-9733 ext. 12</p></body></html>"""
                    .format(family_names=" / ".join(to_names),
                            family_url=family_url,
                            member_links=member_links,
                            general_form_url=general_url))

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

##############################################################################

def _want_to_email_member(m):
    if 'Head' in m['type'] or 'Spouse' in m['type']:
        return True
    else:
        return False

def _send_family_emails(families, cookies, log=None):
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
            if _want_to_email_member(m):
                em = PDSChurch.find_any_email(m)
                if em:
                    to_emails.append(em)

            if first:
                log.info("=== Family: {name}".format(name=f['Name']))
                first = False
                fam_url = make_family_form_url(f, cookies, log)
            log.info("    Member: {mem}".format(mem=m['Name']))

            mem_url = make_member_form_url(m, cookies, log)

            family_member_data.append({
                "member" : m,
                "url"    : mem_url,
            })

        family_data = {
            'family'             : f,
            'family_url'         : fam_url,
            'family_member_data' : family_member_data,

            'to_emails'          : to_emails,
        }

        if len(to_emails) > 0:
            send_count = send_family_email(to_emails, f, fam_url,
                                           family_member_data, log)
            email_sent.append(family_data)

        elif len(to_emails) == 0:
            if log:
                log.info("    *** Have no HoH/Spouse emails for Family {family}"
                         .format(family=f['Name']))
            email_not_sent.append(family_data)

    return email_sent, email_not_sent

##############################################################################

def send_all_family_emails(families, cookies, log=None):
    return _send_family_emails(families, cookies, log)

#-----------------------------------------------------------------------------

def send_some_family_emails(args, families, cookies, log=None):
    target = args.email
    some_families = dict()

    keys = [ PDSChurch.pkey, PDSChurch.npkey ]

    log.debug("Looking for email addresses: {e}".format(e=target))

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

    return _send_family_emails(some_families, cookies, log)

##############################################################################

def setup_args():
    parser = argparse.ArgumentParser(description='Send census update emails')
    parser.add_argument('--all', action='store_true',
                        help='Send all emails')
    parser.add_argument('--email',
                        action='append',
                        help='Send only to this email address')

    parser.add_argument('--cookie-db', required=True,
                        help='Name of the SQLite3 database to output to')
    parser.add_argument('--append', action='store_true',
                        help='If specified, append to the existing SQLite3 database')

    args = parser.parse_args()

    # If a database already exists and --append was not specified, barf
    if os.path.exists(args.cookie_db) and not args.append:
        print("Error: database {db} already exists and --append was not specified"
              .format(db=args.cookie_db))
        print("Cowardly refusing to do anything")
        exit(1)

    # Need either --all or --email
    if not args.all and not args.email:
        print("Error: must specify either --all or --email")
        print("Cowardly refusing to do anything")
        exit(1)

    return args

##############################################################################

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

##############################################################################

def write_csv(family_data, filename, log=None):
    csv_family_fields = {
        "parishKey"          : 'Envelope ID',
        "fid"                : 'FID',
        "streetAddress59"    : 'Street address 1',
        "streetAddress58"    : 'Street address 2',
        "cityState"          : 'City / State',
        "zipCode"            : 'Zip code',
    }

    csv_member_fields = {
        "mid"                : 'MID',
        "titleif"            : 'Title',
        "legalFirst26"       : 'Legal first name',
        "nicknameonly"       : 'Nickname',
        "middleName"         : 'Middle name',
        "lastName5"          : 'Last name',
        "suffixif"           : 'Suffix',

        "inWhat"             : 'Birth year',
        "preferredEmail"     : 'Preferred email',

        "maritalStatus"      : 'Marital status',
        "weddingDate[day]"   : 'Wedding day',
        "weddingDate[month]" : 'Wedding month',
        "weddingDate[year]"  : 'Wedding year',

        "cellPhone13"        : 'Cell phone',

        "occupation"         : 'Occupation',
    }

    fieldnames = list()
    # This field is not in either of the forms
    fieldnames.append('Member type')

    # Add the fields from both forms
    for _, name in csv_family_fields.items():
        fieldnames.append(name)
    for _, name in csv_member_fields.items():
        fieldnames.append(name)

    if log:
        log.info("Writing result CSV: {filename}"
                 .format(filename=filename))

    with open(filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames,
                                quoting=csv.QUOTE_ALL)
        writer.writeheader()

        for fentry in family_data:
            row = {}

            family             = fentry['family']
            family_member_data = fentry['family_member_data']

            for ff, cff in csv_family_fields.items():
                func = family_fields[ff]
                row[cff] = func(family)

            for fmd in family_member_data:
                member = fmd['member']

                row['Member type'] = member['type']

                for mf, cmf in csv_member_fields.items():
                    func = member_fields[mf]
                    row[cmf] = func(member)

                writer.writerow(row)

##############################################################################

def main():
    global families, members

    args = setup_args()

    log = ECC.setup_logging(debug=True)

    (pds, families,
     members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    log=log)


    for _, m in members.items():
        if 'Squyres,Jeff' in m['Name']:
            log.debug("**** DEBUG: Jeff Squyres member")
            log.debug(pformat(m))

    # Open the cookies DB
    if not args.append or not os.path.exists(args.cookie_db):
        fn = cookiedb_create
    else:
        fn = cookiedb_open
    cookies = fn(args.cookie_db)

    # Send the emails
    if args.all:
        sent, not_sent = send_all_family_emails(families, cookies, log)
    else:
        sent, not_sent = send_some_family_emails(args, families, cookies, log)

    # Record who/what we sent

    ts = datetime.datetime.now().strftime('%Y-%m-%d-%H%M%S')
    write_csv(sent,     'emails-sent-{ts}.csv'.format(ts=ts),     log=log)
    write_csv(not_sent, 'emails-not-sent-{ts}.csv'.format(ts=ts), log=log)

    # Close the databases
    cookies.connection.close()
    pds.connection.close

# Need to make these global for the lambda functions
members = 1
families = 1

last_updated = datetime.datetime.now().strftime('%A %B %d, %Y at %I:%M%p')

main()
