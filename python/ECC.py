#!/usr/bin/env python3
#
# Utility functions and helpers for all ECC code.
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

class ECCSlackLogHandler(logging.StreamHandler):
    def __init__(self, token_filename, channel="#bot-errors"):
        logging.StreamHandler.__init__(self)
        self.channel = channel

        if not os.path.exists(token_filename):
            print(f"ERROR: Slack token filename {token_filename} does not exist")
            exit(1)

        with open(token_filename, "r") as fp:
            self.token = fp.read().strip()

        # We'll initialize this the first time it is actually used. No need to
        # login to Slack unless we actually intend to send a message.  Note that
        # we set the level for this logger to be "CRITIAL", so we won't actually
        # login to Slack unless log.critical() is invoked.
        self.client  = None

    def emit(self, record):
        # If this is the first time we're emitting a message, then initialize
        # the Slack client object.  This allows apps who don't use the Slack
        # handler to not have the slack_sdk module installed/available.
        import slack_sdk
        if not self.client:
            self.client = slack_sdk.WebClient(token=self.token)

        msg      = self.format(record)
        response = self.client.chat_postMessage(channel=self.channel,
                                                text=msg)

#-------------------------------------------------------------------

def setup_logging(name=sys.argv[0], info=True, debug=False, logfile=None,
                  log_millisecond=True, rotate=False,
                  slack_token_filename=None, slack_channel="#bot-errors"):
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

    if slack_token_filename:
        s = ECCSlackLogHandler(slack_token_filename, slack_channel)
        s.setLevel('CRITICAL')
        log.addHandler(s)

    # Optionally save to a logfile
    if logfile:
        if rotate:
            s = logging.handlers.RotatingFileHandler(filename=logfile,
                                                     maxBytes=(pow(2,20) * 10),
                                                     backupCount=50)
        else:
            if platform.system() != "Windows":
                # According to
                # https://docs.python.org/3/library/logging.handlers.html#watchedfilehandler,
                # the WatchedFile handler is not appropriate for MS
                # Windows.  The WatchedFile handler is friendly to
                # services like the Linux logrotater (i.e.,
                # WatchedFile will check the file before it writes
                # anything, and will re-open the file if it needs to).
                s = logging.handlers.WatchedFileHandler(filename=logfile)
            else:
                s = logging.FileHandler(filename=logfile)
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
