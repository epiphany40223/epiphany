#!/bin/zsh

#
# Run the PDS SQL queries scripts.
#

set -xeuo pipefail

base=/home/coeadmin/git/epiphany/media/linux
prog_dir=$base/pds-sqlite3-queries
sqlite_dir=$base/pds-data

cd $prog_dir

################################################################################
#
# Synchronize PDS and select Google Groups.
#
# NOTE: This script requires Google credentials.  See the comments at
# the top of the script for more information.
################################################################################

# Generate the list of email addresses from PDS data and sync
google_logfile=$HOME/logfiles/linux/sync-google-group/sync-google-group-logfile.txt
cred_dir=$HOME/credentials/pds-sqlite3-queries
./sync-google-group.py \
    --smtp-auth-file $HOME/credentials/smtp-auth.txt \
    --slack-token-file $HOME/credentials/slack-token.txt \
    --sqlite3-db=$sqlite_dir/pdschurch.sqlite3 \
    --app-id $cred_dir/client_id.json \
    --user-credentials $cred_dir/user-credentials.json \
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
    roster_logfile=$HOME/logfiles/linux/ministry-roster/ministry-roster-logfile.txt
    cred_dir=$HOME/credentials/google-drive-uploader
    ./create-ministry-rosters.py \
	--sqlite3-db=$sqlite_dir/pdschurch.sqlite3 \
	--logfile=$roster_logfile \
	--app-id $cred_dir/google-uploader-client-id.json \
	--user-credentials $cred_dir/google-uploader-user-credentials.json

    roster_logfile=$HOME/logfiles/linux/training-roster/trailing-roster-logfile.txt
    ./create-training-rosters.py \
	--sqlite3-db=$sqlite_dir/pdschurch.sqlite3 \
	--logfile=$roster_logfile \
	--app-id $cred_dir/google-uploader-client-id.json \
	--user-credentials $cred_dir/google-uploader-user-credentials.json

    ppc_logfile=$HOME/logfiles/linux/ppc-feedback/ppc-feedback-logfile.txt
    ./ppc-feedback-google-group.py \
        --smtp-auth-file $HOME/credentials/smtp-auth.txt \
        --logfile=$ppc_logfile \
	--app-id $cred_dir/google-uploader-client-id.json \
	--user-credentials $cred_dir/google-uploader-user-credentials.json
fi
