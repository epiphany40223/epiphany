#!/bin/zsh

#
# Run the PDS SQL queries scripts.
#

set -xeuo pipefail

logfile_dir=/home/coeadmin/logfiles
credential_dir=/home/coeadmin/credentials

git_base=/home/coeadmin/git/epiphany/media/linux
prog_dir=$git_base/pds-sqlite3-queries
sqlite_dir=$git_base/pds-data

cd $prog_dir

################################################################################
#
# Synchronize PDS and select Google Groups.
#
# NOTE: This script requires Google credentials.  See the comments at
# the top of the script for more information.
################################################################################

# Generate the list of email addresses from PDS data and sync
google_logfile=$logfile_dir/linux/sync-google-group/sync-google-group-logfile.txt
goog_cred_dir=$credential_dir/pds-sqlite3-queries
./sync-google-group.py \
    --smtp-auth-file $credential_dir/smtp-auth.txt \
    --slack-token-file $credential_dir/slack-token.txt \
    --sqlite3-db=$sqlite_dir/pdschurch.sqlite3 \
    --app-id $goog_cred_dir/client_id.json \
    --user-credentials $goog_cred_dir/user-credentials.json \
    --logfile=$google_logfile \
    --verbose

################################################################################
#
# Generate Google sheet rosters
#
# NOTE: This script requires Google credentials.
################################################################################

# Generate ministry rosters
# We only need to do this once a day, around 2am or so.

h=`date '+%H'`
m=`date '+%M'`
if test $h -eq 2 -a $m -lt 15; then
    roster_logfile=$logfile_dir/linux/ministry-roster/ministry-roster-logfile.txt
    goog_cred_dir=$credential_dir/google-drive-uploader
    ./create-ministry-rosters.py \
	--sqlite3-db=$sqlite_dir/pdschurch.sqlite3 \
	--logfile=$roster_logfile \
	--app-id $goog_cred_dir/google-uploader-client-id.json \
	--user-credentials $goog_cred_dir/google-uploader-user-credentials.json

    roster_logfile=$logfile_dir/linux/training-roster/trailing-roster-logfile.txt
    ./create-training-rosters.py \
	--sqlite3-db=$sqlite_dir/pdschurch.sqlite3 \
	--logfile=$roster_logfile \
	--app-id $goog_cred_dir/google-uploader-client-id.json \
	--user-credentials $goog_cred_dir/google-uploader-user-credentials.json

    ppc_logfile=$logfile_dir/linux/ppc-feedback/ppc-feedback-logfile.txt
    goog_cred_dir=$credential_dir/ppc-feedback
    ./ppc-feedback-google-group.py \
        --smtp-auth-file $credential_dir/smtp-auth.txt \
        --logfile=$ppc_logfile \
	--app-id $goog_cred_dir/client-id-ppc-feedback.json \
	--user-credentials $goog_cred_dir/user-credentials-ppc-feedback.json
fi
