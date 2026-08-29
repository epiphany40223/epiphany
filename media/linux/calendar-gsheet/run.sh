#!/bin/bash

#
# Run the PS queries scripts.
#

set -xeuo pipefail

logfile_dir=$HOME/logfiles
credential_dir=$HOME/credentials

git_base=$HOME/git/epiphany/media/linux
prog_dir=$git_base/calendar-gsheet

cd $prog_dir

################################################################################
# Do things in Google, once a day
#
# NOTE: These scripts require Google credentials.
################################################################################

# We only need to do this once a day, around 2am or so.

hour=`date '+%H'`
minute=`date '+%M'`

if test $hour -eq 2 -a $minute -lt 15; then
    gsheet_logfile=$logfile_dir/linux/gsheet-driven-google-group/gsheet-driven-google-group-logfile.txt
    goog_cred_dir=$credential_dir/gsheet-driven-google-group
    ./gsheet-driven-google-group.py \
        --service-account-json $credential_dir/ecc-emailer-service-account.json \
        --impersonated-user no-reply@epiphanycatholicchurch.org \
        --logfile=$gsheet_logfile \
	--app-id $goog_cred_dir/client-id-gsheet-driven-google-group.json \
	--user-credentials $goog_cred_dir/user-credentials-gsheet-driven-google-group.json
fi
