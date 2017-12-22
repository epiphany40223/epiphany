#!/bin/zsh

set -x

base=/home/itadmin/git/epiphany/media/linux
prog_dir=$base/pds-sqlite3-queries
sqlite_dir=$base/pds-data

cd $prog_dir

# Generate the list of email addresses from PDS data
mailman_logfile=$prog_dir/sync-mailman-logfile.txt
./sync-mailman.py \
    --sqlite3-db=$sqlite_dir/pdschurch.sqlite3 \
    --logfile=$mailman_logfile \
    --verbose

# This generated mailman-parishioner.txt.
# Copy this file up to the mailman server.
file=mailman-parishioner.txt
scp $file jeff@lists.epiphanycatholicchurch.org:ecc
# Now update the list
ssh jeff@lists.epiphanycatholicchurch.org ecc/replace-parishioners.sh ecc/$file

################################################################################

# Generate the list of email addresses from PDS data and sync
google_logfile=$prog_dir/sync-google-group-logfile.txt
./sync-google-group.py \
    --sqlite3-db=$sqlite_dir/pdschurch.sqlite3 \
    --logfile=$google_logfile \
    --verbose

exit 0
