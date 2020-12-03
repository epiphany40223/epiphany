This is the postfix config for the Linux VM running on the media
server.  This postfix server is mainly running to act as a relay from
the Konica Minolta copier to our Gmail SMTP servers.  The firmware
running on the Konica is too old to understand modern TLS protocol.
So we have the Konica submit to this local Postfix server, which then
relays out to smtp-relay.gmail.com for the actual delivery.

We use the "konica-minolta@epiphanycatholicchurch.org" G Suite user to
send these emails (i.e., the "from" address corresponds to a real G
Suite account; we also had to set to allow "less secure apps" on that
account -- THIS MAY STOP WORKING SOMEDAY!  I.e., Google may stop
allowing "less secure apps", in which case we'll have to figure out a
new solution.  Hopefully we'll have a new copier that can legit send
emails via Gmail by that point, and this won't be necessary!).  Note
that it was necessary to generate an app-specific password for the
konica-minolta@ecc user (which isn't saved in lastpass) because that
user uses 2FA.  If this password is lost, just delete it and
re-generate a new one.

Additionally, it looks like Google may periodically expire the 2FA/app
specific password.  When that happens, the mail will stop flowing
because Postfix will fail to SASL authenticate to smtp-relay.gmail.com (this
will be evident in the /var/log/mail.* logs).  Just login as
konica-minolta@ecc.org, go to the security settings on the account and
create a new app specific password.  Then follow the instructions in
the comments in these files for how to reset the Postfix config with
the new app specific password.

***UPDATE 2020 AUGUST:*** We stopped allowlisting Epiphany's IP
   address in the G Suite dashboard because we don't pay for a fixed
   IP address, and Spectrum kept changing it on us.  Instead, we're
   now using SMTP SASL AUTH authentication (which works no matter what
   IP address you're coming from).  As such, we updated the SMTP
   hostname to `smtp-relay.gmail.com`, which accepts authentication on
   port 587 (which is what we have Postfix configured to do).

***UPDATE 2020 AUGUST:*** The irony is that we updated to SMTP SASL
   AUTH right before we replaced the Konica with a modern Ricoh model
   that can natively email to Google, and this SMTP relay is no longer
   necessary for Konica scans.  We may still want this email relay for
   other reasons, though -- TBD.

See the "Epiphany" and "ECC" comments in the files in this folder for
more details about:

* exactly what settings were changed from the postfix defaults
* additional commands that were run (e.g., to setup the SASL password)
* additional Google dashboard settings that were required
