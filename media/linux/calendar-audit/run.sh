#!/bin/bash

set -xeuo pipefail

base=$HOME/git/epiphany/media/linux
prog_dir=$base/calendar-audit
logfile=$HOME/logfiles/linux/calendar-audit/logfile.txt
slack_token=$HOME/credentials/slack-token.txt
cred_dir=$HOME/credentials/calendar-audit
client_id=$cred_dir/client_id-automated-reports.json
user_creds=$cred_dir/user-credentials-automated-reports.json

cd $prog_dir

# Only run on the first day of the month, before 12:15am.
t=`date '+%d%H%M'`
if test $t -le 10014; then
    # We're already running under a top-level runner.py (which reports
    # Python errors to Slack), so we can just directly invoke our script
    # here.
    ./calendar-audit.py \
        --verbose \
        --slack-token-filename $slack_token \
        --logfile $logfile \
        --app-id $client_id \
        --user-credentials $user_creds \
        |& tee calendar.out
fi

exit 0
