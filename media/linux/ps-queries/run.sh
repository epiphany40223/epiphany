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
    --service-account-json $credential_dir/ecc-emailer-service-account.json \
    --impersonated-user no-reply@epiphanycatholicchurch.org \
    --app-id $goog_cred_dir/sync-google-group-client-id.json \
    --user-credentials $goog_cred_dir/sync-google-group-user-credentials.json \
    --logfile=$google_logfile \
    --debug

cc_logfile=$logfile_dir/linux/sync-constant-contact/sync-cc-logfile.txt
cc_cred_dir=$goog_cred_dir

# Run the unsubscribed report once a week on Mondays between 2:00-2:15am
cc_extra_args=""
dow=`date '+%u'`
hour=`date '+%H'`
minute=`date '+%M'`
if test $dow -eq 1 -a $hour -eq 2 -a $minute -lt 15; then
    cc_extra_args="--unsubscribed-report"
fi

./sync-ps-to-cc.py \
    --ps-api-keyfile $credential_dir/parishsoft-api-key.txt \
    --ps-cache-dir=$git_base/ps-data \
    --cc-client-id $cc_cred_dir/constant-contact-client-id.json \
    --cc-access-token $cc_cred_dir/constant-contact-access-token.json \
    --service-account-json $credential_dir/ecc-emailer-service-account.json \
    --impersonated-user no-reply@epiphanycatholicchurch.org \
    --update-names \
    --logfile=$cc_logfile \
    --debug \
    $cc_extra_args

################################################################################
# Do other things in Google, once a day
#
# NOTE: These scripts require Google credentials.
################################################################################

# We only need to do this once a day, around 2am or so.

if test $hour -eq 2 -a $minute -lt 15; then
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
        --service-account-json $credential_dir/ecc-emailer-service-account.json \
        --impersonated-user no-reply@epiphanycatholicchurch.org \
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
