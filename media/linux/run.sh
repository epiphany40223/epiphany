#!/bin/bash

set -eoux pipefail

TOP=$HOME/git/epiphany

cd $TOP/media/linux

hour=`date '+%H'`
minute=`date '+%M'`

# This uses $PS1, even if it's not set :-(
# So we have to turn off error detection for a moment...
set +ux
. ./py312/bin/activate
set -ux

# Set timeout for 14.5 minutes because periodically Google APIs
# take a long time for no apparent reason
$TOP/slack/runner.py \
    --slack-token-filename $HOME/credentials/slack-token.txt \
    --logfile $HOME/logfiles/linux/runner-log.txt \
    --child-timeout 870 \
    --verbose \
    --comment "Linux cron run-all automation" \
    -- \
    ./run-all.py

# Now run ParishKit jobs
deactivate
set +ux
. /opt/parishkit/venv/bin/activate
set -ux

# Run the 3 jobs
/opt/parishkit/bin/pk-cron-runner \
    --verbose \
    --config /opt/parishkit/config/pk-cron-runner.yaml \
    ps-to-google-groups ps-to-cc validate-google-calendar

# Run the ministry rosters around 2am
echo run.sh log: hour=$hour, minute=$minute >> /tmp/run.log
if test $hour -eq 2 -a $minute -lt 15; then
    echo run.sh log: lets make ministry rosters >> /tmp/run.log
    /opt/parishkit/bin/pk-cron-runner \
        --verbose \
        --config /opt/parishkit/config/pk-cron-runner.yaml \
        ministry-rosters
fi
