#!/bin/bash

#
# Run the PS queries scripts.
#

set -xeuo pipefail

logfile_dir=$HOME/logfiles
credential_dir=$HOME/credentials

git_base=$HOME/git/epiphany/media/linux
prog_dir=$git_base/ps-queries
sqlite_dir=$git_base/ps-data

cd $prog_dir

################################################################################
#
# Synchronize PS and select Google Groups.
#
# NOTE: This script requires Google credentials.  See the comments at
# the top of the script for more information.
################################################################################

# Generate the list of email addresses from PS data and sync
google_logfile=$logfile_dir/linux/sync-google-group/sync-google-group-logfile.txt
goog_cred_dir=$credential_dir/ps-queries
./sync-google-group.py \
    --ps-api-keyfile $credential_dir/parishsoft-api-key.txt \
    --ps-cache-dir=$git_base/ps-data \
    --smtp-auth-file $credential_dir/smtp-auth.txt \
    --app-id $goog_cred_dir/sync-google-group-client-id.json \
    --user-credentials $goog_cred_dir/sync-google-group-user-credentials.json \
    --logfile=$google_logfile \
    --debug

################################################################################
# Do other things in Google, once a day
#
# NOTE: These scripts require Google credentials.
################################################################################

# We only need to do this once a day, around 2am or so.

h=`date '+%H'`
m=`date '+%M'`
if test $h -eq 2 -a $m -lt 15; then
    roster_logfile=$logfile_dir/linux/ministry-roster/ministry-roster-logfile.txt
    goog_cred_dir=$credential_dir/google-drive-uploader
    ./create-ministry-rosters.py \
        --ps-api-keyfile $credential_dir/parishsoft-api-key.txt \
        --ps-cache-dir=$git_base/ps-data \
	--logfile=$roster_logfile \
	--app-id $goog_cred_dir/google-uploader-client-id.json \
	--user-credentials $goog_cred_dir/google-uploader-user-credentials.json

    gsheet_logfile=$logfile_dir/linux/gsheet-driven-google-group/gsheet-driven-google-group-logfile.txt
    goog_cred_dir=$credential_dir/gsheet-driven-google-group
    ./gsheet-driven-google-group.py \
        --smtp-auth-file $credential_dir/smtp-auth.txt \
        --logfile=$gsheet_logfile \
	--app-id $goog_cred_dir/client-id-gsheet-driven-google-group.json \
	--user-credentials $goog_cred_dir/user-credentials-gsheet-driven-google-group.json
fi

################################################################################
# Do other things once a week, on Monday mornings
#
# NOTE: These scripts require Google credentials.
################################################################################

day=`date '+%a'`
time=`date '+%H%M'`
if test $day == 'Mon' -a -lt 14; then
    ./ps-error-checker.py \
        --debug \
        --ps-api-keyfile $credential_dir/parishsoft-api-key.txt \
        --ps-cache-dir=$git_base/ps-data \
        --smtp-auth-file $credential_dir/smtp-auth.txt \
	--logfile=$roster_logfile
fi
