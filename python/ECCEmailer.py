#!/usr/bin/env python3
#
# Send an automated email based on provided information.
#
# This script presumes that smtp-relay.gmail.com has been setup to
# accept emails from this public IP address without authentication.
# To set this up:
#
# 1. Login to admin.google.com as an administrator.
# 2. Apps
# 3. G Suite
# 4. Gmail
# 5. Advanced settings (at the bottom of the list)
# 6. Scroll down to Routing and find SMTP relay service
# 7. Add the desired IP address:
#    - require TLS encryption: yes
#    - require SMTP authentication: no
#    - allowed senders: Only addresses in my domains
#

import smtplib
import argparse

from email.message import EmailMessage
import mimetypes

import ECC
import Google

smtp_server = 'smtp-relay.gmail.com'
smtp_from   = 'no-reply@epiphanycatholicchurch.org'

###########################################################

# This assumes that the file has a single line in the format
# of username:password.
def _read_smtp_credentials(smtp_auth_file):
    with open(smtp_auth_file) as f:
        line = f.read()
        smtp_username, smtp_password = line.split(':')
        return smtp_username, smtp_password

###########################################################

def _set_attachments(attachments, msg, log):
    if attachments is not None:
        for attachment in attachments.values():
            fname = attachment['filename']
            ftype = attachment['type']
            log.debug(f"Attachment is: {fname}")
            log.debug(f'Ftype is: {ftype}')
            log.debug(f'mime types are {Google.mime_types[ftype]}')
            mime_type, mime_subtype = Google.mime_types[ftype].split('/')

            with open(fname, 'rb') as ap:
                msg.add_attachment(ap.read(), maintype = mime_type,
                                   subtype = mime_subtype,
                                   filename = fname)

    return msg

###########################################################

# This is a public function because there are places in ECC code where
# we want to open 1 SMTP connection and send a lot of emails on it.
def open_smtp_connection(smtp_auth_file, log):
    smtp = smtplib.SMTP_SSL(host=smtp_server,
                            local_hostname='epiphanycatholicchurch.org')
    # Login; we can't rely on being IP allowlisted.
    try:
        # This assumes that the file has a single line in the format
        # of username:password.
        smtp_username, smtp_password = _read_smtp_credentials(smtp_auth_file)
        smtp.login(smtp_username, smtp_password)
    except Exception as e:
        log.error(f'Error: failed to SMTP login: {e}')
        exit(1)

    return smtp

###########################################################

# If you have an existing SMTP connection (from
# open_smtp_connection()), use this function to send a single email on
# it.
def send_email_existing_smtp(body, bodytype, attachments, recipient, subject,
                             smtp_from, smtp, log):
    msg = EmailMessage()
    msg.set_content(body)
    msg['From']    = smtp_from
    msg['To']      = recipient
    msg['Subject'] = subject
    msg.replace_header('Content-Type', Google.mime_types[bodytype])

    msg = _set_attachments(attachments, msg, log)
    smtp.send_message(msg)

###########################################################

def send_email(body, bodytype, attachments, smtp_auth_file, recipient, subject,
               smtp_from, log):
    with open_smtp_connection(smtp_auth_file, log) as smtp:
        send_email_existing_smtp(body, bodytype, attachments,
                                 recipient, subject, smtp_from,
                                 smtp, log)
