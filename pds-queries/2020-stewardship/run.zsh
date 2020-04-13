#!/bin/zsh

# This is a convenience script to invoke the "send all the emails"
# script.
#
# You should run copy-while-running.zsh at the same time as
# this script!!

start=`date`
echo "========================================================="
echo "Starting at: $start"
echo "========================================================="

#email=email-initial.html
email=email-1st-reminder.html

./make-and-send-emails.py \
        --email-content $email \
        --unsubmitted \
        --cookie-db cookies.sqlite3 \
        --append \
        |& tee out.txt

echo "========================================================="
echo "Started at:  $start"
echo "Finished at: `date`"
echo "========================================================="
