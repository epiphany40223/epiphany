#!/usr/bin/env python

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

from email.message import EmailMessage

smtp_server = 'smtp-relay.gmail.com'
smtp_from   = 'Epiphany reminder <no-reply@epiphanycatholicchurch.org>'
smtp_to     = 'staff@epiphanycatholicchurch.org,tech-committee@epiphanycatholicchurch.org'
subject     = 'Epiphany time card reminder'

body        = '''
<p>Please complete and turn in timesheets the first working day
after the 15th and end of each month.</p>

<p>Thanks!</p>

<p>Your friendly server,<br />
Teddy</p>'''

#------------------------------------------------------------------

with smtplib.SMTP_SSL(host=smtp_server) as smtp:
    msg = EmailMessage()
    msg.set_content(body)

    msg['From']    = smtp_from
    msg['To']      = smtp_to
    msg['Subject'] = subject
    msg.replace_header('Content-Type', 'text/html')

    smtp.send_message(msg)
