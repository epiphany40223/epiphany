#!/bin/bash

set -xeuo pipefail

base=$HOME/git/epiphany/media/linux
prog_dir=$base/calendar-reservations
logfile=$HOME/logfiles/linux/calendar-reservations/logfile.txt
slack_token=$HOME/credentials/slack-token.txt
cred_dir=$HOME/credentials/calendar-reservations
client_id=$cred_dir/gcalendar-reservations-client-id.json
user_creds=$cred_dir/gcalendar-reservations-user-credentials.json

cd $prog_dir

# We're already running under a top-level runner.py (which reports
# Python errors to Slack), so we can just directly invoke our script
# here.
./calendar-reservations.py \
    --verbose \
    --slack-token-filename $slack_token \
    --logfile $logfile \
    --app-id $client_id \
    --user-credentials $user_creds \
    |& tee calendar.out

exit 0
