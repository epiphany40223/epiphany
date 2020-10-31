#!/usr/bin/env python3

#
# Send a simple automated email.
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
# And then make sure that the sender is actually a valid email address
# in the ECC Google domain.
#

import smtplib
import argparse

from email.message import EmailMessage

smtp_server = 'smtp-relay.gmail.com'
smtp_from   = 'Epiphany reminder <no-reply@epiphanycatholicchurch.org>'
smtp_to     = 'staff@epiphanycatholicchurch.org,itadmin@epiphanycatholicchurch.org'
subject     = 'Epiphany patch Tuesday reminder'

parser = argparse.ArgumentParser(description='Patch Tuesday email sender')
parser.add_argument(f'--smtp-auth-file',
                    required=True,
                    help='File containing SMTP AUTH username:password for {smtp_server}')
args = parser.parse_args()

# This assumes that the file has a single line in the format of username:password.
with open(args.smtp_auth_file) as f:
    line = f.read()
    smtp_username, smtp_password = line.split(':')

body        = '''<h1>REMINDER!</h1>

<p>The Tech committee needs to run updates on your computer this evening.
Please:</p>

<ol>
<li> Leave your computer powered on tonight.</li>
<li> Ensure that the computer is connected to AC power.</li>
<li> Ensure that the computer is connected to the internet.</li>
</ol>

<p>You can still logout of your computer when you are finished; the Tech
Committee just needs the machine powered on, connected to AC power, and
connected to the internet.</p>

<p>If you cannot leave your computer on tonight, please let the Tech
Committee know.  Thanks.</p>

<p>Your friendly server,<br />
Myrador</p>'''

#------------------------------------------------------------------

with smtplib.SMTP_SSL(host=smtp_server,
                      local_hostname='epiphanycatholicchurch.org') as smtp:
    msg = EmailMessage()
    msg.set_content(body)

    # Login; we can't rely on being IP whitelisted.
    try:
        smtp.login(smtp_username, smtp_password)
    except Exception as e:
        log.error(f'Error: failed to SMTP login: {e}')
        exit(1)

    msg['From']    = smtp_from
    msg['To']      = smtp_to
    msg['Subject'] = subject
    msg.replace_header('Content-Type', 'text/html')

    smtp.send_message(msg)
