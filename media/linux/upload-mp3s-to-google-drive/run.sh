#!/bin/bash

set -xeuo pipefail

base=$HOME/git/epiphany/media/linux
name=upload-mp3s-to-google-drive
prog_dir=$base/$name
logfile=$HOME/logfiles/linux/$name/logfile.txt
slack_token=$HOME/credentials/slack-token.txt
cred_base=$HOME/credentials
cred_dir=$cred_base/$name
client_id=$cred_dir/$name-client-id.json
user_creds=$cred_dir/$name-user-credentials.json
# This is the ID for the "ECC Recordings" Google Shared Drive
shared_drive_id=0AJQlNh2zkxqWUk9PVA

data_dir=$HOME/wc-mp3-recordings
incoming_ftp_dir=/mnt/c/ftp/ECC-recordings

cd $prog_dir

set +u
. ./py312/bin/activate
set -u

./find-and-copy.py \
    --smtp \
        smtp-relay.gmail.com \
        director-worship@epiphanycatholicchurch.org,itadmin@epiphanycatholicchurch.org \
        no-reply@epiphanycatholicchurch.org \
    --smtp-auth-file $cred_base/smtp-auth.txt \
    --logfile $logfile \
    --app-id $client_id \
    --user-creds $user_creds \
    --google-shared-drive-id $shared_drive_id \
    --data-dir $data_dir \
    --incoming-ftp-dir $incoming_ftp_dir
