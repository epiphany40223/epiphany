#!/bin/bash

set -xeuo pipefail

base=$HOME/git/epiphany/media/linux
name=email-patch-tuesday
prog_dir=$base/$name
cred_dir=$HOME/credentials

cd $prog_dir

# Only run on Tuesdays, between 10am and 10:14am.
day=`date '+%u'`
if test $day -eq 2; then
    t=`date '+%d%H%M'`
    if test $t -ge 1000 -a $t -le 1014; then
        ./patch-tuesday.py \
            --smtp-auth-file $cred_dir/smtp-auth.txt \
            |& tee calendar.out
    fi
fi

exit 0
