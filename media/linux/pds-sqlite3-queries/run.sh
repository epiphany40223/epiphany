#!/bin/zsh

#
# Run the PDS SQL queries scripts.
#

set -x

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
google_logfile=$prog_dir/sync-google-group-logfile.txt
./sync-google-group.py \
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
    roster_logfile=$prog_dir/ministry-roster-logfile.txt
    ./create-ministry-rosters.py \
	--sqlite3-db=$sqlite_dir/pdschurch.sqlite3 \
	--logfile=$roster_logfile \
	--app-id ../google-drive-uploader/google-uploader-client-id.json \
	--user-credentials ../google-drive-uploader/google-uploader-user-credentials.json
fi

exit 0
