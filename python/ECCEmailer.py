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

import ECC

smtp_server     = 'smtp-relay.gmail.com'
smtp_from = 'no-reply@epiphanycatholicchurch.org'

def setup_cli_args():
    parser = argparse.ArgumentParser(description='Epiphany email sender')
    parser.add_argument(f'--smtp-auth-file',
                        required=True,
                        help='File containing SMTP AUTH username:password for {smtp_server}')
    parser.add_argument(f'--html-body-file',
                        required=False,
                        help='File containing HTML code to constitute email body')
    parser.add_argument(f'--subject',
                        required=True,
                        help='String to be inserted as email subject line')
    parser.add_argument(f'--recipient',
                        required=True,
                        help='Valid email address of recipient')
    parser.add_argument('--logfile',
                        default='log.txt',
                        help='Log file name')
    parser.add_argument(f'--slack-token-filename',
                        help='File containing the Slack bot authorization token')
    parser.add_argument(f'--client',
                        help='Sender address',
                        default=smtp_from)
    args = parser.parse_args()

    return args

#------------------------------------------------------------------

def read_smtp_credentials(smtp_auth_file):
    with open(smtp_auth_file) as f:
        line = f.read()
        smtp_username, smtp_password = line.split(':')
        return smtp_username, smtp_password

#------------------------------------------------------------------

def set_email_body(body_file):
    with open(body_file) as f:
        content = f.read()
        return content

#------------------------------------------------------------------

def send_email(body_file, smtp_auth_file, recipient, subject, client, log): 
    with smtplib.SMTP_SSL(host=smtp_server,
                          local_hostname='epiphanycatholicchurch.org') as smtp:
        msg = EmailMessage()
        body = set_email_body(body_file)
        msg.set_content(body)

        # Login; we can't rely on being IP allowlisted.
        smtp_username, smtp_password = read_smtp_credentials(smtp_auth_file)
        try:
            smtp.login(smtp_username, smtp_password)
        except Exception as e:
            log.error(f'Error: failed to SMTP login: {e}')
            exit(1)

        msg['From']    = client
        msg['To']      = recipient
        msg['Subject'] = subject
        msg.replace_header('Content-Type', 'text/html')

        smtp.send_message(msg)

#------------------------------------------------------------------

def main():
    args = setup_cli_args()
    log  = ECC.setup_logging(logfile=args.logfile,
                            rotate=True,
                            slack_token_filename=args.slack_token_filename)

    send_email(args.html_body_file, args.smtp_auth_file, args.recipient, args.subject, args.client, log)
    
main()