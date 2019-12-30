These scripts run in a Linux environment on Epiphany's \\media-o3020
server.

The `run-all.py` script runs via cron.  It uses a lockfile to ensure
that if one copy of it runs long (i.e., for more than 10 minutes), the
next iteration will simply quit without doing anything (and therefore
not stomping on the copy that is already running).

The `run-all.py` script, in turn, runs `run.sh` scripts in each of the
subdirectories, which then do whatever it is they need to do.
