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
smtp_to     = 'staff@epiphanycatholicchurch.org,itadmin@epiphanycatholicchurch.org'
subject     = 'Epiphany backup Thursday reminder'

body        = '''<h1>REMINDER!</h1>

<p>The Tech committee needs you to run your laptop backup today.</p>

<ol>
<li> Double click on the "Backup to fileengine" icon on your desktop.</li>
<li> It will open a window and start scrolling text.</li>
<li> The backup will finish and the window will close by itself.</li>
<li> You can continue to do other work while the backup is running.</li>
</ol>

<p><font color="red"><em><strong>YOU MUST BE ON THE EPIPHANY CAMPUS TO
RUN THE BACKUP!</strong></em></font> If you're not on campus today,
please run the backup the next time you're on campus.<p>

<p>It is very, <em>Very</em>, <strong>VERY</strong> important for you
to run backups on a regular basis.  Go start this backup
<em><strong>NOW</strong></em> while you're thinking about it.</p>

<p>Thanks!</p>

<p>Your friendly server,<br />
Myrador</p>'''

#------------------------------------------------------------------

with smtplib.SMTP_SSL(host=smtp_server) as smtp:
    msg = EmailMessage()
    msg.set_content(body)

    msg['From']    = smtp_from
    msg['To']      = smtp_to
    msg['Subject'] = subject
    msg.replace_header('Content-Type', 'text/html')

    smtp.send_message(msg)
