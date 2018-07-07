#!/usr/bin/env python3

'''

Utility functions and helpers for all ECC code

'''

import logging
import logging.handlers

#-------------------------------------------------------------------

def diediedie(msg):
    print(msg)
    print("Aborting")

    exit(1)

#-------------------------------------------------------------------

def setup_logging(info=True, debug=False, logfile=None):
    level=logging.ERROR

    if debug:
        level="DEBUG"
    elif info:
        level="INFO"

    log = logging.getLogger('FToTD')
    log.setLevel(level)

    # Make sure to include the timestamp in each message
    f = logging.Formatter('%(asctime)s %(levelname)-8s: %(message)s')

    # Default log output to stdout
    s = logging.StreamHandler()
    s.setFormatter(f)
    log.addHandler(s)

    # Optionally save to a rotating logfile
    if logfile:
        s = logging.FileHandler(filename=logfile)
        s.setFormatter(f)
        log.addHandler(s)

    log.info('Starting')

    return log
