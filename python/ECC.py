#!/usr/bin/env python3
#
# Utility functions and helpers for all ECC code.
#
# Needs:
#
# pip3 install --upgrade pytz
#

import os
import sys
import platform
import logging
import logging.handlers

import pytz

local_tz_name = 'America/Louisville'
local_tz = pytz.timezone(local_tz_name)

#-------------------------------------------------------------------

def diediedie(msg):
    print(msg)
    print("Aborting")

    exit(1)

#-------------------------------------------------------------------

def setup_logging(name=sys.argv[0], info=True, debug=False, logfile=None,
                  log_millisecond=True):
    level=logging.ERROR

    if debug:
        level="DEBUG"
    elif info:
        level="INFO"

    log = logging.getLogger('ECC')
    log.setLevel(level)

    # Make sure to include the timestamp in each message
    extra = "%Y-%m-%d %H:%M:%S" if not log_millisecond else ""
    f = logging.Formatter('%(asctime)s %(levelname)-8s: %(message)s', extra)

    # Default log output to stdout
    s = logging.StreamHandler()
    s.setFormatter(f)
    log.addHandler(s)

    # Optionally save to a rotating logfile
    if logfile:
        s = logging.handlers.RotatingFileHandler(filename=logfile,
                                                 maxBytes=(pow(2,20) * 10),
                                                 backupCount=50)
        s.setFormatter(f)
        log.addHandler(s)

    # If on a Linux system with journald running, also emit to syslog
    # (which will end up at the journald).  Note: the journald may not
    # be running in a WSL environment.
    dev_log = '/dev/log'
    if platform.system() == "Linux" and os.path.exists(dev_log):
        syslog = logging.handlers.SysLogHandler(address=dev_log)

        # For the syslog, we need to get the basename of the
        # python script we are running (otherwise, it'll default to
        # "python" or "python3" or the like).
        b = os.path.basename(name)
        f = logging.Formatter(f'{b}: %(message)s')
        syslog.setFormatter(f)

        log.addHandler(syslog)

    log.info('Starting')

    return log
