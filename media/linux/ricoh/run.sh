#!/bin/bash

set -xeuo pipefail

base=$HOME/git/epiphany/media/linux
prog_dir=$base/ricoh
logfile=$HOME/logfiles/linux/ricoh/logfile.txt
slack_token=$HOME/credentials/slack-token.txt
ricoh_password=$HOME/credentials/ricoh-password.txt

cd $prog_dir

# We're already running under a top-level runner.py (which reports
# Python errors to Slack), so we can just directly invoke our script
# here.

# Run once a day (i.e., the first run after midnight)
t=`date '+%H%M'`
if test $t -le 14; then
    file=ricoh-`date "+%Y-%m-%d-%H%M"`.csv
    # Download the CSV data from the Ricoh
    ./download-user-counter.py \
        --verbose \
        --ip 10.10.0.4 \
        --password-filename $ricoh_password \
        --slack-token-filename $slack_token \
        --csv $file \
        |& tee ricoh.out

    # ... add the CSV data to the Ricoh SQLite database ...
fi

exit 0
