#!/usr/bin/env python3

import subprocess
import datetime
import logging
import logging.handlers
import time
import sys
import os

# We assume that there is a "ecc-python-modules" sym link in this
# directory that points to the directory with ECC.py and friends.
moddir = os.path.join(os.getcwd(), 'ecc-python-modules')
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)

sys.path.insert(0, moddir)

import ECC

###############################################################################

out = subprocess.run(['git', 'rev-parse', '--show-toplevel'],
                    capture_output=True)
git_top = out.stdout.decode('utf-8').strip()

# Globals
logfile  = os.path.join(os.environ['HOME'], 'logfiles', 'lock-logfile.txt')
lockfile = os.path.join(git_top, 'media', 'linux', 'pds-run-all.lock')

###############################################################################

# A lockfile class so that we can use this lockfile in a context
# manager (so that we can guarantee that the lockfile is removed
# whenever the process exits, for any reason).
class LockFile:
    def __init__(self, lockfile, log):
        self.lockfile = lockfile
        self.opened = False
        self.log = log

        # JMS Oct 2022: Change max lockfile timeout to 16 minutes
        self.max_lockfile_age = datetime.timedelta(minutes=16)

    def __enter__(self):
        while True:
            try:
                fp = open(self.lockfile, mode='x')
                fp.write(time.ctime())
                fp.close()
                self.log.debug("Locked!")
                self.opened = True
                return
            except:
                # We weren't able to create the file, so that means
                # someone else has it locked.  If the lockfile is "old"
                # (e.g., over an hour old), then something is wrong --
                # alert a human.
                try_again = self._check_lockfile_age()
                if try_again:
                    continue

                # If we get here, the lock file isn't old.  So this is not
                # an error -- we just exit.
                self.log.warning("Unable to obtain lockfile -- exiting")
                exit(0)

    def _check_lockfile_age(self):
        try:
            lockfile_stat = os.stat(self.lockfile)
        except:
            self.log.error(f"Unable to stat() the lockfile {self.lockfile}")
            exit(1)

        now = datetime.datetime.now()
        lockfile_create = datetime.datetime.fromtimestamp(lockfile_stat.st_ctime)
        age = now - lockfile_create
        if age >= self.max_lockfile_age:
            self.log.error(f"Lockfile is too old ({self.lockfile})")
            self.log.error(f"Created: {lockfile_create}")
            self.log.error(f"Age: {age}")
            # In Oct 2022, some "awk" process is hanging every day,
            # and we get stale lockfiles.  Hence, after the timeout,
            # just remove the lockfile (vs. exiting in error).
            #exit(1)
            self.log.error("REMOVING LOCKFILE")
            os.unlink(self.lockfile)
            return True

        # If we get here, the lockfile isn't too old.  So just return.
        return False

    def __exit__(self, exception_type, exception_value, exeception_traceback):
        if self.opened:
            os.unlink(self.lockfile)
            self.log.debug("Unlocked")

#---------------------------------------------------------------------------

def main():
    log = ECC.setup_logging(info=True, debug=True,
                            logfile=logfile, rotate=True)

    # Only run if we can get the logfile
    with LockFile(lockfile, log) as lockfile_obj:
        for subdir in ['ricoh', 'export-pds-into-sqlite', 'pds-sqlite3-queries',
                       'calendar-reservations']:
            os.chdir(os.path.join(git_top, 'media', 'linux', subdir))
            subprocess.run(["./run.sh"], env=os.environ, check=True)

if __name__ == '__main__':
    main()
