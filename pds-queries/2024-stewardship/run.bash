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
#email_file=email-commitment-weekend.html
#email_file=email-1st-reminder.html
#email_file=email-sorry-we-did-get-your-submission.html
#email_file=email-2nd-reminder.html
#email_file=email-3rd-reminder.html
#email_file=email-4th-reminder.html
#email_file=email-5th-reminder.html
#email_file=email-6th-reminder.html
#email_file=email-7th-reminder.html
email_file=email-final-reminder.html

#email_addr=jeff@squyres.com
#email_addr=jsquyres@epiphanycatholicchurch.org
#email_addr=billc9936@gmail.com
#email_addr=sdreiss71@gmail.com
#filter="--email $email_addr"

#filter="--all"
#filter="--all --do-not-send"

#email_file=email-test.html
#env_ids_file=id.txt
#filter="--env-id-file $env_ids_file"
#filter="--env-id-file $env_ids_file --do-not-send"

#filter="--submitted"
#filter="--submitted --do-not-send"

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
