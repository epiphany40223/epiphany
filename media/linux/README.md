# Overview

These scripts run in a Linux environment to run Epiphany's automation.

## July, 2025: AWS (free) EC2 instance

The infrastructure has been updated to run on an AWS (free) EC2
instance, and is therefore pure Linux (without WSL weirdness).

There's now `*-aws.*` scripts (e.g., `run-all-aws.py` and
`run-aws.sh`) that do the same thing as the older WSL-based scripts,
but slightly updated for the AWS environment.

If this AWS test works out, we'll probably just remove all the WSL
stuff and consolidate down to the pure Linux environment.

## Original: WSL on Windows

This infrastructure runs on Epiphany's \\media-o3020 server.

The `run-all.py` script runs via cron.  It uses a lockfile to ensure
that if one copy of it runs long (i.e., for more than 10 minutes), the
next iteration will simply quit without doing anything (and therefore
not stomping on the copy that is already running).

The `run-all.py` script, in turn, runs `run.sh` scripts in each of the
subdirectories, which then do whatever it is they need to do.
