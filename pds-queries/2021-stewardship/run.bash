#!/bin/bash

set -euo pipefail

# This is a convenience script to invoke the "send all the emails"
# script.
#
# You should run copy-while-running.zsh at the same time as
# this script!!

start=`date`
echo "========================================================="
echo "Starting at: $start"
echo "========================================================="

email=email-initial.html

./make-and-send-emails.py \
        --email-content $email \
        --unsubmitted \
        --cookie-db cookies.sqlite3 \
        --append \
        2>&1 | tee out.txt

echo "========================================================="
echo "Started at:  $start"
echo "Finished at: `date`"
echo "========================================================="
