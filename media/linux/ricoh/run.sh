#!/bin/bash

set -xeuo pipefail

base=$HOME/git/epiphany/media/linux
prog_dir=$base/ricoh
logfile=$HOME/logfiles/linux/ricoh/logfile.txt
credential_dir=/home/coeadmin/credentials
slack_token=$credential_dir/slack-token.txt
ricoh_password=$credential_dir/ricoh-password.txt
smtp_creds=$credential_dir/smtp-auth.txt
sqlite3_file=$prog_dir/ricoh.sqlite3

cd $prog_dir

# We're already running under a top-level runner.py (which reports
# Python errors to Slack), so we can just directly invoke our script
# here.

# Run once a day (i.e., the first run after midnight)
t=`date '+%H%M'`
if test $t -le 14; then
    file=ricoh-`date "+%Y-%m-%d-%H%M"`.csv
    gmt_timestamp=`date -u "+%Y-%m-%d %H:%M:%S"`
    # Download the CSV data from the Ricoh
    ./download-user-counter.py \
        --verbose \
        --ip 10.10.0.4 \
        --password-filename $ricoh_password \
        --slack-token-filename $slack_token \
        --csv $file \
        |& tee ricoh.out

    # Insert the result into the sqlite3 database
    ./db_insert.py \
        --slack-token-filename $slack_token \
        --logfile $logfile \
        --db $sqlite3_file \
        --verbose \
        --csv $file \
        --timestamp "$gmt_timestamp"
fi

# Run once a month, on the 9th
day=`date '+%d'`
if test $day -eq 9 && test $t -le 14; then
    # This folder is in the ECC Tech Committee Google Shared Drive,
    # under "Data/Ricoh".
    google_folder=1zPjpPSFiNttptZ_TEi6FCVOzaBi7O5dD
    email_to=ricoh-reporting@epiphanycatholicchurch.org

    name=upload-ricoh-to-google-drive
    cred_base=$HOME/credentials
    cred_dir=$cred_base/$name
    client_id=$cred_dir/$name-client-id.json
    user_creds=$cred_dir/$name-user-credentials.json

    first=`date +%Y-%m-%d -d "1 month ago"`
    last=`date +%Y-%m-%d -d yesterday`
    ./report.py \
        --debug \
        --smtp-recipient $email_to \
        --smtp-auth-file $smtp_creds \
        --db ricoh.sqlite3 \
        --first $first \
        --last $last \
        --xlsx "$first to $last ricoh data.xlsx" \
        --app-id $client_id \
        --user-creds $user_creds \
        --google-parent-folder-id $google_folder \
        --slack-token-filename $slack_token
fi

exit 0
