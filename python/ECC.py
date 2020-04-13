#!/usr/bin/env python3
#
# Utility functions and helpers for all ECC code.
#
# Needs:
#
# pip3 install --upgrade pytz
#

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

def setup_logging(info=True, debug=False, logfile=None,
                  log_millisecond=True):
    level=logging.ERROR

    if debug:
        level="DEBUG"
    elif info:
        level="INFO"

    log = logging.getLogger('FToTD')
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

    log.info('Starting')

    return log
