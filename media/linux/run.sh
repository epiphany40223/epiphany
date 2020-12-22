#!/bin/bash

set -eoux pipefail

TOP=$HOME/git/epiphany

cd $TOP/media/linux

# This uses $PS1, even if it's not set :-(
# So we have to turn off error detection for a moment...
set +ux
. ./py38/bin/activate
set -ux

# Set timeout for 14.5 minutes because periodically Google APIs
# take a long time for no apparent reason
$TOP/slack/runner.py \
    --slack-token-filename /home/coeadmin/slack-token.txt \
    --logfile $HOME/logfiles/linux/runner-log.txt \
    --child-timeout 900 \
    --verbose \
    --comment "Linux cron run-all automation" \
    -- \
    ./run-all.py
