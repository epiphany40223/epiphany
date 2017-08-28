#!/usr/bin/env python3

import smtplib
import csv
import re

from email.message import EmailMessage

base_url = 'https://form.jotform.us/72278254038156?'

smtp_server = 'smtp-relay.gmail.com'
smtp_from = 'no-reply@epiphanycatholicchurch.org'
smtp_subject = 'Update your email address at Epiphany Catholic Church'

name_order = re.compile('^([^,]+),(.+)$')
name_squash1 = re.compile('\(.+\)')
name_squash2 = re.compile('\{.+\}')

filename = 'members-gt13-email-update-form.csv'
with open(filename, 'r', newline='') as csvfile:
    fieldnames = ['ParKey', 'Member Name', 'PreferredEmail',
                  'OtherEmail1', 'OtherEmail2', 'OtherEmail3',
                  'OtherEmail4', 'OtherEmail5' ]
    reader = csv.DictReader(csvfile, fieldnames=fieldnames)
    first = True
    for row in reader:
        # Skip first row -- it's the headers
        if first:
            first = False
            continue

        # Fix a few things with names
        name = row['Member Name']

        # Remove all (foo) and {foo}
        name = name_squash1.sub('', name)
        name = name_squash2.sub('', name)

        # Some names are "Last,First".  Change that to "First Last"
        m = name_order.match(name)
        if m:
            name = "{first} {last}".format(first=m.group(2), last=m.group(1))

        print("Sending to: {name} at {email}"
              .format(name=name, email=row['PreferredEmail']))

        url = ("{base}"
               "familyIdenvelope={parkey}&"
               "yourName30={name}&"
               "preferredEmail={preferred}&"
               "preferredEmail8={preferred}&"
               "additionalEmail={other1}&"
               "additionalEmail17={other1}&"
               "additionalEmail13={other2}&"
               "additionalEmail18={other2}&"
               "additionalEmail14={other3}&"
               "additionalEmail19={other3}&"
               "additionalEmail15={other4}&"
               "additionalEmail20={other4}&"
               "additionalEmail16={other5}&"
               "additionalEmail21={other5}"
               .format(base=base_url,
                       parkey=row['ParKey'],
                       name=name,
                       preferred=row['PreferredEmail'],
                       other1=row['OtherEmail1'],
                       other2=row['OtherEmail2'],
                       other3=row['OtherEmail3'],
                       other4=row['OtherEmail4'],
                       other5=row['OtherEmail5']))

        message_body = ("""<html><body>
<p>Dear {name}:</p>

<p>In an effort to improve communications with the parish, the office
has been reviewing the parishioner email addresses we have on file.
It appears that some of our parishioners may not have been receiving
our parish-wide emails and some of the email addresses may not be
up-to-date.  We need your help to fix that!</p>

<p>In the next week or so, we will be including your email in the
distribution list for Parish-wWide emails.  It is possible that we do
not have the correct email on file for you, so if this communication
has reached you at the wrong -- or less -- preferred email address,
please click on the link below and update it.  Once you click on the
link, you can check what we have on file, make changes if necessary,
and have the option to "unsubscribe".  (Though we hope you will choose
to continue to receive our emails.)</p>

<p>If you have any changes to make, <em>please click the link below
and update your data before ___TBD___</em>.</p>

<p>We hope that you are as excited as we are to share with you the
happenings at Epiphany Catholic Church.  Thank you for your continued
support of our parish - there are exciting improvements coming soon
and we look forward to sharing more with you.</p>

<p><strong><a href="{url}">CLICK HERE TO UPDATE YOUR EMAIL ADDRESS
WITH EPIPHANY</a></strong>.</p>

<p>Sincerely,</p>

<p>Mary A. Downs<br />
Business Manager<br />
Epiphany Catholic Church<br />
502-245-9733 ext. 12</p></body></html>"""
                        .format(name=name,url=url))

        smtp_to = '"{name}" <{email}>'.format(name=name, email=row['PreferredEmail'])
        # JMS DEBUG
        smtp_to = '"{name}" <{email}>'.format(name=name, email='tech-committee@epiphanycatholicchurch.org')

        with smtplib.SMTP_SSL(host=smtp_server) as smtp:
            msg = EmailMessage()
            msg.set_content(message_body)
            msg['Subject'] = smtp_subject
            msg['From'] = smtp_from
            msg['To'] = smtp_to
            msg.replace_header('Content-Type', 'text/html')

            smtp.send_message(msg)
