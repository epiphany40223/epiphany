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
./sync-google-group.py \
    --smtp-auth-file $HOME/smtp-auth.txt \
    --slack-token-file $HOME/slack-token.txt \
    --sqlite3-db=$sqlite_dir/pdschurch.sqlite3 \
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
    ./create-ministry-rosters.py \
	--sqlite3-db=$sqlite_dir/pdschurch.sqlite3 \
	--logfile=$roster_logfile \
	--app-id ../google-drive-uploader/google-uploader-client-id.json \
	--user-credentials ../google-drive-uploader/google-uploader-user-credentials.json

    roster_logfile=$HOME/logfiles/linux/training-roster/trailing-roster-logfile.txt
    ./create-training-rosters.py \
	--sqlite3-db=$sqlite_dir/pdschurch.sqlite3 \
	--logfile=$roster_logfile \
	--app-id ../google-drive-uploader/google-uploader-client-id.json \
	--user-credentials ../google-drive-uploader/google-uploader-user-credentials.json

    ppc_logfile=$HOME/logfiles/linux/ppc-feedback/ppc-feedback-logfile.txt
    ./ppc-feedback-google-group.py \
        --smtp-auth-file $HOME/smtp-auth.txt \
        --logfile=$ppc_logfile \
        --app-id $HOME/credentials/client_id-ppc-feedback.json \
        --user-credentials $HOME/credentials/user-credentials-ppc-feedback.json
fi
