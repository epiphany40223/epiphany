#!/bin/bash

set -eoux pipefail

TOP=$HOME/git/epiphany

cd $TOP/media/linux

# This uses $PS1, even if it's not set :-(
# So we have to turn off error detection for a moment...
set +ux
. ./py38/bin/activate
set -ux

$TOP/slack/runner.py \
    --slack-token-filename /home/coeadmin/slack-token.txt \
    --logfile runner-log.txt \
    --verbose \
    --comment "Linux cron run-all automation" \
    -- \
    ./run-all.py
