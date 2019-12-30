This is the postfix config for the Linux VM running on the media
server.  This postfix server is mainly running to act as a relay from
the Konica Minolta copier to our Gmail SMTP servers.  The firmware
running on the Konica is too old to understand modern TLS protocol.
So we have the Konica submit to this local Postfix server, which then
relays out to smtp.gmail.com for the actual delivery.

We use the "konica-minolta@epiphanycatholicchurch.org" G Suite user to
send these emails (i.e., the "from" address corresponds to a real G
Suite account so that we can set to use "less secure apps" on that
account).

See the "Epiphany" and "ECC" comments in this file for more details
about:

* exactly what settings were changed from the postfix defaults
* additional commands that were run (e.g., to setup the SASL password)
* additional Google dashboard settings that were required