#!/usr/bin/env python3

import traceback
import smtplib
import base64
import csv
import re

from recordclass import recordclass
from email.message import EmailMessage

single_email_base_url = 'https://form.jotform.us/72402423638149'
multi_email_base_url  = 'https://form.jotform.us/72402766938162'

smtp_server = 'smtp-relay.gmail.com'
smtp_from = '"Epiphany Catholic Church" <email-update@epiphanycatholicchurch.org>'
smtp_subject = 'Update your email address at Epiphany Catholic Church'

name_order = re.compile('^([^,]+),(.+)$')
name_squash1 = re.compile('\(.+\)')
name_squash2 = re.compile('\{.+\}')

member_email_filename = 'members-ge13-email-update-form.csv'

# Read in the list of those who we need to send the reminder.
NotUpdated = recordclass('NotUpdated',
                         ['ParKey',
                          'original_email'])

not_updated_filename = 'those-who-have-not-updated.csv'
not_updated_list = list()
with open(not_updated_filename, 'r', newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        nu = NotUpdated(ParKey         = int(row['ParKey']),
                        original_email = row['OriginalEmail'])
        not_updated_list.append(nu)

with open(member_email_filename, 'r', newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        # See if this person has not updated
        found = False
        pk = int(row['ParKey'])
        print("Checking: {pk} {name}"
              .format(pk=pk, name=row['PreferredEmail']))
        for nu in not_updated_list:
            if nu.ParKey == pk and nu.original_email == row['PreferredEmail']:
                print("FOUND SOMEONE WHO NEEDS A REMINDER: {pk} {mail}"
                      .format(pk=pk, mail=nu.original_email))
                found = True

        # If we didn't find this person in the "not updated list",
        # that means this person submitted.  So we don't need to bug
        # them again.
        if not found:
            continue

        # Fix a few things with names
        name = row['Member Name'].strip()

        # Remove all (foo) and {foo}
        name = name_squash1.sub('', name)
        name = name_squash2.sub('', name)

        # Some names are "Last,First".  Change that to "First Last"
        m = name_order.match(name)
        if m:
            first_name = m.group(2)
            full_name = "{first} {last}".format(last=m.group(1),
                                                first=m.group(2))
        else:
            words = name.split(' ')
            first_name = words[0]
            full_name = name

        # If we don't do this wonky value for the Family ID, the
        # resulting Google Sheet from the form submission will strip
        # off the leading zeros.  :-(
        parkey = "' {}".format(str(row['ParKey']).strip())

        print("Sending to: {fullname} ({salutation}) at {email}"
              .format(fullname=full_name,
                      salutation=first_name, email=row['PreferredEmail']))

        # If the Member has a single email address, use one form.  If
        # they have multiple addresses, use a different form.
        # Multiple email addresses
        if 'OtherEmail1' in row and row['OtherEmail1'] != '':
            we_have = row['PreferredEmail']
            if row['OtherEmail1']:
                we_have = we_have + '%0d' + row['OtherEmail1']
            if row['OtherEmail2']:
                we_have = we_have + '%0d' + row['OtherEmail2']
            if row['OtherEmail3']:
                we_have = we_have + '%0d' + row['OtherEmail3']
            if row['OtherEmail4']:
                we_have = we_have + '%0d' + row['OtherEmail4']
            if row['OtherEmail5']:
                we_have = we_have + '%0d' + row['OtherEmail5']

            url = ("{base}?"
                   "familyIdenvelope={parkey}&"
                   "yourName30={name}&"
                   "weHave={we_have}&"
                   "whichEmail={preferred}&"
                   "preferredEmail8={preferred}"
                   .format(base=multi_email_base_url,
                           parkey=parkey,
                           we_have=we_have,
                           name=full_name,
                           preferred=row['PreferredEmail']))

        # Single email address
        else:
            url = ("{base}?"
                   "familyIdenvelope={parkey}&"
                   "yourName30={name}&"
                   "preferredEmail={preferred}&"
                   "preferredEmail8={preferred}"
                   .format(base=single_email_base_url,
                           parkey=parkey,
                           name=full_name,
                           preferred=row['PreferredEmail']))

        message_body = ("""<html><body>
<p>
<img src="http://jeff.squyres.com/ecc/email-graphic.jpg" alt="" align="left" scale="0" style="margin: 0px 20px; height: 75px">
Dear {name}:</p>

<p>Just a gentle reminder: Epiphany wants to make sure that we have a
correct email addresses for you.  If this communication has reached
you at the wrong -- or a less-preferred -- email address <font
color="red"><em>and you have not already done so</em></font>, please
click on the link below and update it.  Once you click on the link,
you can check what we have on file, make changes if necessary, and
have the option to unsubscribe.</p>

<p>If you have any changes to make, <em>please click the link below
and update your data before October 16, 2017.</em>.</p>

<p>We hope that you are as excited as we are to share with you the
happenings at Epiphany Catholic Church.  Thank you for your continued
support of our parish - there are exciting improvements coming soon
and we look forward to sharing more with you.</p>

<p><strong><a href="{url}">CLICK HERE TO UPDATE YOUR EMAIL ADDRESS
WITH EPIPHANY</a></strong>.</p>

<p>Sincerely,</p>

<p>Mary A. Downs<br />
<em>Business Manager</em><br />
Epiphany Catholic Church<br />
502-245-9733 ext. 12</p></body></html>"""
                        .format(name=full_name, url=url))

        smtp_to = '"{name}" <{email}>'.format(name=name, email=row['PreferredEmail'])
        # JMS DEBUG
        #smtp_to = '"{name}" <{email}>'.format(name=name, email='tech-committee@epiphanycatholicchurch.org')
        # JMS DOUBLE DEBUG
        #smtp_to = '"{name}" <{email}>'.format(name=name, email='jsquyres@gmail.com')

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
            print("==== Error with {email}"
                  .format(email=row['PreferredEmail']))
            print(traceback.format_exc())
