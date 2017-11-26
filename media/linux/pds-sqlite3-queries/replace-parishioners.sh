#!/bin/zsh

# Temporary script used to sync Epiphany's email parishioner list.  To
# be replaced with a Google Group in the "near future" (as of Nov
# 2017).

##########################################################################
# This script runs on lists.epiphanycatholicchurch.org.  Be sure to
# update the pds-sqlite3-queries/run.sh script with the proper path to
# this script on lists.ecc.org.  Also be sure that the user running on
# lists.ecc.org has NOPASSWD: permissions on the mailman sync_users
# command.
##########################################################################

to="jeff@squyres.com mary@epiphanycatholicchurch.org"
from='Jeff Squyres WBS relay'
subject='Parishioner listserve update'

##########################################################################

doit() {
    eval "$@"
	st=$?
	if test $st -ne 0; then
		echo command failed: "$@"
		echo exit status: $st
		exit $st
	fi
}

#------------------------------------------------------------------------

new_file=$1
if test -z "$1" -o ! -r $1; then
	echo cannot read new parishioner list file: $1
	exit 1
fi

# Setup to capture the output
dir=`dirname $0`
logfile=$dir/changes.txt
rm -rf $logfile

# Do it!
doit sudo -n sync_members -w=no -g=no -a=no -f $new_file parishioner > $logfile

# If something happened, email the results
if test "`cat $logfile`" != 'Nothing to do.'; then
    export MAILNAME="$from"
    doit mail $to -s \$subject <<EOF
Updating the "parishioner" listserve with the latest PDS data:

`cat $logfile`
EOF
fi
doit rm -f $logfile

# Get rid of the old file
doit rm -f $new_file

# All done!
exit 0
