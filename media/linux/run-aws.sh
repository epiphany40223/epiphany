#!/bin/bash

set -eoux pipefail

TOP=$HOME/git/epiphany

cd $TOP/media/linux

. ./py312/bin/activate

# Set timeout for 14.5 minutes because periodically Google APIs
# take a long time for no apparent reason
$TOP/slack/runner.py \
    --slack-token-filename $HOME/credentials/slack-token.txt \
    --logfile $HOME/logfiles/linux/runner-log.txt \
    --child-timeout 900 \
    --verbose \
    --comment "Linux cron run-all automation" \
    -- \
    ./run-all-aws.py
