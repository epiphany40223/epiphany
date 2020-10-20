#!/bin/bash

set -euo pipefail

# This is a convenience script to invoke the "send all the emails"
# script.
#
# You should run copy-while-running.sh at the same time as
# this script!!

start=`date`
echo "========================================================="
echo "Starting at: $start"
echo "========================================================="

#email_file=email-initial.html
email_file=email-5th-reminder.html

#email_addr=jeff@squyres.com
#email_addr=jsquyres@epiphanycatholicchurch.org
#filter="--email $email_addr"

#filter="--all"

#email_file=email-test.html
#env_ids_file=id.txt
#filter="--env-id-file $env_ids_file"

filter="--unsubmitted"
#filter="--unsubmitted --do-not-send"

./make-and-send-emails.py \
        --smtp-auth smtp-auth.txt \
        --email-content $email_file \
        $filter \
        --cookie-db cookies.sqlite3 \
        --append \
        2>&1 | tee out.txt

echo "========================================================="
echo "Started at:  $start"
echo "Finished at: `date`"
echo "========================================================="
