#!/usr/bin/env python3

import subprocess
import logging
import logging.handlers
import time
import os

###############################################################################

def setup_logging(logfile, verbose=True, debug=True):
    level=logging.ERROR

    if debug:
        level="DEBUG"
    elif verbose:
        level="INFO"

    global log
    log = logging.getLogger('pds')
    log.setLevel(level)

    # Make sure to include the timestamp in each message
    f = logging.Formatter('%(asctime)s %(levelname)-8s: %(message)s')

    # Default log output to stdout
    s = logging.StreamHandler()
    s.setFormatter(f)
    log.addHandler(s)

    # Optionally save to a rotating logfile
    if logfile:
        s = logging.handlers.RotatingFileHandler(logfile,
                                                 maxBytes=(pow(2,20) * 10),
                                                 backupCount=10)
        s.setFormatter(f)
        log.addHandler(s)

###############################################################################

# A lockfile class so that we can use this lockfile in a context
# manager (so that we can guarantee that the lockfile is removed
# whenever the process exits, for any reason).
class LockFile:
    def __init__(self, lockfile):
        self.lockfile = lockfile
        self.opened = False

    def __enter__(self):
        try:
            fp = open(self.lockfile, mode='x')
            fp.write(time.ctime())
            fp.close()
            log.debug("Locked!")
            self.opened = True
        except:
            # We weren't able to create the file, so that means
            # someone else has it locked.  This is not an error -- we
            # just exit.
            log.debug("Unable to obtain lockfile -- exiting")
            exit(0)

    def __exit__(self, exception_type, exception_value, exeception_traceback):
        if self.opened:
            os.unlink(self.lockfile)
            log.debug("Unlocked")

#---------------------------------------------------------------------------

def main():
    setup_logging(os.path.join(os.environ['HOME'], 'logfiles', 'lock-logfile.txt'))

    c = os.getcwd()
    filename = '{dir}/pds-run-all.lock'.format(dir=c)
    with LockFile(filename) as lockfile:
        os.chdir("/home/coeadmin/git/epiphany/media/linux")

        # Export the PDS database into an SQLite3 database
        os.chdir("export-pds-into-sqlite")
        subprocess.run(["./run.sh"], env=os.environ, check=True)
        os.chdir("..")

        # Run some queries (and act on the results) from that SQLite3
        # database
        os.chdir("pds-sqlite3-queries")
        subprocess.run(["./run.sh"], env=os.environ, check=True)
        os.chdir("..")

if __name__ == '__main__':
    main()
